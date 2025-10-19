import telebot
from telebot import types
import datetime
import time
import sqlite3
import threading
from flask import Flask
import requests

TOKEN = "8479919737:AAEYofffz9W5--UssgdS5lFN9Y9NkxdidSw"
bot = telebot.TeleBot(TOKEN)

SUPPORT_CHAT_ID = -1002783988320
ADMIN_IDS = [8051825625, 1221002491]  # ID админов

# Flask app для мониторинга
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот поддержки работает! Статус: ONLINE"

@app.route('/ping')
def ping():
    return "PONG"

# Функция для самопинга чтобы не засыпал
def keep_awake():
    while True:
        try:
            bot_url = "https://supp-b0t.onrender.com"
            response = requests.get(f"{bot_url}/ping", timeout=10)
            print(f"🔄 Самопинг отправлен: {response.status_code} - бот активен")
        except Exception as e:
            print(f"⚠️ Ошибка самопинга: {e}")
        time.sleep(300)

# Запускаем Flask в отдельном потоке
def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Запускаем потоки
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

ping_thread = threading.Thread(target=keep_awake)
ping_thread.daemon = True
ping_thread.start()

print("🚀 Бот запускается...")
print("🔄 Самопинг активирован - бот не будет засыпать")

# База данных для статистики и банов
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
    """Проверяет забанен ли пользователь"""
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('SELECT * FROM bans WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def ban_user(user_id, banned_by, reason="Нарушение правил"):
    """Банит пользователя"""
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    
    # Получаем информацию о пользователе
    c.execute('SELECT username, first_name FROM users WHERE user_id = ?', (user_id,))
    user_info = c.fetchone()
    username = user_info[0] if user_info else ""
    first_name = user_info[1] if user_info else "Неизвестно"
    
    # Добавляем в бан лист
    c.execute('''INSERT OR REPLACE INTO bans 
                 (user_id, username, first_name, banned_by, ban_reason, ban_date)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, banned_by, reason, datetime.datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True

def unban_user(user_id):
    """Разбанивает пользователя"""
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    c.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def get_banned_users():
    """Получает список забаненных пользователей"""
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
    
    # Сохраняем статистику сообщений
    c.execute('''INSERT OR REPLACE INTO stats (date, user_id, messages, type)
                 VALUES (?, ?, COALESCE((SELECT messages FROM stats WHERE date=? AND user_id=? AND type=?), 0) + 1, ?)''',
              (today, user_id, today, user_id, message_type, message_type))
    
    # Сохраняем/обновляем информацию о пользователе
    c.execute('''INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_date, last_activity)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, "", "", "", today, datetime.datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def get_daily_stats():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('bot_stats.db')
    c = conn.cursor()
    
    # Статистика за день
    c.execute('''SELECT COUNT(DISTINCT user_id) FROM stats WHERE date = ?''', (today,))
    daily_users = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM stats WHERE date = ?''', (today,))
    daily_messages = c.fetchone()[0]
    
    # Статистика за месяц
    month_start = datetime.datetime.now().replace(day=1).strftime("%Y-%m-%d")
    c.execute('''SELECT COUNT(DISTINCT user_id) FROM stats WHERE date >= ?''', (month_start,))
    monthly_users = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM stats WHERE date >= ?''', (month_start,))
    monthly_messages = c.fetchone()[0]
    
    # Всего пользователей
    c.execute('''SELECT COUNT(*) FROM users''')
    total_users = c.fetchone()[0]
    
    # Забаненные пользователи
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
    
    # Проверяем бан
    if is_banned(user_id):
        bot.send_message(user_id, "❌ Вы заблокированы в этом боте и не можете использовать его функции.")
        return
    
    # Сохраняем пользователя
    save_message_stat(user_id, "start")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🆘 Мне нужна поддержка')
    btn2 = types.KeyboardButton('💬 Я хочу поговорить') 
    btn3 = types.KeyboardButton('📢 Наш канал')
    btn4 = types.KeyboardButton('⭐ Наши отзывы')
    
    # Добавляем админ-меню для админов
    if user_id in ADMIN_IDS:
        btn5 = types.KeyboardButton('👑 Админ меню')
        markup.add(btn1, btn2, btn3, btn4, btn5)
    else:
        markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите опцию:", reply_markup=markup)

# Админ меню
@bot.message_handler(func=lambda m: m.text == '👑 Админ меню' and m.from_user.id in ADMIN_IDS)
def admin_menu(message):
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

# Обработка админ-команд
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text in ['📊 Статистика', '👥 Список пользователей', '📋 Список банов'])
def handle_admin_commands(message):
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
        print(f"📊 Админ {message.from_user.id} запросил статистику")
    
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
        print(f"👥 Админ {message.from_user.id} запросил список пользователей")
    
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

