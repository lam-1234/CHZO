import telebot
import sqlite3
import os

# ==========================================
# СЮДА ВСТАВЬТЕ ВАШИ ДАННЫЕ:
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 5299699683  # ВСТАВЬТЕ_СЮДА_ВАШ_ID_ЦИФРАМИ (без кавычек)
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)


# Создание базы данных (не трогайте этот блок)
def init_db():
    conn = sqlite3.connect('stalker_rp.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
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
    conn = sqlite3.connect('stalker_rp.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    player = cursor.fetchone()
    if not player:
        cursor.execute("INSERT INTO players (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        player = cursor.fetchone()
    conn.close()
    return player


# --- КОМАНДЫ ДЛЯ ИГРОКОВ ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "☢️ <b>Терминал ЧЗО активирован.</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/profile - Открыть личное дело (посмотреть баланс)\n"
        "/pay [сумма] [валюта] - Перевести деньги (в ответ на сообщение игрока)\n"
        "Валюты для перевода: uah (гривна), rub (рубль), usd (доллар), eur (евро).\n\n"
        "⚠️ <i>Конвертация валют проводится только через Администрацию.</i>"
    )
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(commands=['profile'])
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


@bot.message_handler(commands=['pay'])
def transfer_money(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ошибка. Чтобы перевести деньги, ответьте (Reply) на сообщение нужного игрока.")
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
        bot.reply_to(message,
                     "❌ Неверный формат.\nИспользуйте: <code>/pay [сумма] [валюта]</code>\nПример: <code>/pay 500 rub</code>",
                     parse_mode='HTML')
        return

    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше нуля.")
        return

    curr_map = {'uah': 4, 'rub': 5, 'usd': 6, 'eur': 7}
    if currency not in curr_map:
        bot.reply_to(message, "❌ Неизвестная валюта. Доступны: uah, rub, usd, eur")
        return

    col_index = curr_map[currency]
    sender = get_player(sender_id)

    if sender[col_index] < amount:
        bot.reply_to(message, "❌ Недостаточно средств на счету.")
        return

    try:
        conn = sqlite3.connect('stalker_rp.db')
        cursor = conn.cursor()
        cursor.execute(f"UPDATE players SET {currency} = {currency} - ? WHERE user_id = ?", (amount, sender_id))
        cursor.execute(f"UPDATE players SET {currency} = {currency} + ? WHERE user_id = ?", (amount, receiver_id))
        conn.commit()
        conn.close()

        receiver_name = get_player(receiver_id)[1]
        bot.reply_to(message,
                     f"✅ Перевод успешен!\nВы перевели <b>{amount} {currency.upper()}</b> сталкеру <b>{receiver_name}</b>.",
                     parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка базы данных при переводе.")


# --- КОМАНДЫ АДМИНИСТРАТОРА (ТОЛЬКО ДЛЯ ВАС) ---

def is_admin(message):
    return message.from_user.id == ADMIN_ID


@bot.message_handler(commands=['setname'])
def admin_setname(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        name = message.text.split(maxsplit=1)[1]
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = sqlite3.connect('stalker_rp.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET char_name = ? WHERE user_id = ?", (name, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Имя изменено на <b>{name}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/setname Имя Фамилия</code> (в ответ на сообщение)", parse_mode='HTML')


@bot.message_handler(commands=['setfaction'])
def admin_setfaction(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        faction = message.text.split(maxsplit=1)[1]
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = sqlite3.connect('stalker_rp.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET faction = ? WHERE user_id = ?", (faction, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Группировка изменена на <b>{faction}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/setfaction Название</code> (в ответ на сообщение)", parse_mode='HTML')


@bot.message_handler(commands=['addmoney'])
def admin_addmoney(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        args = message.text.split()[1:]
        amount = int(args[0])
        currency = args[1].lower()
        curr_map = {'uah': 4, 'rub': 5, 'usd': 6, 'eur': 7}
        if currency not in curr_map:
            return bot.reply_to(message, "❌ Неизвестная валюта. Доступны: uah, rub, usd, eur")
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = sqlite3.connect('stalker_rp.db')
        cursor = conn.cursor()
        cursor.execute(f"UPDATE players SET {currency} = {currency} + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Начислено <b>{amount} {currency.upper()}</b> игроку.", parse_mode='HTML')
    except:
        bot.reply_to(message,
                     "Формат: <code>/addmoney [сумма] [валюта]</code>\nПример: <code>/addmoney 1000 usd</code>",
                     parse_mode='HTML')


@bot.message_handler(commands=['addrep'])
def admin_addrep(message):
    if not is_admin(message): return
    if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение игрока.")
    try:
        amount = int(message.text.split()[1])
        target_id = message.reply_to_message.from_user.id
        get_player(target_id)
        conn = sqlite3.connect('stalker_rp.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET reputation = reputation + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Репутация изменена на <b>{amount}</b>.", parse_mode='HTML')
    except:
        bot.reply_to(message, "Формат: <code>/addrep [число]</code>", parse_mode='HTML')


print("Терминал ЧЗО запущен и работает...")
bot.polling(none_stop=True)