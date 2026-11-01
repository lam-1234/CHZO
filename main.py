import telebot
import psycopg2
import os
import time
from telebot import types

# ==========================================
# ВАШИ НАСТРОЙКИ
BOT_TOKEN = os.getenv('BOT_TOKEN') 
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 5299699683 
ALLOWED_CHAT_ID = -1004490896933 
ALLOWED_TOPIC_ID = 9 
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        active_char_id INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS characters (
        char_id SERIAL PRIMARY KEY,
        user_id BIGINT,
        char_name TEXT,
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

def get_active_player(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT active_char_id FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or not user[0]:
        conn.close()
        return None
    cursor.execute("SELECT * FROM characters WHERE char_id = %s", (user[0],))
    player = cursor.fetchone()
    conn.close()
    return player

def get_all_chars(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT char_id, char_name FROM characters WHERE user_id = %s", (user_id,))
    chars = cursor.fetchall()
    conn.close()
    return chars

def is_allowed(message):
    if message.chat.type == 'private' and message.chat.id == ADMIN_ID:
        return True
    if message.chat.id == ALLOWED_CHAT_ID and message.message_thread_id == ALLOWED_TOPIC_ID:
        return True
    return False

# --- КОМАНДЫ ИГРОКОВ ---

@bot.message_handler(commands=['start', 'help'], func=is_allowed)
def send_welcome(message):
    text = (
        "☢️ <b>Терминал ЧЗО активирован.</b>\n\n"
        "<b>Команды:</b>\n"
        "/create - Создать персонажа\n"
        "/mychars - Список ваших персонажей (переключение)\n"
        "/profile - Посмотреть карточку\n"
        "/pay [сумма] [валюта] - Перевести деньги\n"
        "/deletechar - Удалить текущего персонажа"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['create'], func=is_allowed)
def create_char(message):
    msg = bot.reply_to(message, "Введите имя вашего нового сталкера (или напишите 'Отмена'):")
    bot.register_next_step_handler(msg, process_create_char)

def process_create_char(message):
    if message.text.lower() == 'отмена':
        return bot.reply_to(message, "Создание отменено.")
    if len(message.text) > 30:
        return bot.reply_to(message, "Имя слишком длинное (макс 30 символов). Попробуйте снова /create")

    name = message.text
    user_id = message.from_user.id

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO characters (user_id, char_name) VALUES (%s, %s) RETURNING char_id", (user_id, name))
        new_char_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO users (user_id, active_char_id) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET active_char_id = %s", (user_id, new_char_id, new_char_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Персонаж <b>{name}</b> успешно создан и выбран активным!", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "Ошибка базы данных при создании.")

@bot.message_handler(commands=['mychars'], func=is_allowed)
def list_chars(message):
    user_id = message.from_user.id
    chars = get_all_chars(user_id)
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT active_char_id FROM users WHERE user_id = %s", (user_id,))
    active = cursor.fetchone()
    active_id = active[0] if active else None
    conn.close()

    if not chars:
        return bot.reply_to(message, "У вас пока нет персонажей. Напишите /create")

    markup = types.InlineKeyboardMarkup()
    for c in chars:
        prefix = "✅ " if c[0] == active_id else "👤 "
        markup.add(types.InlineKeyboardButton(f"{prefix}{c[1]}", callback_data=f"switch_{c[0]}"))
    
    bot.reply_to(message, "Выберите персонажа, от лица которого хотите играть:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('switch_'))
def switch_character(call):
    char_id = int(call.data.split('_')[1])
    user_id = call.from_user.id
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT char_name FROM characters WHERE char_id = %s AND user_id = %s", (char_id, user_id))
    char = cursor.fetchone()
    if char:
        cursor.execute("UPDATE users SET active_char_id = %s WHERE user_id = %s", (char_id, user_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"Вы переключились на {char[0]}")
        bot.edit_message_text(f"Активный персонаж: <b>{char[0]}</b>", call.message.chat.id, call.message.message_id, parse_mode='HTML')
    else:
        bot.answer_callback_query(call.id, "Ошибка: персонаж не найден.")
    conn.close()

@bot.message_handler(commands=['deletechar'], func=is_allowed)
def delete_char(message):
    p = get_active_player(message.from_user.id)
    if not p:
        return bot.reply_to(message, "У вас нет активного персонажа для удаления.")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💀 Да, удалить", callback_data=f"delchar_{p[0]}"))
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="delchar_cancel"))
    bot.reply_to(message, f"Вы уверены, что хотите <b>НАВСЕГДА</b> удалить персонажа <b>{p[2]}</b>?", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('delchar_'))
def process_delete_char(call):
    if call.data == "delchar_cancel":
        return bot.edit_message_text("Удаление отменено.", call.message.chat.id, call.message.message_id)
    char_id = int(call.data.split('_')[1])
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM characters WHERE char_id = %s AND user_id = %s", (char_id, call.from_user.id))
    cursor.execute("UPDATE users SET active_char_id = NULL WHERE user_id = %s", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.edit_message_text("🗑 Персонаж удален. Вы можете создать нового через /create.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['profile'], func=is_allowed)
def show_profile(message):
    p = get_active_player(message.from_user.id)
    if not p:
        return bot.reply_to(message, "У вас нет активного персонажа. Создайте его через /create")
    text = (
        f"📁 <b>Личное дело сталкера</b>\n\n"
        f"👤 <b>Имя:</b> {p[2]}\n"
        f"🛡 <b>Группировка:</b> {p[3]}\n"
        f"⭐ <b>Репутация:</b> {p[4]}\n\n"
        f"💰 <b>Баланс:</b>\n"
        f"🇺🇦 Гривна: {p[5]}\n"
        f"🇷🇺 Рубль: {p[6]}\n"
        f"🇺🇸 Доллар: {p[7]}\n"
        f"🇪🇺 Евро: {p[8]}"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['pay'], func=is_allowed)
def transfer_money(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "❌ Ответьте (Reply) на сообщение игрока, которому хотите перевести деньги.")
    sender = get_active_player(message.from_user.id)
    receiver = get_active_player(message.reply_to_message.from_user.id)
    if not sender: return bot.reply_to(message, "У вас нет активного персонажа.")
    if not receiver: return bot.reply_to(message, "У получателя нет активного персонажа.")

    try:
        args = message.text.split()[1:]
        amount = int(args[0])
        currency = args[1].lower()
    except:
        return bot.reply_to(message, "Формат: <code>/pay [сумма] [валюта]</code>", parse_mode='HTML')

    if amount <= 0: return bot.reply_to(message, "Сумма должна быть больше нуля.")
    curr_map = {'uah': 5, 'rub': 6, 'usd': 7, 'eur': 8}
    if currency not in curr_map: return bot.reply_to(message, "Валюты: uah, rub, usd, eur")

    if sender[curr_map[currency]] < amount:
        return bot.reply_to(message, "❌ Недостаточно средств.")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE characters SET {currency} = {currency} - %s WHERE char_id = %s", (amount, sender[0]))
        cursor.execute(f"UPDATE characters SET {currency} = {currency} + %s WHERE char_id = %s", (amount, receiver[0]))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Вы перевели <b>{amount} {currency.upper()}</b> сталкеру <b>{receiver[2]}</b>.", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "Ошибка базы данных.")

# --- КОМАНДЫ АДМИНИСТРАТОРА (С ВЫБОРОМ ПЕРСОНАЖА) ---

def is_admin(message): return message.from_user.id == ADMIN_ID

@bot.message_handler(commands=['setfaction'], func=is_allowed)
def admin_setfaction(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    chars = get_all_chars(message.reply_to_message.from_user.id)
    if not chars: return bot.reply_to(message, "У этого игрока нет персонажей.")
    try: faction = message.text.split(maxsplit=1)[1]
    except: return bot.reply_to(message, "Формат: <code>/setfaction Название</code>", parse_mode='HTML')

    if len(chars) == 1:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE characters SET faction = %s WHERE char_id = %s", (faction, chars[0][0]))
        conn.commit()
        conn.close()
        return bot.reply_to(message, f"✅ Группировка <b>{faction}</b> выдана персонажу <b>{chars[0][1]}</b>.", parse_mode='HTML')
    else:
        markup = types.InlineKeyboardMarkup()
        for c in chars:
            markup.add(types.InlineKeyboardButton(c[1], callback_data=f"sf_{c[0]}_{faction}"))
        bot.reply_to(message, f"Выберите, кому выдать фракцию <b>{faction}</b>:", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['addmoney'], func=is_allowed)
def admin_addmoney(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    chars = get_all_chars(message.reply_to_message.from_user.id)
    if not chars: return bot.reply_to(message, "У этого игрока нет персонажей.")
    try:
        args = message.text.split()[1:]
        amount = int(args[0])
        currency = args[1].lower()
        if currency not in {'uah', 'rub', 'usd', 'eur'}: raise Exception
    except:
        return bot.reply_to(message, "Формат: <code>/addmoney [сумма] [валюта]</code>", parse_mode='HTML')

    if len(chars) == 1:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE characters SET {currency} = {currency} + %s WHERE char_id = %s", (amount, chars[0][0]))
        conn.commit()
        conn.close()
        return bot.reply_to(message, f"✅ Начислено <b>{amount} {currency.upper()}</b> персонажу <b>{chars[0][1]}</b>.", parse_mode='HTML')
    else:
        markup = types.InlineKeyboardMarkup()
        for c in chars:
            markup.add(types.InlineKeyboardButton(c[1], callback_data=f"am_{c[0]}_{amount}_{currency}"))
        bot.reply_to(message, f"Кому начислить <b>{amount} {currency.upper()}</b>?", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['addrep'], func=is_allowed)
def admin_addrep(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    chars = get_all_chars(message.reply_to_message.from_user.id)
    if not chars: return bot.reply_to(message, "У этого игрока нет персонажей.")
    try: amount = int(message.text.split()[1])
    except: return bot.reply_to(message, "Формат: <code>/addrep [число]</code>", parse_mode='HTML')

    if len(chars) == 1:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE characters SET reputation = reputation + %s WHERE char_id = %s", (amount, chars[0][0]))
        conn.commit()
        conn.close()
        return bot.reply_to(message, f"✅ Репутация <b>{amount}</b> выдана персонажу <b>{chars[0][1]}</b>.", parse_mode='HTML')
    else:
        markup = types.InlineKeyboardMarkup()
        for c in chars:
            markup.add(types.InlineKeyboardButton(c[1], callback_data=f"ar_{c[0]}_{amount}"))
        bot.reply_to(message, f"Кому начислить репутацию <b>{amount}</b>?", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('am_') or call.data.startswith('ar_') or call.data.startswith('sf_'))
def handle_admin_action(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "Нет прав!")
    data = call.data.split('_')
    action, char_id = data[0], int(data[1])
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        if action == 'am':
            amount, currency = int(data[2]), data[3]
            cursor.execute(f"UPDATE characters SET {currency} = {currency} + %s WHERE char_id = %s", (amount, char_id))
            msg_text = f"✅ Начислено <b>{amount} {currency.upper()}</b>."
        elif action == 'ar':
            amount = int(data[2])
            cursor.execute("UPDATE characters SET reputation = reputation + %s WHERE char_id = %s", (amount, char_id))
            msg_text = f"✅ Репутация изменена на <b>{amount}</b>."
        elif action == 'sf':
            faction = data[2]
            cursor.execute("UPDATE characters SET faction = %s WHERE char_id = %s", (faction, char_id))
            msg_text = f"✅ Группировка изменена на <b>{faction}</b>."
        conn.commit()
        conn.close()
        bot.edit_message_text(f"{msg_text}\nДействие применено к выбранному персонажу.", call.message.chat.id, call.message.message_id, parse_mode='HTML')
    except Exception as e:
        bot.answer_callback_query(call.id, "Ошибка при выполнении.")

# --- АВТОПЕРЕЗАПУСК ---
print("Терминал ЧЗО запущен...")
while True:
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        time.sleep(5)
