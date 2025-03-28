# utils.py
def get_display_name(user):
    username = user.username  # Получаем имя пользователя
    telegram_id = user.id  # Получаем Telegram ID
    # Если username отсутствует, используем "Клиент"
    if username:
        return f"[@{username}]({telegram_id})"
    else:
        return f"[Клиент]({telegram_id})"
