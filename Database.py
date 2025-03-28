import sqlite3
from datetime import datetime, timedelta
import logging
# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        """Создает таблицы, если они не существуют."""
        try:
            # Создаем таблицу records
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending', -- Статусы: pending, confirmed, declined
                    notification_sent INTEGER DEFAULT 0 -- 0 - уведомление не отправлено, 1 - уведомление отправлено
                )
            ''')

            # Создаем таблицу schedule_mode
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_mode (
                    mode TEXT NOT NULL DEFAULT 'default' -- Режим: 'default' или 'excel'
                )
            ''')

            # Убедимся, что в таблице schedule_mode есть хотя бы одна запись
            self.cursor.execute('''
                INSERT OR IGNORE INTO schedule_mode (rowid, mode)
                VALUES (1, 'default')
            ''')
            # Создаем таблицу для расписания, если ее нет
            self.cursor.execute(''' 
                            CREATE TABLE IF NOT EXISTS schedule (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date TEXT NOT NULL,
                                day_of_week TEXT NOT NULL,
                                status TEXT NOT NULL,
                                start_shift TEXT,
                                start_break TEXT,
                                end_break TEXT,
                                end_shift TEXT
                            )
                        ''')

            self.conn.commit()
            print("Таблицы успешно созданы или уже существуют.")
        except sqlite3.Error as e:
            print(f"Ошибка при создании таблиц: {e}")

    def get_available_dates(self):
        """Получает список доступных дат из таблицы расписания, исключая прошедшие дни."""
        today = datetime.now().strftime("%Y-%m-%d")  # Получаем текущую дату в формате YYYY-MM-DD
        query = "SELECT DISTINCT date FROM schedule WHERE status = 'Рабочий' AND date >= ?"
        return [row[0] for row in self.cursor.execute(query, (today,)).fetchall()]

    def clear_schedule(self):
        """Очищает таблицу с расписанием перед загрузкой новых данных"""
        try:
            query = "DELETE FROM schedule"  # Удаляет все записи из таблицы
            self.cursor.execute(query)
            self.conn.commit()
            logger.info("Таблица расписания успешно очищена.")
        except sqlite3.Error as e:
            logger.error(f"Ошибка при очистке таблицы расписания: {e}", exc_info=True)
            self.conn.rollback()

    def get_available_times(self, date):
        """
        Получает доступные временные слоты для записи на указанную дату,
        исключая прошедшее время для текущего дня.
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M") if date == now.strftime("%Y-%m-%d") else "00:00"

        query = """
        SELECT start_shift, start_break, end_break, end_shift 
        FROM schedule 
        WHERE date = ? AND status = 'Рабочий'
        """
        result = self.cursor.execute(query, (date,)).fetchall()

        available_times = []

        for start_shift, start_break, end_break, end_shift in result:
            # Преобразуем строки в datetime-объекты
            start_shift = datetime.strptime(start_shift, "%H:%M")
            start_break = datetime.strptime(start_break, "%H:%M")
            end_break = datetime.strptime(end_break, "%H:%M")
            end_shift = datetime.strptime(end_shift, "%H:%M")

            # Добавляем интервалы работы, исключая перерыв
            slot = start_shift
            while slot + timedelta(hours=1) <= end_shift:
                slot_str = slot.strftime("%H:%M")

                # Фильтруем прошедшее время для сегодняшнего дня
                if date > now.strftime("%Y-%m-%d") or slot_str >= current_time:
                    if not (start_break <= slot < end_break):
                        available_times.append(slot_str)

                slot += timedelta(hours=1)

        return available_times

    def insert_schedule(self, schedule_data):
        """Вставляет данные расписания в таблицу schedule."""
        try:
            # Логируем передаваемые данные
            logger.info(f"Попытка вставки {len(schedule_data)} записей в таблицу расписания.")

            query = '''
                INSERT INTO schedule (date, day_of_week, status, start_shift, start_break, end_break, end_shift)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''

            # Выполнение запроса
            self.cursor.executemany(query, schedule_data)
            self.conn.commit()

            # Логируем успешную вставку
            logger.info(f"{len(schedule_data)} записей расписания добавлено в базу данных.")

        except sqlite3.Error as e:
            # Логируем ошибку с деталями
            logger.error(f"Ошибка при добавлении расписания: {e}", exc_info=True)
            self.conn.rollback()

    def get_schedule(self):
        """Возвращает все записи расписания."""
        try:
            self.cursor.execute('SELECT * FROM schedule')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении расписания: {e}")
            return []

    def get_active_records_user_for_reminder(self, reminder_time):
        """Получает активные записи для пользователей, которые должны быть напомнены за 1 час."""
        try:
            # Преобразуем время в формате datetime для SQL-запроса
            reminder_time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(''' 
                SELECT * 
                FROM records 
                WHERE status = 'Подтверждена' 
                AND datetime(date || ' ' || time) <= datetime(?)
                AND datetime(date || ' ' || time) > datetime(?)
            ''', (reminder_time_str, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении записей для напоминаний: {e}")
            return []

    def insert_record(self, telegram_id, name, phone, date, time):
        """
        Добавляет новую запись в базу данных, преобразуя дату в формат YYYY-MM-DD и время в HH:MM:SS.
        """
        try:
            # Логируем входные данные перед преобразованием
            print(f"Исходные данные: {telegram_id}, {name}, {phone}, {date}, {time}")

            # Проверяем, в каком формате дата (YYYY-MM-DD или DD-MM-YYYY)
            if '-' in date and len(date) == 10:
                parts = date.split('-')
                if len(parts[0]) == 4:  # Если год идет первым (YYYY-MM-DD) — значит, формат уже правильный
                    pass
                else:  # Если день идет первым (DD-MM-YYYY), то конвертируем в YYYY-MM-DD
                    try:
                        date_obj = datetime.strptime(date, "%d-%m-%Y")
                        date = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        print(f"Ошибка: Неправильный формат даты - {date}")
                        return None

            # Преобразуем время в формат HH:MM:SS
            parts = time.split(':')
            hours = parts[0].zfill(2)  # Добавляем ведущий ноль для часов
            minutes = parts[1].zfill(2) if len(parts) > 1 else '00'  # Добавляем ведущий ноль для минут
            time = f"{hours}:{minutes}:00"  # Преобразуем в HH:MM:SS

            # Логируем перед вставкой
            print(f"Вставка записи: {telegram_id}, {name}, {phone}, {date}, {time}")

            # Выполняем запись в базу данных
            self.cursor.execute('''
                INSERT INTO records (telegram_id, name, phone, date, time)
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, name, phone, date, time))
            self.conn.commit()

            return self.cursor.lastrowid  # Возвращаем ID созданной записи
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении записи: {e}")
            self.conn.rollback()
            return None

    def get_record_by_id(self, record_id):
        """Возвращает запись по её ID."""
        try:
            self.cursor.execute('''
                SELECT * FROM records WHERE id = ?
            ''', (record_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Ошибка при получении записи по ID: {e}")
            return None

    def update_record_status(self, record_id, status):
        """Обновляет статус записи."""
        try:
            self.cursor.execute('''
                UPDATE records
                SET status = ?
                WHERE id = ?
            ''', (status, record_id))
            self.conn.commit()
            return self.cursor.rowcount > 0  # Возвращаем True, если запись была обновлена
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении статуса записи: {e}")
            self.conn.rollback()
            return False

    def get_active_records_user(self, telegram_id):
        """Возвращает активные записи для пользователя, которые еще не прошли."""
        try:
            self.cursor.execute('''
                SELECT *
                FROM records
                WHERE telegram_id = ?
                AND status = 'Подтверждена'
                AND datetime(date || ' ' || time) >= datetime('now');
            ''', (telegram_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении активных записей для пользователя: {e}")
            return []

    def get_history_records_user(self, telegram_id):
        """Возвращает все записи пользователя, без фильтрации по дате, только по telegram_id."""
        try:
            self.cursor.execute('''
                SELECT *
                FROM records
                WHERE telegram_id = ?
            ''', (telegram_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении исторических записей для пользователя: {e}")
            return []

    def get_active_records_admin(self):
        """Возвращает активные записи для администратора, которые еще не прошли."""
        try:
            self.cursor.execute('''
                SELECT *
                FROM records
                WHERE status = 'Подтверждена'
                AND datetime(date || ' ' || time) >= datetime('now');
            ''')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении активных записей для администратора: {e}")
            return []

    def get_all_records(self):
        """Возвращает все записи из базы данных."""
        try:
            self.cursor.execute('''
                SELECT * FROM records
            ''')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении всех записей: {e}")
            return []

    def update_notification_sent(self, record_id):
        """
        Обновляет статус отправки уведомления для записи с данным ID.
        """
        try:
            self.cursor.execute('''
                UPDATE records
                SET notification_sent = 1
                WHERE id = ?;
            ''', (record_id,))
            self.conn.commit()
            print(f"Статус уведомления для записи {record_id} обновлен.")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении статуса уведомления: {e}")
            self.conn.rollback()

    def close(self):
        """Закрывает соединение с базой данных."""
        try:
            self.conn.close()
        except sqlite3.Error as e:
            print(f"Ошибка при закрытии соединения с базой данных: {e}")
