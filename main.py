        bot.send_message(message.chat.id, "🔄 Начинаю рассылку...")
        print(f"📢 Админ {message.from_user.id} запустил рассылку: {broadcast_text}")
        send_broadcast(message.from_user.id, broadcast_text)
    else:
        bot.send_message(message.chat.id, "❌ Рассылка отменена")
        admin_menu(message)

def send_broadcast(admin_id, text):
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    users = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    total = len(users)
    
    progress_msg = bot.send_message(admin_id, f"📤 Рассылка начата...\nВсего пользователей: {total}\n\nОбработано: 0/{total}")
    
    for i, user in enumerate(users):
        # Пропускаем забаненных пользователей
        if is_banned(user[0]):
            continue
            
        try:
            bot.send_message(user[0], f"📢 Рассылка:\n\n{text}")
            success += 1
            time.sleep(0.1)
        except:
            failed += 1
        
        if i % 10 == 0:
            try:
                bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=progress_msg.message_id,
                    text=f"📤 Рассылка в процессе...\nВсего пользователей: {total}\n\nОбработано: {i+1}/{total}\n✅ Успешно: {success}\n❌ Ошибок: {failed}"
                )
            except:
                pass
    
    bot.edit_message_text(
        chat_id=admin_id,
        message_id=progress_msg.message_id,
        text=f"✅ Рассылка завершена!\n\nВсего пользователей: {total}\n✅ Успешно: {success}\n❌ Не удалось: {failed}"
    )
    print(f"✅ Рассылка завершена. Успешно: {success}, Ошибок: {failed}")
    admin_menu(bot.send_message(admin_id, "Возвращаю в админ-меню..."))

# Кнопка Назад
@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main(message):
    start(message)

@bot.message_handler(func=lambda m: m.text in ['🆘 Мне нужна поддержка', '💬 Я хочу поговорить'])
def start_chat(message):
    user_id = message.from_user.id
    
    # Проверяем бан
    if is_banned(user_id):
        bot.send_message(user_id, "❌ Вы заблокированы в этом боте и не можете использовать его функции.")
        return
    
    user_name = message.from_user.first_name
    
    if message.text == '🆘 Мне нужна поддержка':
        bot.send_message(user_id, "💬 Чат с поддержкой начат! Пишите сообщения...")
        save_message_stat(user_id, "support_request")
        bot.send_message(
            SUPPORT_CHAT_ID,
            f"🆘 ПОЛЬЗОВАТЕЛЬ НУЖДАЕТСЯ В ПОДДЕРЖКЕ!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"📝 Статус: Ожидает помощи поддержки"
        )
        print(f"🆘 Пользователь {user_id} запросил поддержку")
        
    else:
        bot.send_message(user_id, "💬 Режим общения начат! Пишите сообщения...")
        save_message_stat(user_id, "chat_request")
        bot.send_message(
            SUPPORT_CHAT_ID,
            f"💬 ПОЛЬЗОВАТЕЛЬ ХОЧЕТ ПОБОЛТАТЬ!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"📝 Статус: Хочет пообщаться"
        )
        print(f"💬 Пользователь {user_id} хочет поговорить")

# Все сообщения от пользователей пересылаем в поддержку
@bot.message_handler(func=lambda m: not m.text.startswith('/') and m.text not in ['🆘 Мне нужна поддержка', '💬 Я хочу поговорить', '📢 Наш канал', '⭐ Наши отзывы', '👑 Админ меню', '📊 Статистика', '📢 Сделать рассылку', '👥 Список пользователей', '🔨 Забанить пользователя', '🔓 Разбанить пользователя', '📋 Список банов', '🔙 Назад'])
def handle_all_messages(message):
    user_id = message.from_user.id
    
    # Проверяем бан
    if is_banned(user_id):
        return
    
    # Сохраняем статистику
    save_message_stat(user_id, "message")
    
    # Если сообщение из группы поддержки - это ответ админа
    if message.chat.id == SUPPORT_CHAT_ID:
        print(f"📨 Сообщение из поддержки: {message.text}")
        
        if message.reply_to_message:
            replied_text = message.reply_to_message.text
            print(f"🔗 Ответ на: {replied_text}")
            
            if "ID:" in replied_text:
                try:
                    import re
                    user_id = int(re.search(r'ID:(\d+)', replied_text).group(1))
                    print(f"✅ Найден пользователь: {user_id}")
                    
                    # Проверяем не забанен ли пользователь
                    if not is_banned(user_id):
                        bot.send_message(user_id, f"💬 Поддержка: {message.text}")
                        print(f"✅ Ответ отправлен пользователю {user_id}")
                    else:
                        bot.send_message(SUPPORT_CHAT_ID, "❌ Пользователь забанен и не может получать сообщения")
                    
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
    
    # Если сообщение от пользователя - пересылаем в поддержку
    elif not message.from_user.is_bot:
        user_name = message.from_user.first_name
        
        chat_type = "💬 Обычное сообщение"
        if "🆘" in message.text or "поддержк" in message.text.lower():
            chat_type = "🆘 Сообщение в поддержку"
        elif "💬" in message.text "поболтать" in message.text.lower():
            chat_type = "💬 Сообщение для общения"
            
        bot.send_message(
            SUPPORT_CHAT_ID, 
            f"{chat_
