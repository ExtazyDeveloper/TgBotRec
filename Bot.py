import logging
import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    Application,
    filters
)
from Config import Config
from Database import Database
from utils import get_display_name
from keyboards import InlineKeyboard  # Импортируем наш класс InlineKeyboard
from Settings import Settings  # Импортируем ваш класс
from ScheduleExcelGenerator import ScheduleExcelGenerator
from ScheduleExcelProcessor import ScheduleExcelProcessor



# Включаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger("Bot")

# Состояния для разговорного обработчика
SELECT_DATE, SELECT_TIME, GET_NAME, GET_PHONE = range(4)

class TelegramBot:
    def __init__(self, application):
        """Конструктор класса TelegramBot."""
        self.application = application
        self.db = Database('records.db')  # Путь к базе данных SQLite
        self.admin_id = Config.ADMIN_ID  # ID администратора
        self.settings = Settings(self)  # Создаем объект настроек
        self.schedule_processor = ScheduleExcelProcessor(self.db)  # Передаем self.db в ScheduleExcelProcessor
    async def send_excel(self, update: Update, context: CallbackContext):
        # Создаем объект для генерации расписания
        schedule_generator = ScheduleExcelGenerator()
        schedule_generator.create_schedule()
        schedule_generator.save("schedule_week.xlsx")

        # Отправка файла пользователю
        with open("schedule_week.xlsx", "rb") as file:
            await update.message.reply_document(
                document=file,
                filename="schedule_week.xlsx",
                caption="Вот ваше расписание на неделю."
            )

    async def send_notifications(self):
        """Проверка и отправка уведомлений пользователю и админу за час до записи."""
        try:
            now = datetime.now()
            one_hour_later = now + timedelta(hours=1)

            # Получаем все записи со статусом 'Подтверждена', где время записи через час или меньше
            records = self.db.get_active_records_admin()

            if not records:
                logger.info("Нет записей для отправки уведомлений.")

            for record in records:
                record_datetime_str = f"{record[4]} {record[5]}"  # date и time из записи
                record_datetime = datetime.strptime(record_datetime_str,
                                                    "%Y-%m-%d %H:%M")  # Используем правильный формат

                # Проверяем, если время записи через час или меньше
                if now <= record_datetime <= one_hour_later:
                    user_id = record[1]  # Telegram ID пользователя

                    # Проверяем, было ли уже отправлено уведомление (если notification_sent == 0)
                    if record[6] == 0:  # Предполагаем, что 6-й индекс это notification_sent
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=f"Напоминаем, что ваша запись на {record[4]} в {record[5]} состоится через 1 час или меньше!"
                        )

                        # Отправляем уведомление админу
                        await self.application.bot.send_message(
                            chat_id=self.admin_id,
                            text=f"Напоминание: У пользователя {record[2]} (ID {record[1]}) запись на {record[4]} в {record[5]} через 1 час или меньше."
                        )

                        # Обновляем флаг notification_sent в базе данных
                        self.db.update_notification_sent(record[0])  # record[0] - это ID записи

                        logger.info(f"Уведомление отправлено пользователю {user_id} и администратору.")
                    else:
                        logger.info(f"Запись пользователя {record[1]} уже получила уведомление.")

                else:
                    logger.info(f"Запись пользователя {record[1]} не подходит для уведомления.")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомлений: {str(e)}")

    async def start_notifications(self):
        """Запуск функции для уведомлений с интервалом в 60 минут."""
        while True:

            await self.send_notifications()
            await asyncio.sleep(1 * 60)  # Повторять каждый час

    async def start(self, update: Update, context: CallbackContext):
        """
        Обрабатывает команду /start и показывает inline-кнопки.
        Для администратора добавляется кнопка "Настройки", а также "Настроить расписание", если включен режим Excel.
        """
        user_id = update.effective_user.id  # Получаем ID пользователя
        is_admin = self.is_admin(user_id)  # Проверяем, является ли пользователь администратором

        # Получаем текущий режим расписания
        schedule_mode = self.settings.get_current_schedule_mode()

        # Формируем клавиатуру с учетом статуса администратора и режима расписания
        reply_markup = InlineKeyboard.start_keyboard(is_admin=is_admin, schedule_mode=schedule_mode)

        # Отправляем сообщение с клавиатурой
        await update.message.reply_text(
            "Добро пожаловать! Выберите действие:",
            reply_markup=reply_markup
        )

    async def handle_button(self, update: Update, context: CallbackContext):
        """Обрабатывает нажатия кнопок."""
        query = update.callback_query
        await query.answer()

        # Проверяем текущий режим расписания
        current_mode = self.settings.get_current_schedule_mode()

        if current_mode == 'default':
            # Работа с дефолтным расписанием
            if query.data == 'start_registration':
                today = datetime.today()
                next_7_days = [today + timedelta(days=i) for i in range(7)]
                reply_markup = InlineKeyboard.select_date_keyboard(today, next_7_days)
                await query.edit_message_text("Выберите дату для записи:", reply_markup=reply_markup)
                return SELECT_DATE

            elif query.data.startswith('date_'):
                date_index = int(query.data.split('_')[1])
                today = datetime.today()
                selected_date = (today + timedelta(days=date_index)).strftime("%d-%m-%Y")
                context.user_data['selected_date'] = selected_date

                selected_date_db = f"{selected_date[6:10]}-{selected_date[3:5]}-{selected_date[0:2]}"
                now = datetime.now()
                selected_datetime = datetime.strptime(selected_date, "%d-%m-%Y")

                occupied_times = {
                    time[:5] for time, in self.db.cursor.execute(
                        '''
                        SELECT time
                        FROM records
                        WHERE date = ? AND status = 'Подтверждена'
                        ''',
                        (selected_date_db,)
                    )
                }

                available_hours = [
                    f"{str(hour).zfill(2)}:00"
                    for hour in range(9, 19)
                    if not (selected_datetime.date() == now.date() and hour <= now.hour)
                       and f"{str(hour).zfill(2)}:00" not in occupied_times
                ]

                if not available_hours:
                    next_7_days = [today + timedelta(days=i) for i in range(7)]
                    reply_markup = InlineKeyboard.select_date_keyboard(today, next_7_days)
                    await query.edit_message_text(
                        text=(f"На выбранную дату ({selected_date}) нет доступного времени.\n"
                              "Пожалуйста, выберите другой день."),
                        reply_markup=reply_markup
                    )
                    return SELECT_DATE

                reply_markup = InlineKeyboard.select_time_keyboard(available_hours, selected_date)
                await query.edit_message_text(
                    text=f"Выберите время для {selected_date}:",
                    reply_markup=reply_markup
                )
                return SELECT_TIME

            elif query.data.startswith('time_'):
                selected_time = query.data.split('_')[1]
                context.user_data['selected_time'] = selected_time
                await query.message.reply_text("Введите ваше имя:")
                await query.delete_message()
                return GET_NAME

        elif current_mode == 'excel':
            # Работа с расписанием Excel
            if query.data == 'start_registration':
                available_dates = self.db.get_available_dates()
                if not available_dates:
                    await query.edit_message_text("Нет доступных дат для записи.")
                    return

                reply_markup = InlineKeyboard.select_date_keyboard_excel(available_dates)
                await query.edit_message_text("Выберите дату для записи:", reply_markup=reply_markup)
                return SELECT_DATE

            elif query.data.startswith('date_'):
                selected_date = query.data.split('_')[1]
                context.user_data['selected_date'] = selected_date

                available_times = self.db.get_available_times(selected_date)
                if not available_times:
                    await query.edit_message_text(
                        text=f"На выбранную дату ({selected_date}) нет доступного времени.",
                        reply_markup=InlineKeyboard.back_button_keyboard()
                    )
                    return SELECT_DATE

                reply_markup = InlineKeyboard.select_time_keyboard(available_times, selected_date)
                await query.edit_message_text(
                    text=f"Выберите время для {selected_date}:",
                    reply_markup=reply_markup
                )
                return SELECT_TIME

            elif query.data.startswith('time_'):
                selected_time = query.data.split('_')[1]
                context.user_data['selected_time'] = selected_time
                await query.message.reply_text("Введите ваше имя:")
                await query.delete_message()
                return GET_NAME

        # Обработка для других кнопок
        if query.data == 'view_records':
            telegram_id = query.from_user.id
            is_admin = self.is_admin(telegram_id)
            reply_markup = InlineKeyboard.view_records_keyboard(is_admin)
            await query.edit_message_text("Выберите тип записей для просмотра:", reply_markup=reply_markup)
            return

        elif query.data == 'view_active_records_admin':
            records = self.db.get_active_records_admin()
            if not records:
                await query.edit_message_text("Нет активных записей.")
                return

            text = "Активные записи (Админ):\n"
            for record in records:
                user = await context.bot.get_chat(record[1])
                display_name = get_display_name(user)
                text += (
                    f"ID: {record[0]}, Имя: {record[2]}, Телефон: {record[3]}, "
                    f"Дата: {record[4]}, Время: {record[5]}, Телеграм: {display_name}\n"
                )

            reply_markup = InlineKeyboard.back_button_keyboard()
            await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif query.data == 'view_history_records_admin':
            records = self.db.get_all_records()
            if not records:
                await query.edit_message_text("История записей пуста.")
                return

            text = "История записей (Админ):\n"
            for record in records:
                user = await context.bot.get_chat(record[1])
                display_name = get_display_name(user)
                text += (
                    f"ID: {record[0]}, Имя: {record[2]}, Телефон: {record[3]}, "
                    f"Дата: {record[4]}, Время: {record[5]}, Статус: {record[6]}, "
                    f"Телеграм: {display_name}\n"
                )

            reply_markup = InlineKeyboard.back_button_keyboard()
            await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif query.data == 'view_active_records_user':
            telegram_id = query.from_user.id
            records = self.db.get_active_records_user(telegram_id)
            if not records:
                await query.edit_message_text("У вас нет активных записей.")
                return

            text = "Ваши активные записи:\n"
            for record in records:
                text += f"Дата: {record[4]}, Время: {record[5]}\n"

            reply_markup = InlineKeyboard.back_button_keyboard()
            await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif query.data == 'view_history_records_user':
            telegram_id = query.from_user.id
            records = self.db.get_history_records_user(telegram_id)
            if not records:
                await query.edit_message_text("У вас нет завершенных или отклоненных записей.")
                return

            text = "История ваших записей:\n"
            for record in records:
                text += f"Дата: {record[4]}, Время: {record[5]}\n"

            reply_markup = InlineKeyboard.back_button_keyboard()
            await query.edit_message_text(text=text, reply_markup=reply_markup)

    async def get_name(self, update: Update, context: CallbackContext):
        user_name = update.message.text
        context.user_data['name'] = user_name

        await update.message.reply_text("Введите ваш номер телефона:")
        return GET_PHONE

    async def get_phone(self, update: Update, context: CallbackContext):
        phone = update.message.text
        context.user_data['phone'] = phone

        telegram_id = update.message.from_user.id
        name = context.user_data['name']
        phone = context.user_data['phone']
        date = context.user_data['selected_date']
        time = context.user_data['selected_time']

        user = update.message.from_user
        display_name = get_display_name(user)  # Получаем display_name для пользователя

        booking_id = self.db.insert_record(telegram_id, name, phone, date, time)
        if booking_id is None:
            await update.message.reply_text("Ошибка: не удалось создать запись. Попробуйте снова.")
            return ConversationHandler.END

        reply_markup = InlineKeyboard.confirm_reject_keyboard(booking_id)

        await self.application.bot.send_message(
            chat_id=self.admin_id,
            text = f"Новая запись:\nИмя: {name}\nТелефон: {phone}\nДата: {date}\nВремя: {time}\nТелеграм: {display_name}",
            reply_markup=reply_markup
        )
        await update.message.reply_text("Ваша запись ожидает подтверждения. Ожидайте уведомления.")
        return ConversationHandler.END

    async def admin_response(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        action, booking_id = query.data.split('_')
        try:
            booking_id = int(booking_id)
        except ValueError:
            await query.edit_message_text("Ошибка: Неверный ID записи.")
            return

        booking = self.db.get_record_by_id(booking_id)
        if not booking:
            await query.edit_message_text("Запись не найдена.")
            return

        if action == 'confirm':
            self.db.update_record_status(booking_id, "Подтверждена")
            await self.application.bot.send_message(
                chat_id=booking[1],
                text=f"Ваша запись на {booking[4]} в {booking[5]} подтверждена!",
                reply_markup = InlineKeyboard.start_keyboard()
            )

            await query.edit_message_text("Запись подтверждена.")



        elif action == 'reject':
            # Обновляем статус записи в базе данных
            self.db.update_record_status(booking_id, "Отклонена")

            # Отправляем сообщение пользователю о том, что его запись отклонена
            # Сразу добавляем кнопку "Назад" в том же сообщении
            reply_markup = InlineKeyboard.back_button_keyboard()  # Используем метод для кнопки "Назад"

            # Отправляем сообщение с текстом и кнопкой "Назад"
            await self.application.bot.send_message(
                chat_id=booking[1],
                text="К сожалению, ваша запись была отклонена. С вами свяжется оператор для уточнения деталей.",
                reply_markup=reply_markup
            )

            # Также редактируем сообщение в админской панели (если нужно)
            await query.edit_message_text("Запись отклонена.")
            await query.delete_message()

    async def cancel(self, update: Update, context: CallbackContext):
        """
        Отменяет текущий процесс и возвращает пользователя к стартовому меню.
        Для администратора добавляется кнопка "Настройки", а также "Настроить расписание", если включен режим Excel.
        """
        query = update.callback_query
        if query:
            await query.answer()  # Обязательно ответить на CallbackQuery

            # Определяем, является ли пользователь администратором
            user_id = query.from_user.id
            is_admin = self.is_admin(user_id)

            # Получаем текущий режим расписания
            schedule_mode = self.settings.get_current_schedule_mode()

            # Формируем клавиатуру с учетом статуса администратора и режима расписания
            reply_markup = InlineKeyboard.start_keyboard(is_admin=is_admin, schedule_mode=schedule_mode)

            # Обновляем сообщение с новой клавиатурой
            await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)

        return ConversationHandler.END

    def is_admin(self, user_id):
        """Проверка, является ли пользователь администратором."""
        return user_id == Config.ADMIN_ID

    def run(self):

        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.settings.show_settings, pattern='^settings$'))
        logger.info("CallbackQueryHandler для 'settings' добавлен")
        self.application.add_handler(CallbackQueryHandler(self.settings.handle_settings, pattern='^settings_schedule$'))
        self.application.add_handler(
            CallbackQueryHandler(self.settings.handle_schedule_option, pattern='^enable_standard_schedule$'))
        self.application.add_handler(
            CallbackQueryHandler(self.settings.handle_schedule_option, pattern='^enable_excel_schedule$'))

        # Добавляем обработчик для команды отправки Excel-файла с расписанием
        self.application.add_handler(CommandHandler("send_excel", self.send_excel))
        # Обработчик для команды отправки Excel-файла с расписанием
        schedule_conversation = ConversationHandler(
            entry_points=[CommandHandler("get_excel", self.schedule_processor.start_get_schedule)],
            states={
                ScheduleExcelProcessor.WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, self.schedule_processor.get_schedule_from_file)]
            },
            fallbacks=[CommandHandler("cancel", self.schedule_processor.cancel)]
        )
        self.application.add_handler(schedule_conversation)

        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^start_registration$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^view_records$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^view_active_records_admin$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^view_history_records_admin$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^view_active_records_user$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_button, pattern='^view_history_records_user$'))
        self.application.add_handler(CallbackQueryHandler(self.cancel, pattern='^cancel$'))


        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.handle_button, pattern='^date_')],
            states={
                SELECT_DATE: [CallbackQueryHandler(self.handle_button, pattern='^date_')],
                SELECT_TIME: [CallbackQueryHandler(self.handle_button, pattern='^time_')],
                GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_name)],
                GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        # Получаем текущий цикл событий
        loop = asyncio.get_event_loop()

        # Запускаем задачу для уведомлений в фоне
        loop.create_task(self.start_notifications())

        self.application.add_handler(conv_handler)
        self.application.add_handler(CallbackQueryHandler(self.admin_response, pattern='^(confirm|reject)_\d+$'))

        self.application.run_polling()
