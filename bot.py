import os
import telebot
from telebot import types
import re
import sqlite3
import datetime
import time
from threading import Lock

# Получаем токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN', '8479919737:AAEYofffz9W5--UssgdS5lFN9Y9NkxdidSw')
SUPPORT_CHAT_ID = int(os.getenv('SUPPORT_CHAT_ID', '-1002783988320'))
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '8051825625,1221002491').split(',')]

bot = telebot.TeleBot(TOKEN)

# Храним связь сообщений
message_to_user = {}

# CD система
user_cooldowns = {}
cooldown_lock = Lock()
BUTTON_COOLDOWN = 3  # 3 секунды

def check_cooldown(user_id):
    """Проверяет CD для пользователя"""
    with cooldown_lock:
        current_time = time.time()
        if user_id in user_cooldowns:
            if current_time - user_cooldowns[user_id] < BUTTON_COOLDOWN:
                return False
        user_cooldowns[user_id] = current_time
        return True

# БАЗА ДАННЫХ
def init_db():
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (date TEXT, user_id INTEGER, messages INTEGER, type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                  last_name TEXT, registered_date TEXT, last_activity TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bans
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                  banned_by INTEGER, ban_reason TEXT, ban_date TEXT)''')
    conn.commit()
    conn.close()

init_db()

def is_banned(user_id):
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('SELECT * FROM bans WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def ban_user(user_id, banned_by, reason="Нарушение правил"):
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('SELECT username, first_name FROM users WHERE user_id = ?', (user_id,))
    user_info = c.fetchone()
    username = user_info[0] if user_info else ""
    first_name = user_info[1] if user_info else "Неизвестно"
    c.execute('''INSERT OR REPLACE INTO bans 
                 (user_id, username, first_name, banned_by, ban_reason, ban_date)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, banned_by, reason, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def unban_user(user_id):
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def get_banned_users():
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('SELECT * FROM bans ORDER BY ban_date DESC')
    banned_users = c.fetchall()
    conn.close()
    return banned_users

def save_message_stat(user_id, message_type="message"):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO stats (date, user_id, messages, type)
                 VALUES (?, ?, COALESCE((SELECT messages FROM stats WHERE date=? AND user_id=? AND type=?), 0) + 1, ?)''',
              (today, user_id, today, user_id, message_type, message_type))
    c.execute('''INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_date, last_activity)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, "", "", "", today, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_daily_stats():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('''SELECT COUNT(DISTINCT user_id) FROM stats WHERE date = ?''', (today,))
    daily_users = c.fetchone()[0]
    c.execute('''SELECT COUNT(*) FROM stats WHERE date = ?''', (today,))
    daily_messages = c.fetchone()[0]
    month_start = datetime.datetime.now().replace(day=1).strftime("%Y-%m-%d")
    c.execute('''SELECT COUNT(DISTINCT user_id) FROM stats WHERE date >= ?''', (month_start,))
    monthly_users = c.fetchone()[0]
    c.execute('''SELECT COUNT(*) FROM stats WHERE date >= ?''', (month_start,))
    monthly_messages = c.fetchone()[0]
    c.execute('''SELECT COUNT(*) FROM users''')
    total_users = c.fetchone()[0]
    c.execute('''SELECT COUNT(*) FROM bans''')
    banned_users = c.fetchone()[0]
    conn.close()
    return {
        'daily_users': daily_users,
        'daily_messages': daily_messages,
        'monthly_users': monthly_users,
        'monthly_messages': monthly_messages,
        'total_users': total_users,
        'banned_users': banned_users
    }

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        bot.send_message(user_id, "❌ Вы заблокированы в этом боте и не можете использовать его функции.")
        return
    
    save_message_stat(user_id, "start")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🆘 Мне нужна поддержка')
    btn2 = types.KeyboardButton('💬 Я хочу поговорить') 
    btn3 = types.KeyboardButton('📢 Наш канал')
    btn4 = types.KeyboardButton('⭐ Наши отзывы')
    
    if user_id in ADMIN_IDS:
        btn5 = types.KeyboardButton('👑 Админ меню')
        markup.add(btn1, btn2, btn3, btn4, btn5)
    else:
        markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите опцию:", reply_markup=markup)

