from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
import logging
from keyboards import InlineKeyboard  # Импортируем наш класс InlineKeyboard

logger = logging.getLogger(__name__)

class Settings:
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance

    async def show_settings(self, update: Update, context: CallbackContext):
        """Отображает клавиатуру настроек."""
        logger.info("Вызван метод show_settings")
        reply_markup = InlineKeyboard.settings_keyboard()
        query = update.callback_query

        if query:
            await query.answer()
            logger.info("Ответили на CallbackQuery")
            await query.edit_message_text(
                text="Выберите настройку:",
                reply_markup=reply_markup
            )

    async def handle_settings(self, update: Update, context: CallbackContext):
        """Обработчик для кнопок настроек."""
        query = update.callback_query
        if query:
            await query.answer()

            if query.data == 'settings_schedule':
                # Получаем текущий режим расписания
                current_mode = self.get_current_schedule_mode()
                reply_markup = InlineKeyboard.schedule_keyboard(current_mode)
                await query.edit_message_text(
                    text=f"Текущий режим: {current_mode}\nВыберите действие:",
                    reply_markup=reply_markup
                )
            elif query.data == 'settings_option_2':
                await query.edit_message_text(text="Настройка 2 активирована.")
            elif query.data == 'cancel':
                await self.cancel(update, context)

    async def handle_schedule_option(self, update: Update, context: CallbackContext):
        """Обработчик для выбора типа расписания."""
        query = update.callback_query
        if query:
            await query.answer()

            if query.data == 'enable_standard_schedule':
                self.update_schedule_mode('default')
                await query.edit_message_text(text="Стандартное расписание включено.")
            elif query.data == 'enable_excel_schedule':
                self.update_schedule_mode('excel')
                await query.edit_message_text(text="Excel расписание включено.")
            elif query.data == 'cancel':
                await self.cancel(update, context)

    def get_current_schedule_mode(self):
        """Получает текущий режим расписания из базы данных."""
        try:
            cursor = self.bot_instance.db.cursor
            cursor.execute("SELECT mode FROM schedule_mode WHERE rowid = 1")
            result = cursor.fetchone()
            return result[0] if result else 'default'
        except Exception as e:
            logger.error(f"Ошибка при получении режима расписания: {e}")
            return 'default'

    def update_schedule_mode(self, mode: str):
        """Обновляет режим расписания в базе данных."""
        try:
            cursor = self.bot_instance.db.cursor
            cursor.execute("UPDATE schedule_mode SET mode = ? WHERE rowid = 1", (mode,))
            self.bot_instance.db.conn.commit()
            logger.info(f"Режим расписания обновлен на: {mode}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении режима расписания: {e}")

    async def cancel(self, update: Update, context: CallbackContext):
        """Обработчик для кнопки 'Назад'."""
        await self.bot_instance.cancel(update, context)  # Вызов метода cancel из класса бота
