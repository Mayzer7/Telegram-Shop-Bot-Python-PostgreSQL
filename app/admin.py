import os
import telebot
from dotenv import load_dotenv
import psycopg2

# Загружаем переменные окружения
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')
admin_password = os.getenv('ADMIN_PASSWORD')

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

# Папка для изображений
IMAGE_FOLDER = 'images/goods/'
os.makedirs(IMAGE_FOLDER, exist_ok=True)  # Создаёт папку, если её нет

# Добавление товара в БД
def add_product_to_db(name, description, quantity, image_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goods (name, description, quantity, image_url) VALUES (%s, %s, %s, %s)",
        (name, description, quantity, image_path)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def privet_command(message):
    bot.send_message(message.chat.id, "Привет, я администратинвый бот интернет-магазина, введи команду /add_product для добавления товара в базу данных!")

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

        # Сохранение изображения
        image_name = f"{product_name.replace(' ', '_')}.jpg"
        image_full_path = os.path.join(IMAGE_FOLDER, image_name)

        with open(image_full_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Сохраняем относительный путь в БД
        add_product_to_db(product_name, product_description, product_quantity, image_full_path)

        bot.send_message(message.chat.id, f"Товар '{product_name}' успешно добавлен!")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте изображение.")

# Запускаем бота
bot.polling(none_stop=True)
