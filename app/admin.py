import os
import telebot
import requests
from dotenv import load_dotenv
import psycopg2

# Загружаем переменные окружения
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')
imgbb_api_key = os.getenv('IMGBB_API_KEY')

bot = telebot.TeleBot(bot_token)

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
    )

# Функция загрузки изображения в imgbb
def upload_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"
    with open(image_path, "rb") as file:
        response = requests.post(url, data={"key": imgbb_api_key}, files={"image": file})
    
    print(response.json())  # Смотрим, что возвращает API

    if response.status_code == 200:
        return response.json()["data"]["image"]["url"]  # Правильный путь
    else:
        print("Ошибка загрузки:", response.json())
        return None


# Добавление товара в БД
def add_product_to_db(name, description, quantity, image_url):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goods (name, description, quantity, image_url) VALUES (%s, %s, %s, %s)",
        (name, description, quantity, image_url)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def privet_command(message):
    bot.send_message(message.chat.id, "Привет, я административный бот интернет-магазина, введи команду /add_product для добавления товара!")

# Запуск добавления товара
@bot.message_handler(commands=['add_product'])
def start_adding_product(message):
    bot.send_message(message.chat.id, "Введите название товара:")
    bot.register_next_step_handler(message, get_product_name)

def get_product_name(message):
    product_name = message.text
    bot.send_message(message.chat.id, "Введите описание товара:")
    bot.register_next_step_handler(message, get_product_description, product_name)

def get_product_description(message, product_name):
    product_description = message.text
    bot.send_message(message.chat.id, "Введите количество товара:")
    bot.register_next_step_handler(message, get_product_quantity, product_name, product_description)

def get_product_quantity(message, product_name, product_description):
    try:
        product_quantity = int(message.text)
        bot.send_message(message.chat.id, "Отправьте изображение товара:")
        bot.register_next_step_handler(message, get_product_image, product_name, product_description, product_quantity)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите количество числом.")

def get_product_image(message, product_name, product_description, product_quantity):
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        downloaded_file = bot.download_file(file_path)

        # Сохраняем временный файл
        image_name = f"{product_name.replace(' ', '_')}.jpg"
        local_image_path = f"temp_{image_name}"

        with open(local_image_path, "wb") as new_file:
            new_file.write(downloaded_file)

        # Загружаем в imgbb
        image_url = upload_to_imgbb(local_image_path)

        # Удаляем временный файл
        os.remove(local_image_path)

        if image_url:
            add_product_to_db(product_name, product_description, product_quantity, image_url)
            bot.send_message(message.chat.id, f"Товар '{product_name}' успешно добавлен!")
        else:
            bot.send_message(message.chat.id, "Ошибка загрузки фото. Попробуйте снова.")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте изображение.")


# ЗАПУСКАЕМ БОТА
bot.polling(none_stop=True)
