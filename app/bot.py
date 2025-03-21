import os
import psycopg2
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Command
from aiogram.utils import executor

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup


load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

bot = Bot(token=bot_token)
dp = Dispatcher(bot)

from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Инициализация хранилища состояний
storage = MemoryStorage()

# Инициализация Dispatcher с хранилищем
dp = Dispatcher(bot, storage=storage)

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
    )


# Состояния для процесса покупки товара
class PurchaseStates(StatesGroup):
    waiting_for_quantity = State()

# Хендлер для команды /start
@dp.message_handler(Command("start"))
async def privet_command(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("Каталог"),
        KeyboardButton("Корзина"),
        KeyboardButton("Мои заказы"),
        KeyboardButton("Мой баланс")
    ]
    keyboard.add(*buttons)
    
    await message.answer("Привет, я бот интернет-магазина!", reply_markup=keyboard)

# Хендлер для отображения каталога товаров
@dp.message_handler(lambda message: message.text == "Каталог")
async def show_catalog(message: types.Message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, quantity, price, image_url FROM goods")
    goods = cursor.fetchall()
    cursor.close()
    conn.close()

    if goods:
        for product in goods:
            product_id, name, description, quantity, price, image_url = product
            product_message = f"Название: {name}\nОписание: {description}\nКоличество: {quantity}\nЦена: {price} руб."

            # Создаем inline кнопку "Купить"
            markup = InlineKeyboardMarkup()
            buy_button = InlineKeyboardButton("Купить", callback_data=f"buy_{product_id}_{quantity}_{price}")
            markup.add(buy_button)

            # Отправляем товар с кнопкой
            await message.answer_photo(image_url, caption=product_message, reply_markup=markup)
    else:
        await message.answer("В каталоге нет товаров.")

# Хендлер для кнопки "Купить"
@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy_product(callback_query: types.CallbackQuery, state: FSMContext):
    # Извлекаем данные из callback_data
    product_id, product_quantity, product_price = callback_query.data.split('_')[1:]
    product_id = int(product_id)
    product_quantity = int(product_quantity)
    product_price = float(product_price)

    # Запрашиваем количество товара
    await callback_query.message.answer(f"Сколько товара вы хотите купить? Доступно на складе: {product_quantity}")
    
    # Сохраняем данные о товаре в состоянии
    await state.update_data(product_id=product_id, product_quantity=product_quantity, product_price=product_price)
    
    await PurchaseStates.waiting_for_quantity.set()

# Хендлер для получения количества товара
@dp.message_handler(state=PurchaseStates.waiting_for_quantity)
async def get_product_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        user_data = await state.get_data()
        product_id = user_data['product_id']
        product_quantity = user_data['product_quantity']
        product_price = user_data['product_price']

        # Проверяем, достаточно ли товара на складе
        if quantity > product_quantity:
            await message.answer(f"На складе нет такого количества товара. Доступно всего: {product_quantity}. Введите количество заново.")
        else:
            # Добавляем товар в корзину с указанным количеством
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO carts (user_id, product_id, price, quantity) 
                VALUES (%s, %s, %s, %s)
            """, (message.from_user.id, product_id, product_price, quantity))
            conn.commit()
            cursor.close()
            conn.close()

            await message.answer(f"Товар успешно добавлен в корзину! {quantity} шт. по цене {product_price} руб. за штуку.")
            await state.finish()  # Завершаем процесс
    except ValueError:
        await message.answer("Пожалуйста, введите количество числом.")

# Хендлер для отображения корзины
@dp.message_handler(lambda message: message.text == "Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()

    # Получаем товары из корзины с image_url
    cursor.execute("""
        SELECT g.name, g.price, g.image_url, c.id, c.quantity
        FROM carts c
        JOIN goods g ON c.product_id = g.id
        WHERE c.user_id = %s
    """, (user_id,))

    cart_items = cursor.fetchall()
    cursor.close()
    conn.close()

    if cart_items:
        await message.answer("Ваша корзина:")

        # Добавляем товары в сообщение и создаем кнопки для удаления
        for item in cart_items:
            name, price, image_url, cart_item_id, quantity = item

            # Вычисляем итоговую цену
            total_price = price * quantity

            # Создаем inline кнопку "Удалить"
            remove_button = InlineKeyboardButton("Удалить", callback_data=f"remove_{cart_item_id}")
            markup = InlineKeyboardMarkup().add(remove_button)

            # Отправляем изображение товара с описанием и кнопкой удаления
            await message.answer_photo(image_url, caption=f"{name} - {price} руб. (Количество: {quantity})\nИтоговая цена: {total_price} руб.", reply_markup=markup)
    else:
        await message.answer("Ваша корзина пуста.")

# Хендлер для удаления товара из корзины
@dp.callback_query_handler(lambda call: call.data.startswith("remove_"))
async def remove_from_cart(call: types.CallbackQuery):
    cart_item_id = call.data.split("_")[1]

    # Удаляем товар из корзины
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carts WHERE id = %s", (cart_item_id,))
    conn.commit()
    cursor.close()
    conn.close()

    await call.message.answer("Товар удален из корзины.")
    # Обновляем корзину
    await show_cart(call.message)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