# Кнопка Забанить пользователя
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '🔨 Забанить пользователя')
def ban_user_start(message):
    msg = bot.send_message(message.chat.id, "🔨 Введите ID пользователя для бана:")
    bot.register_next_step_handler(msg, process_ban_user_id)

def process_ban_user_id(message):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    try:
        user_id = int(message.text.strip())
        
        # Проверяем не админ ли это
        if user_id in ADMIN_IDS:
            bot.send_message(message.chat.id, "❌ Нельзя забанить администратора!")
            return admin_menu(message)
        
        # Проверяем не забанен ли уже
        if is_banned(user_id):
            bot.send_message(message.chat.id, "❌ Этот пользователь уже забанен!")
            return admin_menu(message)
        
        # Сохраняем ID для следующего шага
        msg = bot.send_message(message.chat.id, f"🆔 Пользователь: {user_id}\n📝 Введите причину бана:")
        bot.register_next_step_handler(msg, process_ban_reason, user_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID! Введите числовой ID.")
        admin_menu(message)

def process_ban_reason(message, user_id):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    reason = message.text.strip()
    
    # Баним пользователя
    if ban_user(user_id, message.from_user.id, reason):
        bot.send_message(message.chat.id, f"✅ Пользователь {user_id} забанен!\nПричина: {reason}")
        print(f"🔨 Админ {message.from_user.id} забанил пользователя {user_id}")
        
        # Пытаемся уведомить пользователя
        try:
            bot.send_message(user_id, f"❌ Вы были забанены в боте!\nПричина: {reason}")
        except:
            pass
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при бане пользователя")
    
    admin_menu(message)

# Кнопка Разбанить пользователя
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '🔓 Разбанить пользователя')
def unban_user_start(message):
    msg = bot.send_message(message.chat.id, "🔓 Введите ID пользователя для разбана:")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    if message.text == '🔙 Назад':
        return admin_menu(message)
    
    try:
        user_id = int(message.text.strip())
        
        # Проверяем забанен ли пользователь
        if not is_banned(user_id):
            bot.send_message(message.chat.id, "❌ Этот пользователь не забанен!")
            return admin_menu(message)
        
        # Разбаниваем пользователя
        if unban_user(user_id):
            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} разбанен!")
            print(f"🔓 Админ {message.from_user.id} разбанил пользователя {user_id}")
            
            # Пытаемся уведомить пользователя
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

# Рассылка сообщений
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == '📢 Сделать рассылку')
def start_broadcast(message):
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

# Все сообщения от пользователей пересылаем в поддержку (ТОЛЬКО РЕАЛЬНЫЕ СООБЩЕНИЯ)
@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_all_messages(message):
    user_id = message.from_user.id
    
    # Проверяем бан
    if is_banned(user_id):
        return
    
    # СПИСОК КНОПОК КОТОРЫЕ НЕ ПЕРЕСЫЛАЕМ В ГРУППУ
    menu_buttons = [
        '🆘 Мне нужна поддержка', '💬 Я хочу поговорить', '📢 Наш канал', '⭐ Наши отзывы',
        '👑 Админ меню', '📊 Статистика', '📢 Сделать рассылку', '👥 Список пользователей',
        '🔨 Забанить пользователя', '🔓 Разбанить пользователя', '📋 Список банов', '🔙 Назад'
    ]
    
    # Если это кнопка меню - не пересылаем в группу
    if message.text in menu_buttons:
        return
    
    # Сохраняем статистику только для реальных сообщений
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
    
    # Если сообщение от пользователя - пересылаем в поддержку (ТОЛЬКО РЕАЛЬНЫЕ СООБЩЕНИЯ)
    elif not message.from_user.is_bot:
        user_name = message.from_user.first_name
        
        chat_type = "💬 Обычное сообщение"
        if "🆘" in message.text or "поддержк" in message.text.lower():
            chat_type = "🆘 Сообщение в поддержку"
        elif "💬" in message.text or "поболтать" in message.text.lower():
            chat_type = "💬 Сообщение для общения"
            
        bot.send_message(
            SUPPORT_CHAT_ID, 
            f"{chat_type}\n👤 {user_name} (ID:{user_id}): {message.text}"
        )
        print(f"📨 Сообщение от пользователя {user_id}: {message.text}")

@bot.message_handler(func=lambda m: m.text == '📢 Наш канал')
def channel(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return
    save_message_stat(user_id, "channel_click")
    bot.send_message(message.chat.id, "📢 https://t.me/kaplyakrovi_tgk")

@bot.message_handler(func=lambda m: m.text == '⭐ Наши отзывы')
def reviews(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return
    save_message_stat(user_id, "reviews_click")
    bot.send_message(message.chat.id, "⭐ https://t.me/otziv_kaplyakrovi")

if __name__ == '__main__':
    print("🚀 Бот запущен! Ожидание сообщений...")
    print(f"👑 Админы: {ADMIN_IDS}")
    bot.polling(none_stop=True)
