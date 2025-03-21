import os
import requests
from dotenv import load_dotenv
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Загружаем переменные окружения
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')
imgbb_api_key = os.getenv('IMGBB_API_KEY')

bot = Bot(token=bot_token)

# Используем MemoryStorage для хранения состояний
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

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
def add_product_to_db(name, description, quantity, price, image_url):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goods (name, description, quantity, price, image_url) VALUES (%s, %s, %s, %s, %s)",
        (name, description, quantity, price, image_url)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Классы состояний для FSM
class ProductStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_quantity = State()
    waiting_for_price = State()  # Новый шаг для ввода цены
    waiting_for_image = State()

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет, я административный бот интернет-магазина, введи команду /add_product для добавления товара!")

# Запуск добавления товара
@dp.message_handler(commands=['add_product'])
async def start_adding_product(message: types.Message):
    await message.answer("Введите название товара:")
    await ProductStates.waiting_for_name.set()  # Устанавливаем состояние

# Шаг 1: Получаем название товара
@dp.message_handler(state=ProductStates.waiting_for_name)
async def get_product_name(message: types.Message, state: FSMContext):
    product_name = message.text
    await state.update_data(product_name=product_name)  # Сохраняем название товара
    await message.answer("Введите описание товара:")
    await ProductStates.waiting_for_description.set()  # Переходим к следующему шагу

# Шаг 2: Получаем описание товара
@dp.message_handler(state=ProductStates.waiting_for_description)
async def get_product_description(message: types.Message, state: FSMContext):
    product_description = message.text
    await state.update_data(product_description=product_description)  # Сохраняем описание товара
    await message.answer("Введите количество товара:")
    await ProductStates.waiting_for_quantity.set()  # Переходим к следующему шагу

# Шаг 3: Получаем количество товара
@dp.message_handler(state=ProductStates.waiting_for_quantity)
async def get_product_quantity(message: types.Message, state: FSMContext):
    try:
        product_quantity = int(message.text)
        await state.update_data(product_quantity=product_quantity)  # Сохраняем количество
        await message.answer("Введите цену товара:")
        await ProductStates.waiting_for_price.set()  # Переходим к следующему шагу
    except ValueError:
        await message.answer("Пожалуйста, введите количество числом.")

# Шаг 4: Получаем цену товара
@dp.message_handler(state=ProductStates.waiting_for_price)
async def get_product_price(message: types.Message, state: FSMContext):
    try:
        product_price = float(message.text)  # Преобразуем цену в число с плавающей точкой
        await state.update_data(product_price=product_price)  # Сохраняем цену
        await message.answer("Отправьте изображение товара:")
        await ProductStates.waiting_for_image.set()  # Переходим к следующему шагу
    except ValueError:
        await message.answer("Пожалуйста, введите цену числом.")

# Шаг 5: Получаем изображение товара
@dp.message_handler(content_types=ContentType.PHOTO, state=ProductStates.waiting_for_image)
async def get_product_image(message: types.Message, state: FSMContext):
    # Загружаем изображение
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    downloaded_file = await bot.download_file(file_path)

    # Сохраняем временный файл
    product_data = await state.get_data()
    product_name = product_data["product_name"]
    image_name = f"{product_name.replace(' ', '_')}.jpg"
    local_image_path = f"temp_{image_name}"

    # Записываем файл в локальную систему как байты
    with open(local_image_path, "wb") as new_file:
        new_file.write(downloaded_file.getvalue())  # Преобразуем в байты

    # Загружаем в imgbb
    image_url = upload_to_imgbb(local_image_path)

    # Удаляем временный файл
    os.remove(local_image_path)

    if image_url:
        # Добавляем товар в базу данных
        await state.update_data(image_url=image_url)  # Сохраняем URL изображения
        product_description = product_data["product_description"]
        product_quantity = product_data["product_quantity"]
        product_price = product_data["product_price"]
        add_product_to_db(product_name, product_description, product_quantity, product_price, image_url)
        await message.answer(f"Товар '{product_name}' успешно добавлен!")
    else:
        await message.answer("Ошибка загрузки фото. Попробуйте снова.")

    # Завершаем процесс добавления товара
    await state.finish()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
