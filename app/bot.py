import os
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

import asyncpg

async def get_db_connection():
    return await asyncpg.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )


# Состояния для процесса покупки товара
class PurchaseStates(StatesGroup):
    waiting_for_quantity = State()

# Состояние для пополнения баланса
class BalanceStates(StatesGroup):
    waiting_for_amount = State()

# Хендлер для команды /start
@dp.message_handler(Command("start"))
async def privet_command(message: types.Message):
    # Проверяем, есть ли пользователь в базе данных
    conn = await get_db_connection()
    user_exists = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", message.from_user.id)
    
    if not user_exists:  # Если пользователь еще не добавлен в базу данных
        await conn.execute("""
            INSERT INTO users (telegram_id, username, balance) 
            VALUES ($1, $2, $3)
        """, message.from_user.id, message.from_user.username, 0)  # Баланс по умолчанию = 0
    
    await conn.close()  # Закрываем соединение с базой данных

    # Создаем клавиатуру
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("Каталог"),
        KeyboardButton("Корзина"),
        KeyboardButton("Мои заказы"),
        KeyboardButton("Мой баланс")
    ]
    keyboard.add(*buttons)
    
    # Отправляем приветственное сообщение
    await message.answer("Привет, я бот интернет-магазина!", reply_markup=keyboard)

# Хендлер для отображения каталога товаров
@dp.message_handler(lambda message: message.text == "Каталог")
async def show_catalog(message: types.Message):
    conn = await get_db_connection()
    goods = await conn.fetch("SELECT id, name, description, quantity, price, image_url FROM goods")
    await conn.close()

    if goods:
        for product in goods:
            product_id, name, description, quantity, price, image_url = product
            product_message = f"Название: {name}\nОписание: {description}\nКоличество: {quantity}\nЦена: {price} руб."

            # Создаем inline кнопку "Купить"
            markup = InlineKeyboardMarkup()
            buy_button = InlineKeyboardButton("Купить 💵", callback_data=f"buy_{product_id}_{quantity}_{price}")
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
    # Проверяем, ввёл ли пользователь "отмена"
    if message.text.lower() == "отмена":
        await message.answer("Операция отменена.")
        await state.finish()
        return

    try:
        quantity = int(message.text)
        user_data = await state.get_data()
        product_id = user_data['product_id']
        product_quantity = user_data['product_quantity']
        product_price = user_data['product_price']

        # Проверяем, достаточно ли товара на складе
        if quantity > product_quantity:
            await message.answer(f"На складе нет такого количества товара. Доступно всего: {product_quantity}. Введите количество заново или напишите 'отмена'.")
        else:
            # Добавляем товар в корзину с указанным количеством
            conn = await get_db_connection()
            await conn.execute("""
                INSERT INTO carts (user_id, product_id, price, quantity) 
                VALUES ($1, $2, $3, $4)
            """, message.from_user.id, product_id, product_price, quantity)
            await conn.close()

            await message.answer(f"Товар успешно добавлен в корзину! {quantity} шт. по цене {product_price} руб. за штуку.")
            await state.finish()  # Завершаем процесс
    except ValueError:
        await message.answer("Пожалуйста, введите количество числом.")

