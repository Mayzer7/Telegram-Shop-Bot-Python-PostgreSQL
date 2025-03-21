import os
import psycopg2
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Command
from aiogram.utils import executor

load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

bot = Bot(token=bot_token)
dp = Dispatcher(bot)

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
    )

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
            buy_button = InlineKeyboardButton("Купить", callback_data=f"buy_{product_id}_{price}")
            markup.add(buy_button)

            # Отправляем товар с кнопкой
            await message.answer_photo(image_url, caption=product_message, reply_markup=markup)
    else:
        await message.answer("В каталоге нет товаров.")

# Хендлер для обработки инлайн кнопки "Купить"
@dp.callback_query_handler(lambda call: call.data.startswith("buy_"))
async def handle_buy(call: types.CallbackQuery):
    # Извлекаем id товара и цену из callback_data
    product_id, price = call.data.split("_")[1], call.data.split("_")[2]
    price = float(price)  # Преобразуем цену в число с плавающей точкой

    # Получаем информацию о товаре из БД
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM goods WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if product:
        product_name = product[0]
        
        # Создаем inline кнопки "Да" и "Нет"
        markup = InlineKeyboardMarkup()
        yes_button = InlineKeyboardButton("Да", callback_data=f"confirm_buy_{product_id}_{price}")
        no_button = InlineKeyboardButton("Нет", callback_data="cancel_buy")
        markup.add(yes_button, no_button)

        # Спрашиваем пользователя, хочет ли он купить товар
        await call.message.answer(f"Вы хотите купить товар с названием: {product_name} за {price} руб.?", reply_markup=markup)

# Хендлер для подтверждения покупки
@dp.callback_query_handler(lambda call: call.data.startswith("confirm_buy_"))
async def confirm_buy(call: types.CallbackQuery):
    # Извлекаем id товара и цену из callback_data
    product_id, price = call.data.split("_")[2], float(call.data.split("_")[3])
    user_id = call.from_user.id  # Идентификатор пользователя

    # Добавляем товар в корзину
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO carts (user_id, product_id, price) VALUES (%s, %s, %s)", (user_id, product_id, price))
    conn.commit()
    cursor.close()
    conn.close()

    await call.message.answer("Товар добавлен в корзину! Спасибо за покупку.")

# Хендлер для отмены покупки
@dp.callback_query_handler(lambda call: call.data == "cancel_buy")
async def cancel_buy(call: types.CallbackQuery):
    await call.message.answer("Вы отменили покупку.")

# Хендлер для отображения корзины
# Хендлер для отображения корзины
@dp.message_handler(lambda message: message.text == "Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()

    # Получаем товары из корзины с image_url
    cursor.execute("""
        SELECT g.name, g.price, g.image_url, c.id
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
            name, price, image_url, cart_item_id = item
            
            # Создаем inline кнопку "Удалить"
            remove_button = InlineKeyboardButton("Удалить", callback_data=f"remove_{cart_item_id}")

            # Создаем отдельный markup для каждого товара
            markup = InlineKeyboardMarkup().add(remove_button)

            # Отправляем изображение товара с описанием и кнопкой удаления
            await message.answer_photo(image_url, caption=f"{name} - {price} руб.", reply_markup=markup)
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
