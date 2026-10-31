import telebot
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def spy_on_messages(message):
    # Этот блок будет печатать данные о любом сообщении в логи Infrlo
    print("====================================")
    print(f"ТЕКСТ: {message.text}")
    print(f"ID ГРУППЫ (Chat ID): {message.chat.id}")
    print(f"ID ТЕМЫ (Topic ID): {message.message_thread_id}")
    print(f"ВАШ ID (User ID): {message.from_user.id}")
    print("====================================")
    
    # Бот ответит вам, чтобы вы поняли, что он работает
    bot.reply_to(message, "Я тебя вижу! Иди смотри логи в Infrlo.")

print("Шпион запущен...")
bot.polling(none_stop=True)
