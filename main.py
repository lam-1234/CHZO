import telebot
import psycopg2
import os
import time

# ==========================================
# ВАШИ НАСТРОЙКИ (УЖЕ ЗАПОЛНЕНЫ ВЕРНО)
BOT_TOKEN = os.getenv('BOT_TOKEN') 
DATABASE_URL = os.getenv('DATABASE_URL') # Берется из Infrlo
ADMIN_ID = 529969683 
ALLOWED_CHAT_ID = -1004490896933 
ALLOWED_TOPIC_ID = 9 
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)

# --- ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ (POSTGRESQL) ---
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # Для облачной базы ID должен быть BIGINT
    cursor.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id BIGINT PRIMARY KEY,
        char_name TEXT DEFAULT 'Безымянный',
        faction TEXT DEFAULT 'Одиночка',
        reputation INTEGER DEFAULT 0,
        uah INTEGER DEFAULT 0,
        rub INTEGER DEFAULT 0,
        usd INTEGER DEFAULT 0,
        eur INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_db()

def get_player(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # В постгресе вместо ? используются %s
    cursor.execute("SELECT * FROM players WHERE user_id = %s", (user_id,))
    player = cursor.fetchone()
    if not player:
        cursor.execute("INSERT INTO players (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM players WHERE user_id = %s", (user_id,))
        player = cursor.fetchone()
    conn.close()
    return player

# --- ПРОВЕРКА НА ЧАТ И ТЕМУ ---
def is_allowed(message):
    if message.chat.type == 'private' and message.chat.id == ADMIN_ID:
        return True
    if message.chat.id == ALLOWED_CHAT_ID and message.message_thread_id == ALLOWED_TOPIC_ID:
        return True
    return False

# --- КОМАНДЫ ДЛЯ ИГРОКОВ ---

@bot.message_handler(commands=['start', 'help'], func=is_allowed)
def send_welcome(message):
    text = (
        "☢️ <b>Терминал ЧЗО активирован.</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/profile - Открыть личное дело (посмотреть баланс)\n"
        "/pay [сумма] [валюта] - Перевести деньги (в ответ на сообщение игрока)\n"
        "Валюты: uah (гривна), rub (рубль), usd (доллар), eur (евро).\n\n"
        "⚠️ <i>Конвертация валют проводится только через Администрацию (НИИЧАЗ).</i>"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['profile'], func=is_allowed)
def show_profile(message):
    user_id = message.from_user.id
    p = get_player(user_id)
    
    text = (
        f"📁 <b>Личное дело сталкера</b>\n\n"
        f"👤 <b>Имя:</b> {p[1]}\n"
        f"🛡 <b>Группировка:</b> {p[2]}\n"
        f"⭐ <b>Репутация:</b> {p[3]}\n\n"
        f"💰 <b>Баланс:</b>\n"
        f"🇺🇦 Гривна: {p[4]}\n"
        f"🇷🇺 Рубль: {p[5]}\n"
        f"🇺🇸 Доллар: {p[6]}\n"
        f"🇪🇺 Евро: {p[7]}"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['pay'], func=is_allowed)
def transfer_money(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ошибка. Чтобы перевести деньги, ответьте (Reply) на сообщение игрока.")
        return

    sender_id = message.from_user.id
    receiver_id = message.reply_to_message.from_user.id

    if sender_id == receiver_id:
        bot.reply_to(message, "❌ Вы не можете перевести деньги самому себе.")
        return

    try:
        args = message.text.split()[1:]
        amount = int(args[0])
        currency = args[1].lower()
    except:
        bot.reply_to(message, "❌ Формат: <code>/pay [сумма] [валюта]</code>\nПример: <code>/pay 500 rub</code>", parse_mode='HTML')
        return

    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше нуля.")
        return

    curr_map = {'uah': 4, 'rub': 5, 'usd': 6, 'eur': 7}
    if currency not in curr_map:
        bot.reply_to(message, "❌ Доступны валюты: uah, rub, usd, eur")
        return

    col_index = curr_map[currency]
    sender = get_player(sender_id)

    if sender[col_index] < amount:
        bot.reply_to(message, "❌ Недостаточно средств.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE players SET {currency} = {currency} - %s WHERE user_id = %s", (amount, sender_id))
        cursor.execute(f"UPDATE players SET {currency} = {currency} + %s WHERE user_id = %s", (amount, receiver_id))
        conn.commit()
        conn.close()

        receiver_name = get_player(receiver_id)[1]
        bot.reply_to(message, f"✅ Перевод успешен!\nВы перевели <b>{amount} {currency.upper()}</b> сталкеру <b>{receiver_name}</b>.", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка базы данных.")

# --- КОМАНДЫ АДМИНИСТРАТОРА ---

def is_admin(message):
    return message.from_user.id == ADMIN_ID

@bot.message_handler(commands=['setname'], func=is_allowed)
def admin_setname(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        name = message.text.split(maxsplit=1)[1]
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET char_name = %s WHERE user_id = %s", (name, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Имя изменено на <b>{name}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/setname Имя Фамилия</code>", parse_mode='HTML')

@bot.message_handler(commands=['setfaction'], func=is_allowed)
def admin_setfaction(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        faction = message.text.split(maxsplit=1)[1]
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET faction = %s WHERE user_id = %s", (faction, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Группировка изменена на <b>{faction}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/setfaction Название</code>", parse_mode='HTML')

@bot.message_handler(commands=['addmoney'], func=is_allowed)
def admin_addmoney(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        args = message.text.split()[1:]
        amount = int(args[0])
        currency = args[1].lower()
        curr_map = {'uah': 4, 'rub': 5, 'usd': 6, 'eur': 7}
        if currency not in curr_map:
            return bot.reply_to(message, "❌ Доступны валюты: uah, rub, usd, eur")
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE players SET {currency} = {currency} + %s WHERE user_id = %s", (amount, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Начислено <b>{amount} {currency.upper()}</b> игроку.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/addmoney [сумма] [валюта]</code>", parse_mode='HTML')

@bot.message_handler(commands=['addrep'], func=is_allowed)
def admin_addrep(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        amount = int(message.text.split()[1])
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET reputation = reputation + %s WHERE user_id = %s", (amount, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Репутация изменена на <b>{amount}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/addrep [число]</code>", parse_mode='HTML')

# --- НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ СМЕРТЬЮ ---

@bot.message_handler(commands=['resetplayer'], func=is_allowed)
def admin_resetplayer(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Обнуляем всё и ставим статус "Мертв"
        cursor.execute("""UPDATE players SET 
            char_name = 'Труп', 
            faction = 'Мертв', 
            reputation = 0, 
            uah = 0, rub = 0, usd = 0, eur = 0 
            WHERE user_id = %s""", (target_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "💀 Персонаж убит. Все данные и деньги обнулены. Игрок может начать заново.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Ошибка при обнулении.")

@bot.message_handler(commands=['deleteplayer'], func=is_allowed)
def admin_deleteplayer(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        target_id = message.reply_to_message.from_user.id
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Полностью удаляем запись из базы
        cursor.execute("DELETE FROM players WHERE user_id = %s", (target_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "🗑 Запись игрока полностью удалена из базы данных НИИЧАЗ.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Ошибка при удалении.")

# --- АВТОПЕРЕЗАПУСК ПРИ СБОЕ СЕТИ ---
print("Терминал ЧЗО запущен и работает...")
while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Сбой сети: {e}. Перезапуск через 5 секунд...")
        time.sleep(5)
