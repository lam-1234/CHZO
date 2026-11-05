import telebot
import psycopg2
import os
import time
from telebot import types
from flask import Flask
import threading

# ==========================================
# ВАШИ НАСТРОЙКИ
BOT_TOKEN = os.getenv('BOT_TOKEN') 
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 5299699683 # ТВОЙ ID
ALLOWED_CHAT_ID = -1004490896933 # ID ГРУППЫ
ALLOWED_TOPIC_ID = 9 # ID ТЕМЫ
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)

# --- БАЗА ДАННЫХ ---
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cursor:
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
                rub INTEGER DEFAULT 4000,
                usd INTEGER DEFAULT 0,
                eur INTEGER DEFAULT 0,
                tg_username TEXT
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                trans_id SERIAL PRIMARY KEY,
                sender_id INTEGER,
                receiver_id INTEGER,
                amount INTEGER,
                currency TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()

def get_active_player(user_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT active_char_id FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or not user[0]: return None
            cursor.execute("SELECT * FROM characters WHERE char_id = %s", (user[0],))
            return cursor.fetchone()

def get_all_chars(user_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT char_id, char_name FROM characters WHERE user_id = %s", (user_id,))
            return cursor.fetchall()

def get_char_by_name(name):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM characters WHERE LOWER(char_name) = LOWER(%s)", (name,))
            return cursor.fetchall()

def get_char_by_id(char_id):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM characters WHERE char_id = %s", (char_id,))
            return cursor.fetchone()

def update_char(char_id, field, value):
    allowed_fields = ['faction', 'reputation', 'uah', 'rub', 'usd', 'eur']
    if field not in allowed_fields: return False
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"UPDATE characters SET {field} = {field} + %s WHERE char_id = %s", (value, char_id))
            conn.commit()
            return True

# Функция автообновления ника
def update_user_username(user_id, new_username):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE characters SET tg_username = %s WHERE user_id = %s", (new_username, user_id))
            conn.commit()

def log_transaction(sender_id, receiver_id, amount, currency):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO transactions (sender_id, receiver_id, amount, currency) VALUES (%s, %s, %s, %s)", (sender_id, receiver_id, amount, currency))
            conn.commit()

def get_recent_transactions(limit=10):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.timestamp, s.char_name, s.tg_username, r.char_name, r.tg_username, t.amount, t.currency 
                FROM transactions t
                LEFT JOIN characters s ON t.sender_id = s.char_id
                LEFT JOIN characters r ON t.receiver_id = r.char_id
                ORDER BY t.timestamp DESC LIMIT %s
            """, (limit,))
            return cursor.fetchall()

init_db()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- ЛОГИКА БОТА ---
def is_allowed(message):
    if message.chat.type == 'private' and message.chat.id == ADMIN_ID: return True
    if message.chat.id == ALLOWED_CHAT_ID and message.message_thread_id == ALLOWED_TOPIC_ID: return True
    return False

def is_admin(message): return message.from_user.id == ADMIN_ID

# --- КОМАНДЫ ИГРОКОВ ---

@bot.message_handler(commands=['start', 'help'], func=is_allowed)
def send_welcome(message):
    text = (
        "☢️ <b>Терминал ЧЗО активирован.</b>\n\n"
        "<b>Команды:</b>\n"
        "/create - Создать персонажа (баланс 4000 руб.)\n"
        "/mychars - Список ваших персонажей\n"
        "/profile - Посмотреть карточку\n"
        "/pay [сумма] [валюта] [Имя] - Перевести деньги\n"
        "/deletechar - Удалить текущего персонажа"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['create'], func=is_allowed)
def create_char(message):
    msg = bot.reply_to(message, "Введите имя вашего нового сталкера (или напишите <code>Отмена</code>):", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_create_char)

def process_create_char(message):
    if message.text.lower() == 'отмена': return bot.reply_to(message, "Создание отменено.")
    if len(message.text) > 30: return bot.reply_to(message, "Имя слишком длинное (макс 30 символов).")
    
    user_id = message.from_user.id
    name = message.text
    tg_username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO characters (user_id, char_name, tg_username) VALUES (%s, %s, %s) RETURNING char_id", (user_id, name, tg_username))
            new_char_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO users (user_id, active_char_id) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET active_char_id = %s", (user_id, new_char_id, new_char_id))
            conn.commit()
    bot.reply_to(message, f"✅ Персонаж <b>{name}</b> создан! Выдано 4000 руб.", parse_mode='HTML')

@bot.message_handler(commands=['mychars'], func=is_allowed)
def list_chars(message):
    chars = get_all_chars(message.from_user.id)
    if not chars: return bot.reply_to(message, "У вас нет персонажей. Напишите /create")
    
    active = get_active_player(message.from_user.id)
    active_id = active[0] if active else None
    
    markup = types.InlineKeyboardMarkup()
    for c in chars:
        prefix = "✅ " if c[0] == active_id else "👤 "
        markup.add(types.InlineKeyboardButton(f"{prefix}{c[1]}", callback_data=f"switch_{c[0]}"))
    bot.reply_to(message, "Выберите персонажа:", reply_markup=markup)

@bot.message_handler(commands=['profile'], func=is_allowed)
def show_profile(message):
    current_tag = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    update_user_username(message.from_user.id, current_tag)

    p = get_active_player(message.from_user.id)
    if not p: return bot.reply_to(message, "Нет активного персонажа. /create")
    
    text = (
        f"📁 <b>Личное дело</b>\n\n"
        f"👤 <b>Имя:</b> {p[2]}\n"
        f"🛡 <b>Группировка:</b> {p[3]}\n"
        f"⭐ <b>Репутация:</b> {p[4]}\n\n"
        f"💰 <b>Баланс:</b>\n"
        f"🇺🇦 {p[5]} | 🇷🇺 {p[6]}\n"
        f"🇺🇸 {p[7]} | 🇪🇺 {p[8]}"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['pay'], func=is_allowed)
def transfer_money(message):
    current_tag = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    update_user_username(message.from_user.id, current_tag)

    sender = get_active_player(message.from_user.id)
    if not sender: return bot.reply_to(message, "Нет активного персонажа.")

    receiver = None
    try:
        args = message.text.split()
        if message.reply_to_message:
            receiver = get_active_player(message.reply_to_message.from_user.id)
            amount, currency = int(args[1]), args[2].lower()
        else:
            amount, currency = int(args[1]), args[2].lower()
            target_name = message.text.split(maxsplit=3)[3]
            found = get_char_by_name(target_name)
            
            if not found: return bot.reply_to(message, "❌ Персонаж не найден.")
            if len(found) > 1:
                markup = types.InlineKeyboardMarkup()
                for c in found:
                    btn_text = f"{c[2]} ({c[9]})" if c[9] else c[2]
                    markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"pp_{c[0]}_{amount}_{currency}"))
                return bot.reply_to(message, "Найдено несколько. Выберите нужного (по нику владельца):", reply_markup=markup)
            receiver = found[0]
    except:
        return bot.reply_to(message, "Формат: /pay [сумма] [валюта] [Имя]")

    process_transfer(message, sender, receiver, amount, currency)

def process_transfer(message, sender, receiver, amount, currency):
    if amount <= 0 or currency not in {'uah', 'rub', 'usd', 'eur'}: 
        return bot.reply_to(message, "Ошибка в сумме или валюте.")
    if not receiver: return bot.reply_to(message, "У получателя нет персонажа.")
    if sender[0] == receiver[0]: return bot.reply_to(message, "Себе переводить нельзя.")

    curr_idx = {'uah': 5, 'rub': 6, 'usd': 7, 'eur': 8}[currency]
    if sender[curr_idx] < amount: return bot.reply_to(message, "❌ Недостаточно средств.")

    update_char(sender[0], currency, -amount)
    update_char(receiver[0], currency, amount)
    log_transaction(sender[0], receiver[0], amount, currency)
    
    bot.reply_to(message, f"✅ Переведено <b>{amount} {currency.upper()}</b> игроку <b>{receiver[2]}</b>.", parse_mode='HTML')

# --- КОМАНДЫ АДМИНИСТРАТОРА ---

@bot.message_handler(commands=['history'], func=is_allowed)
def show_history(message):
    if not is_admin(message): return
    trans = get_recent_transactions(10)
    if not trans: return bot.reply_to(message, "Транзакций пока нет.")
    
    text = "📊 <b>Последние 10 транзакций:</b>\n\n"
    for t in trans:
        time_str = t[0].strftime("%H:%M")
        s_name = f"{t[1]} ({t[2]})" if t[2] else t[1]
        r_name = f"{t[3]} ({t[4]})" if t[4] else t[3]
        text += f"🕒 {time_str} | {s_name} ➡️ {r_name} | {t[5]} {t[6].upper()}\n"
    bot.reply_to(message, text, parse_mode='HTML')

def admin_action_factory(action_type):
    def handler(message):
        if not is_admin(message): return
        if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
        chars = get_all_chars(message.reply_to_message.from_user.id)
        if not chars: return bot.reply_to(message, "У игрока нет персонажей.")
        try:
            args = message.text.split()[1:]
            val = int(args[0]) if action_type != 'faction' else ' '.join(args)
            curr = args[1].lower() if action_type == 'money' else None
        except: return bot.reply_to(message, "Ошибка в формате команды.")

        if len(chars) == 1:
            field = 'faction' if action_type == 'faction' else ('reputation' if action_type == 'rep' else curr)
            update_char(chars[0][0], field, val)
            return bot.reply_to(message, f"✅ Успешно применено к <b>{chars[0][1]}</b>.", parse_mode='HTML')
        
        markup = types.InlineKeyboardMarkup()
        for c in chars:
            cb_data = f"{action_type}_{c[0]}_{val}" + (f"_{curr}" if curr else "")
            markup.add(types.InlineKeyboardButton(c[1], callback_data=cb_data))
        bot.reply_to(message, "Выберите персонажа:", reply_markup=markup)
    return handler

bot.message_handler(commands=['addmoney'], func=is_allowed)(admin_action_factory('money'))
bot.message_handler(commands=['addrep'], func=is_allowed)(admin_action_factory('rep'))
bot.message_handler(commands=['setfaction'], func=is_allowed)(admin_action_factory('faction'))

@bot.callback_query_handler(func=lambda call: True)
def all_callbacks(call):
    data = call.data.split('_')
    action = data[0]
    
    if action == 'switch':
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET active_char_id = %s WHERE user_id = %s", (data[1], call.from_user.id))
                conn.commit()
        bot.edit_message_text(f"✅ Персонаж выбран.", call.message.chat.id, call.message.message_id)
        
    elif action == 'delchar':
        if data[1] == 'cancel': return bot.edit_message_text("Отменено.", call.message.chat.id, call.message.message_id)
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM characters WHERE char_id = %s", (data[1],))
                cursor.execute("UPDATE users SET active_char_id = NULL WHERE user_id = %s", (call.from_user.id,))
                conn.commit()
        bot.edit_message_text("🗑 Удален.", call.message.chat.id, call.message.message_id)
        
    elif action in ['pp', 'am', 'ar', 'sf']:
        char_id = int(data[1])
        if action == 'pp':
            sender = get_active_player(call.from_user.id)
            receiver = get_char_by_id(char_id)
            amount = int(data[2])
            currency = data[3]
            curr_idx = {'uah': 5, 'rub': 6, 'usd': 7, 'eur': 8}[currency]
            if sender[curr_idx] >= amount:
                update_char(sender[0], currency, -amount)
                update_char(receiver[0], currency, amount)
                log_transaction(sender[0], receiver[0], amount, currency)
                bot.edit_message_text(f"✅ Переведено {amount} {currency.upper()} игроку {receiver[2]}.", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Недостаточно средств.")
        else:
            field = 'faction' if action == 'sf' else ('reputation' if action == 'ar' else data[3])
            val = data[2] if action != 'sf' else data[2]
            if action == 'am': val = int(val)
            if action == 'ar': val = int(val)
            update_char(char_id, field, val)
            bot.edit_message_text("✅ Начислено.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['deletechar'], func=is_allowed)
def delete_char(message):
    p = get_active_player(message.from_user.id)
    if not p: return bot.reply_to(message, "Нет активного персонажа.")
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("💀 Удалить", callback_data=f"delchar_{p[0]}"),
        types.InlineKeyboardButton("Отмена", callback_data="delchar_cancel")
    )
    bot.reply_to(message, f"Удалить <b>{p[2]}</b>?", reply_markup=markup, parse_mode='HTML')

# --- ЗАПУСК ---
if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Сбой: {e}")
            time.sleep(5)
