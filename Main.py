from telegram.ext import Application
from Bot import TelegramBot
import Config  # Импортируем конфиг для использования токена

if __name__ == '__main__':
    # Создаем объект application с токеном из Config.py
    application = Application.builder().token(Config.Config.TOKEN).build()  # Убедитесь, что обращаетесь к Config.TOKEN

    # Передаем application в конструктор TelegramBot
    bot = TelegramBot(application)

    # Запускаем бота
    bot.run()  # Запуск бота