# Хендлер для отображения корзины
@dp.message_handler(lambda message: message.text == "Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = await get_db_connection()

    # Получаем товары из корзины с image_url
    cart_items = await conn.fetch("""
        SELECT g.name, g.price, g.image_url, c.id, c.quantity
        FROM carts c
        JOIN goods g ON c.product_id = g.id
        WHERE c.user_id = $1
    """, user_id)

    await conn.close()

    if cart_items:
        await message.answer("🛒 Ваша корзина:")

        total_sum = 0  # Переменная для итоговой суммы

        # Добавляем товары в сообщение и создаем кнопки для удаления
        for item in cart_items:
            name, price, image_url, cart_item_id, quantity = item

            # Вычисляем итоговую цену товара
            total_price = price * quantity
            total_sum += total_price  # Добавляем к общей сумме

            # Создаем inline кнопку "Удалить"
            remove_button = InlineKeyboardButton("Удалить", callback_data=f"remove_{cart_item_id}")
            markup = InlineKeyboardMarkup().add(remove_button)

            # Отправляем изображение товара с описанием и кнопкой удаления
            await message.answer_photo(
                image_url, 
                caption=f"{name} - {price} руб. (Количество: {quantity})\nИтоговая цена: {total_price} руб.",
                reply_markup=markup
            )


        # Кнопка "Оформить заказ ✅"
        checkout_button = InlineKeyboardButton("Оформить заказ ✅", callback_data="checkout_order")
        checkout_markup = InlineKeyboardMarkup().add(checkout_button)

        # Отправляем итоговую сумму с кнопкой
        await message.answer(f"💰 Общая сумма заказа: {total_sum} руб.", reply_markup=checkout_markup)
    else:
        await message.answer("🛒 Ваша корзина пуста.")

# Хендлер для удаления товара из корзины
@dp.callback_query_handler(lambda call: call.data.startswith("remove_"))
async def remove_from_cart(call: types.CallbackQuery):
    cart_item_id = int(call.data.split("_")[1])  # Преобразуем в целое число

    # Удаляем товар из корзины
    conn = await get_db_connection()
    await conn.execute("DELETE FROM carts WHERE id = $1", cart_item_id)
    await conn.close()

    await call.message.answer("Товар удален из корзины.")
    # Обновляем корзину
    await show_cart(call.message)


# Хендлер для кнопки "Оформить заказ"
@dp.callback_query_handler(lambda c: c.data == "checkout_order")
async def process_checkout(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    conn = await get_db_connection()

    # Получаем баланс пользователя
    balance_row = await conn.fetchrow("SELECT balance FROM users WHERE telegram_id = $1", user_id)
    balance = balance_row["balance"] if balance_row else 0

    # Получаем товары из корзины
    cart_items = await conn.fetch("""
        SELECT g.id, g.name, g.price, c.quantity
        FROM carts c
        JOIN goods g ON c.product_id = g.id
        WHERE c.user_id = $1
    """, user_id)

    if not cart_items:
        await callback_query.answer("Ваша корзина пуста!")
        await conn.close()
        return

    # Рассчитываем общую сумму заказа
    total_price = sum(item["price"] * item["quantity"] for item in cart_items)

    # Проверяем, хватает ли баланса
    if balance < total_price:
        await callback_query.message.answer("❌ Недостаточно средств! Пополните баланс.")
        await callback_query.answer("❌ Недостаточно средств! Пополните баланс.")
        await conn.close()
        return

    # Уменьшаем баланс пользователя
    await conn.execute("UPDATE users SET balance = balance - $1 WHERE telegram_id = $2", total_price, user_id)

    # Создаём заказ
    order_row = await conn.fetchrow(
        "INSERT INTO orders (user_id, total_price) VALUES ($1, $2) RETURNING id",
        user_id, total_price
    )
    order_id = order_row["id"]

    # Добавляем товары в order_items
    for item in cart_items:
        await conn.execute(
            "INSERT INTO order_items (order_id, product_name, quantity, price, total_price) VALUES ($1, $2, $3, $4, $5)",
            order_id, item["name"], item["quantity"], item["price"], item["price"] * item["quantity"]
        )

    # Уменьшаем количество товаров в таблице goods
    for item in cart_items:
        await conn.execute(
            "UPDATE goods SET quantity = GREATEST(quantity - $1, 0) WHERE id = $2",
            item["quantity"], item["id"]
        )

    # Очищаем корзину
    await conn.execute("DELETE FROM carts WHERE user_id = $1", user_id)

    await conn.close()

    await callback_query.answer("✅ Заказ оформлен!")
    await callback_query.message.answer("Ваш заказ успешно оформлен! Спасибо за покупку.\nС важи скоро свяжется наш менеджер.\nПерейдите в раздел 'Мои заказы'.")

# Хендлер для кнопки "Мои заказы"
@dp.message_handler(lambda message: message.text == "Мои заказы")
async def show_orders(message: types.Message):
    user_id = message.from_user.id
    conn = await get_db_connection()

    # Получаем заказы пользователя
    orders = await conn.fetch(
        "SELECT id, total_price, created_at FROM orders WHERE user_id = $1 ORDER BY created_at ASC",
        user_id
    )

    if not orders:
        await message.answer("❌ У вас пока нет заказов.")
        await conn.close()
        return

    for order in orders:
        order_id = order["id"]
        total_price = order["total_price"]
        created_at = order["created_at"].strftime("%d.%m.%Y %H:%M")

        # Получаем товары для этого заказа
        items = await conn.fetch(
            "SELECT product_name, quantity, price FROM order_items WHERE order_id = $1",
            order_id
        )

        items_text = "\n".join(
            [f"📦 {item['product_name']} (x{item['quantity']}) - {item['price']} руб за 1шт." for item in items]
        )

        text = (f"📋 Заказ №{order_id} от {created_at}\n\n"
                f"{items_text}\n\n"
                f"💰 Итоговая сумма: {total_price} руб.")   

        await message.answer(text)

    await message.answer("👨🏻‍💻 ***По поводу срока выполнения заказа и доставки с вами свяжется менеджер\!***", parse_mode="MarkdownV2")

    await conn.close()

# Хендлер для кнопки "Мой баланс"
@dp.message_handler(lambda message: message.text == "Мой баланс")
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    conn = await get_db_connection()

    # Получаем баланс пользователя
    balance = await conn.fetchrow("SELECT COALESCE(balance, 0) FROM users WHERE telegram_id = $1", user_id)

    await conn.close()

    balance_value = balance[0] if balance else 0

    # Создаем inline-кнопку для пополнения
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("Пополнить баланс", callback_data="top_up_balance"))

    await message.answer(f"Ваш баланс: {balance_value} руб.", reply_markup=markup)

# Хендлер для нажатия на кнопку "Пополнить баланс"
@dp.callback_query_handler(lambda call: call.data == "top_up_balance")
async def top_up_balance(call: types.CallbackQuery):
    await call.message.answer("Введите сумму для пополнения или напишите 'отмена':")
    await BalanceStates.waiting_for_amount.set()

# Хендлер для ввода суммы пополнения
@dp.message_handler(state=BalanceStates.waiting_for_amount)
async def process_top_up_amount(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Операция пополнения отменена.")
        await state.finish()
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Введите положительное число.")
            return

        user_id = message.from_user.id
        conn = await get_db_connection()

        # Обновляем баланс
        await conn.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2", amount, user_id)
        await conn.close()

        await message.answer(f"Баланс успешно пополнен на {amount} руб.")
        await state.finish()

    except ValueError:
        await message.answer("Введите корректное число.")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