# АДМИН МЕНЮ
@bot.message_handler(func=lambda m: m.text == '👑 Админ меню' and m.from_user.id in ADMIN_IDS)
def admin_menu(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('📊 Статистика')
    btn2 = types.KeyboardButton('📢 Сделать рассылку')
    btn3 = types.KeyboardButton('👥 Список пользователей')
    btn4 = types.KeyboardButton('🔨 Забанить пользователя')
    btn5 = types.KeyboardButton('🔓 Разбанить пользователя')
    btn6 = types.KeyboardButton('📋 Список банов')
    btn7 = types.KeyboardButton('🔙 Назад')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    
    bot.send_message(message.chat.id, "👑 Панель администратора:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text in ['📊 Статистика', '👥 Список пользователей', '📋 Список банов'])
def handle_admin_commands(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    if message.text == '📊 Статистика':
        stats = get_daily_stats()
        stat_text = f"""
📊 **СТАТИСТИКА БОТА**

📅 **ЗА СЕГОДНЯ:**
👤 Пользователей: {stats['daily_users']}
💬 Сообщений: {stats['daily_messages']}

📅 **ЗА МЕСЯЦ:**
👤 Пользователей: {stats['monthly_users']}
💬 Сообщений: {stats['monthly_messages']}

👥 **ВСЕГО ПОЛЬЗОВАТЕЛЕЙ:** {stats['total_users']}
🔨 **ЗАБАНЕНО:** {stats['banned_users']}
        """
        bot.send_message(message.chat.id, stat_text, parse_mode='Markdown')
    
    elif message.text == '👥 Список пользователей':
        conn = sqlite3.connect('bot_stats.db')
        c = conn.cursor()
        c.execute('''SELECT user_id, first_name, username, registered_date 
                     FROM users ORDER BY registered_date DESC LIMIT 10''')
        users = c.fetchall()
        conn.close()
        
        users_text = "👥 **ПОСЛЕДНИЕ 10 ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
        for user in users:
            user_id, first_name, username, reg_date = user
            username = f"@{username}" if username else "нет username"
            users_text += f"👤 {first_name} ({username})\n🆔 ID: {user_id}\n📅 {reg_date}\n\n"
        
        bot.send_message(message.chat.id, users_text, parse_mode='Markdown')
    
    elif message.text == '📋 Список банов':
        banned_users = get_banned_users()
        
        if not banned_users:
            bot.send_message(message.chat.id, "📝 Список банов пуст.")
            return
        
        ban_text = "🔨 **ЗАБАНЕННЫЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
        
        for ban in banned_users:
            user_id, username, first_name, banned_by, reason, ban_date = ban
            username = f"@{username}" if username else "нет username"
            ban_date = datetime.datetime.fromisoformat(ban_date).strftime("%d.%m.%Y %H:%M")
            ban_text += f"👤 {first_name} ({username})\n🆔 ID: {user_id}\n📅 {ban_date}\n📝 {reason}\n\n"
        
        bot.send_message(message.chat.id, ban_text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '🔨 Забанить пользователя')
def ban_user_start(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    msg = bot.send_message(message.chat.id, "🔨 Введите ID пользователя для бана:")
    bot.register_next_step_handler(msg, process_ban_user_id)

def process_ban_user_id(message):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    try:
        user_id = int(message.text.strip())
        
        if user_id in ADMIN_IDS:
            bot.send_message(message.chat.id, "❌ Нельзя забанить администратора!")
            return admin_menu(message)
        
        if is_banned(user_id):
            bot.send_message(message.chat.id, "❌ Этот пользователь уже забанен!")
            return admin_menu(message)
        
        msg = bot.send_message(message.chat.id, f"🆔 Пользователь: {user_id}\n📝 Введите причину бана:")
        bot.register_next_step_handler(msg, process_ban_reason, user_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID! Введите числовой ID.")
        admin_menu(message)

def process_ban_reason(message, user_id):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    reason = message.text.strip()
    
    if ban_user(user_id, message.from_user.id, reason):
        bot.send_message(message.chat.id, f"✅ Пользователь {user_id} забанен!\nПричина: {reason}")
        try:
            bot.send_message(user_id, f"❌ Вы были забанены в боте!\nПричина: {reason}")
        except:
            pass
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при бане пользователя")
    
    admin_menu(message)

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '🔓 Разбанить пользователя')
def unban_user_start(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    msg = bot.send_message(message.chat.id, "🔓 Введите ID пользователя для разбана:")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    try:
        user_id = int(message.text.strip())
        
        if not is_banned(user_id):
            bot.send_message(message.chat.id, "❌ Этот пользователь не забанен!")
            return admin_menu(message)
        
        if unban_user(user_id):
            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} разбанен!")
            try:
                bot.send_message(user_id, "✅ Вы были разбанены в боте!")
            except:
                pass
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при разбане пользователя")
        
        admin_menu(message)
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID! Введите числовой ID.")
        admin_menu(message)

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '📢 Сделать рассылку')
def start_broadcast(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    msg = bot.send_message(message.chat.id, "📝 Введите сообщение для рассылки:")
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    broadcast_text = message.text
    msg = bot.send_message(message.chat.id, f"📤 Начинаю рассылку...\n\nТекст: {broadcast_text}\n\nОтправьте '✅' для подтверждения или '❌' для отмены:")
    bot.register_next_step_handler(msg, confirm_broadcast, broadcast_text)

def confirm_broadcast(message, broadcast_text):
    if message.text == '✅':
        bot.send_message(message.chat.id, "🔄 Начинаю рассылку...")
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
        if is_banned(user[0]):
            continue
            
        try:
            bot.send_message(user[0], f"📢 Рассылка:\n\n{text}")
            success += 1
            time.sleep(0.1)  # Задержка чтобы не спамить
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
    admin_menu(bot.send_message(admin_id, "Возвращаю в админ-меню..."))

@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
    start(message)

# ОСНОВНЫЕ ФУНКЦИИ БОТА С CD
@bot.message_handler(func=lambda m: m.text in ['🆘 Мне нужна поддержка', '💬 Я хочу поговорить'])
def start_chat(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    user_id = message.from_user.id
    
    if is_banned(user_id):
        bot.send_message(user_id, "❌ Вы заблокированы в этом боте и не можете использовать его функции.")
        return
    
    user_name = message.from_user.first_name
    
    if message.text == '🆘 Мне нужна поддержка':
        bot.send_message(user_id, "💬 Чат с поддержкой начат! Ожидайте ответа...")
        save_message_stat(user_id, "support_request")
        
        msg = bot.send_message(
            SUPPORT_CHAT_ID,
            f"🆘 ПОЛЬЗОВАТЕЛЬ НУЖДАЕТСЯ В ПОДДЕРЖКЕ!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"✉️ Ответьте реплаем на это сообщение"
        )
        message_to_user[msg.message_id] = user_id
        
    else:
        bot.send_message(user_id, "💬 Режим общения начат! Ожидайте ответа...")
        save_message_stat(user_id, "chat_request")
        
        msg = bot.send_message(
            SUPPORT_CHAT_ID,
            f"💬 ПОЛЬЗОВАТЕЛЬ ХОЧЕТ ПОБОЛТАТЬ!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"✉️ Ответьте реплаем на это сообщение"
        )
        message_to_user[msg.message_id] = user_id

@bot.message_handler(func=lambda m: m.text == '📢 Наш канал')
def channel(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    user_id = message.from_user.id
    if is_banned(user_id):
        return
    save_message_stat(user_id, "channel_click")
    bot.send_message(message.chat.id, "📢 https://t.me/kaplyakrovi_tgk")

@bot.message_handler(func=lambda m: m.text == '⭐ Наши отзывы')
def reviews(message):
    if not check_cooldown(message.from_user.id):
        bot.send_message(message.chat.id, "⏳ Подождите 3 секунды перед следующим действием")
        return
        
    user_id = message.from_user.id
    if is_banned(user_id):
        return
    save_message_stat(user_id, "reviews_click")
    bot.send_message(message.chat.id, "⭐ https://t.me/otziv_kaplyakrovi")

# Обработка медиа-контента
@bot.message_handler(content_types=['photo', 'sticker', 'voice', 'audio', 'document', 'video'])
def handle_media(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    user_name = message.from_user.first_name
    content_type = message.content_type
    
    # Сохраняем статистику
    save_message_stat(user_id, content_type)
    
    # Определяем тип контента и текст
    type_texts = {
        'photo': '📷 фото',
        'sticker': '🎭 стикер', 
        'voice': '🎤 голосовое сообщение',
        'audio': '🎵 музыку',
        'document': '📎 документ',
        'video': '🎥 видео'
    }
    
    type_text = type_texts.get(content_type, 'медиа')
    
    # Отправляем в группу поддержки
    caption = f"📤 {user_name} (ID:{user_id}) отправил {type_text}"
    if message.caption:
        caption += f"\n\nПодпись: {message.caption}"
    
    # Отправляем в зависимости от типа контента
    try:
        if content_type == 'photo':
            msg = bot.send_photo(SUPPORT_CHAT_ID, message.photo[-1].file_id, 
                               caption=caption + "\n\n✉️ Ответьте реплаем на это сообщение")
        elif content_type == 'sticker':
            msg = bot.send_message(SUPPORT_CHAT_ID, 
                                 f"{caption}\n\n✉️ Ответьте реплаем на это сообщение")
            bot.send_sticker(SUPPORT_CHAT_ID, message.sticker.file_id)
        elif content_type == 'voice':
            msg = bot.send_voice(SUPPORT_CHAT_ID, message.voice.file_id, 
                               caption=caption + "\n\n✉️ Ответьте реплаем на это сообщение")
        elif content_type == 'audio':
            msg = bot.send_audio(SUPPORT_CHAT_ID, message.audio.file_id, 
                               caption=caption + "\n\n✉️ Ответьте реплаем на это сообщение")
        elif content_type == 'document':
            msg = bot.send_document(SUPPORT_CHAT_ID, message.document.file_id, 
                                  caption=caption + "\n\n✉️ Ответьте реплаем на это сообщение")
        elif content_type == 'video':
            msg = bot.send_video(SUPPORT_CHAT_ID, message.video.file_id, 
                               caption=caption + "\n\n✉️ Ответьте реплаем на это сообщение")
        
        message_to_user[msg.message_id] = user_id
        bot.send_message(user_id, f"✅ {type_text.capitalize()} отправлено! Ожидайте ответа.")
        
    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка при отправке {type_text}")
        print(f"Media error: {e}")

# Пересылаем обычные текстовые сообщения
@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.text and m.text not in ['🆘 Мне нужна поддержка', '💬 Я хочу поговорить', '📢 Наш канал', '⭐ Наши отзывы', '👑 Админ меню', '📊 Статистика', '📢 Сделать рассылку', '👥 Список пользователей', '🔨 Забанить пользователя', '🔓 Разбанить пользователя', '📋 Список банов', '🔙 Назад'])
def forward_message(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    save_message_stat(user_id, "message")
    user_name = message.from_user.first_name
    
    msg = bot.send_message(
        SUPPORT_CHAT_ID,
        f"💬 {user_name} (ID:{user_id}):\n{message.text}\n\n✉️ Ответьте реплаем на это сообщение"
    )
    
    message_to_user[msg.message_id] = user_id

# Обрабатываем ответы из группы
@bot.message_handler(func=lambda m: m.chat.id == SUPPORT_CHAT_ID and m.reply_to_message)
def handle_reply(message):
    try:
        replied_id = message.reply_to_message.message_id
        
        if replied_id in message_to_user:
            user_id = message_to_user[replied_id]
            send_reply_to_user(user_id, message)
        else:
            # Пытаемся найти ID пользователя в тексте сообщения
            replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            if "ID:" in replied_text:
                match = re.search(r'ID:(\d+)', replied_text)
                if match:
                    user_id = int(match.group(1))
                    send_reply_to_user(user_id, message)
                    
    except Exception as e:
        bot.send_message(SUPPORT_CHAT_ID, f"❌ Ошибка: {e}")

def send_reply_to_user(user_id, message):
    """Отправляет ответ пользователю"""
    try:
        if message.text:
            bot.send_message(user_id, f"💬 Поддержка:\n{message.text}")
        elif message.photo:
            bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
        elif message.sticker:
            bot.send_sticker(user_id, message.sticker.file_id)
        elif message.voice:
            bot.send_voice(user_id, message.voice.file_id)
        elif message.audio:
            bot.send_audio(user_id, message.audio.file_id, caption=message.caption)
        elif message.document:
            bot.send_document(user_id, message.document.file_id, caption=message.caption)
        elif message.video:
            bot.send_video(user_id, message.video.file_id, caption=message.caption)
        
        bot.send_message(SUPPORT_CHAT_ID, f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        bot.send_message(SUPPORT_CHAT_ID, f"❌ Не удалось отправить ответ пользователю {user_id}: {e}")

# Игнорируем другие группы
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'] and m.chat.id != SUPPORT_CHAT_ID)
def ignore_other_groups(message):
    pass

if __name__ == '__main__':
    print("🚀 Бот запущен на хостинге!")
    print("🎵 Поддержка всех медиа-форматов активирована")
    print("🛡️  CD защита активирована (3 секунды)")
    
    # Бесконечный цикл для работы на хостинге
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
            print("Перезапуск бота...")
