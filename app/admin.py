import os
import aiohttp
import asyncpg
import asyncio
from dotenv import load_dotenv
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
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

db_pool = None

async def create_db_pool():
    global db_pool
    db_pool = await asyncpg.create_pool(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        min_size=1,
        max_size=10
    )

async def upload_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"
    async with aiohttp.ClientSession() as session:
        with open(image_path, "rb") as file:
            form = aiohttp.FormData()
            form.add_field("key", imgbb_api_key)
            form.add_field("image", file, filename=image_path)
            async with session.post(url, data=form) as response:
                result = await response.json()
                if response.status == 200:
                    return result["data"]["image"]["url"]
                return None

async def add_product_to_db(name, description, quantity, price, image_url):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO goods (name, description, quantity, price, image_url) VALUES ($1, $2, $3, $4, $5)",
            name, description, quantity, price, image_url
        )

class ProductStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_quantity = State()
    waiting_for_price = State()
    waiting_for_image = State()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Введи команду /add_product для добавления товара.")

@dp.message_handler(commands=['add_product'])
async def start_adding_product(message: types.Message):
    await message.answer("Введите название товара:")
    await ProductStates.waiting_for_name.set()

@dp.message_handler(state=ProductStates.waiting_for_name)
async def get_product_name(message: types.Message, state: FSMContext):
    await state.update_data(product_name=message.text)
    await message.answer("Введите описание товара:")
    await ProductStates.waiting_for_description.set()

@dp.message_handler(state=ProductStates.waiting_for_description)
async def get_product_description(message: types.Message, state: FSMContext):
    await state.update_data(product_description=message.text)
    await message.answer("Введите количество товара:")
    await ProductStates.waiting_for_quantity.set()

@dp.message_handler(state=ProductStates.waiting_for_quantity)
async def get_product_quantity(message: types.Message, state: FSMContext):
    try:
        await state.update_data(product_quantity=int(message.text))
        await message.answer("Введите цену товара:")
        await ProductStates.waiting_for_price.set()
    except ValueError:
        await message.answer("Введите число.")

@dp.message_handler(state=ProductStates.waiting_for_price)
async def get_product_price(message: types.Message, state: FSMContext):
    try:
        await state.update_data(product_price=float(message.text))
        await message.answer("Отправьте изображение товара:")
        await ProductStates.waiting_for_image.set()
    except ValueError:
        await message.answer("Введите число.")

@dp.message_handler(content_types=ContentType.PHOTO, state=ProductStates.waiting_for_image)
async def get_product_image(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    downloaded_file = await bot.download_file(file_path)
    
    product_data = await state.get_data()
    image_name = f"temp_{product_data['product_name'].replace(' ', '_')}.jpg"
    
    await asyncio.to_thread(lambda: open(image_name, "wb").write(downloaded_file.getvalue()))
    image_url = await upload_to_imgbb(image_name)
    await asyncio.to_thread(lambda: os.remove(image_name))
    
    if image_url:
        await add_product_to_db(product_data['product_name'], product_data['product_description'], product_data['product_quantity'], product_data['product_price'], image_url)
        await message.answer(f"Товар '{product_data['product_name']}' успешно добавлен!")
    else:
        await message.answer("Ошибка загрузки фото.")
    await state.finish()

async def main():
    await create_db_pool()  # Запускаем пул соединений
    await dp.start_polling()  # Запускаем бота

if __name__ == "__main__":
    asyncio.run(main())  # Асинхронно запускаем бота
