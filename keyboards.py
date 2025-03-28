from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import timedelta

class InlineKeyboard:

    @staticmethod
    def select_date_keyboard_excel(available_dates):
        """Формирует клавиатуру для выбора доступной даты (режим Excel)."""
        buttons = [
            [InlineKeyboardButton(date, callback_data=f"date_{date}")]
            for date in available_dates
        ]
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def select_time_keyboard(available_times, selected_date):
        """Формирует клавиатуру для выбора времени."""
        buttons = [
            [InlineKeyboardButton(time, callback_data=f"time_{time}")]
            for time in available_times
        ]
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def schedule_keyboard(current_mode):
        """Возвращает клавиатуру для выбора типа расписания."""
        if current_mode == 'default':
            keyboard = [
                [InlineKeyboardButton("Включить Excel расписание", callback_data='enable_excel_schedule')],
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("Включить стандартное расписание", callback_data='enable_standard_schedule')],
            ]

        keyboard.append([InlineKeyboardButton("Назад", callback_data='cancel')])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_keyboard():
        """Возвращает клавиатуру для раздела настроек."""
        keyboard = [
            [InlineKeyboardButton("Расписание", callback_data='settings_schedule')],
            [InlineKeyboardButton("Настройка 2", callback_data='settings_option_2')],
            [InlineKeyboardButton("Назад", callback_data='cancel')],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def start_keyboard(is_admin=False, schedule_mode="default"):
        """
        Возвращает клавиатуру для старта.
        Если пользователь администратор и включен режим Excel, добавляется кнопка "Настроить расписание".
        """
        keyboard = [
            [InlineKeyboardButton("Записаться", callback_data='start_registration')],
            [InlineKeyboardButton("Мои записи", callback_data='view_records')],
        ]

        if is_admin:
            keyboard.append([InlineKeyboardButton("Настройки", callback_data='settings')])

            # Добавляем кнопку "Настроить расписание", если режим Excel включен
            if schedule_mode == "excel":
                keyboard.append([InlineKeyboardButton("Настроить расписание", callback_data='configure_schedule')])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def select_date_keyboard(today, next_7_days):
        """Возвращает клавиатуру для выбора даты."""
        keyboard = [
            [InlineKeyboardButton((today + timedelta(days=i)).strftime("%d-%m-%Y"), callback_data=f"date_{i}")]
            for i in range(7)
        ]
        keyboard.append([InlineKeyboardButton("Назад", callback_data='cancel')])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def select_time_keyboard(available_hours, selected_date):
        """Возвращает клавиатуру для выбора времени."""
        keyboard = [
            [InlineKeyboardButton(time, callback_data=f"time_{time}")]
            for time in available_hours
        ]
        keyboard.append([InlineKeyboardButton("Назад", callback_data='cancel')])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def view_records_keyboard(is_admin):
        """Возвращает клавиатуру для просмотра записей."""
        if is_admin:
            keyboard = [
                [InlineKeyboardButton("Активные записи (Админ)", callback_data='view_active_records_admin')],
                [InlineKeyboardButton("История (Админ)", callback_data='view_history_records_admin')]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("Активные записи", callback_data='view_active_records_user')],
                [InlineKeyboardButton("История", callback_data='view_history_records_user')]
            ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirm_reject_keyboard(booking_id):
        """Возвращает клавиатуру для подтверждения или отклонения записи."""
        keyboard = [
            [
                InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{booking_id}"),
                InlineKeyboardButton("Отклонить", callback_data=f"reject_{booking_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def back_button_keyboard(callback_data='cancel'):
        """Возвращает клавиатуру с кнопкой 'Назад'."""
        keyboard = [
            [InlineKeyboardButton("Назад", callback_data=callback_data)]
        ]
        return InlineKeyboardMarkup(keyboard)
