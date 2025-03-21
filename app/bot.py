import telebot
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

bot = telebot.TeleBot(bot_token)

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
    )

@bot.message_handler(commands=['start'])
def privet_command(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        telebot.types.KeyboardButton("Каталог"),
        telebot.types.KeyboardButton("Корзина"),
        telebot.types.KeyboardButton("Мои заказы"),
        telebot.types.KeyboardButton("Мой баланс")
    ]
    keyboard.add(*buttons)

    bot.send_message(message.chat.id, "Привет, я бот интернет-магазина!", reply_markup=keyboard)



@bot.message_handler(func=lambda message: message.text == "Каталог")
def show_catalog(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, quantity, image_url FROM goods")
    goods = cursor.fetchall()
    cursor.close()
    conn.close()

    if goods:
        for name, description, quantity, image_url in goods:
            product_message = f"Название: {name}\nОписание: {description}\nКоличество: {quantity}"

            print(f"Отправляю фото: {image_url}")  # Проверяем ссылку
            
            bot.send_photo(message.chat.id, image_url, caption=product_message)
    else:
        bot.send_message(message.chat.id, "В каталоге нет товаров.")

bot.polling(none_stop=True)
