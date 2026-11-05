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
if name == 'main':
    threading.Thread(target=run_flask).start()
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20, drop_pending_updates=True)
        except Exception as e:
            print(f"Сбой: {e}")
            time.sleep(5)
