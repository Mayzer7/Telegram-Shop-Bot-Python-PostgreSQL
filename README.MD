# Telegram Shop Bot 🚀
![Image](https://github.com/user-attachments/assets/d39c0d06-717a-41a2-aa1a-b373d8034ad3)
Этот проект — современный, асинхронный телеграм-бот интернет-магазина, построенный на Aiogram 2.22. Он обеспечивает быстрый и удобный процесс покупок для пользователей, а также удобную систему управления товарами для администраторов.

Основной бот и обработчики команд работают асинхронно, что позволяет эффективно обрабатывать запросы без задержек. Вся информация хранится в базе данных, обеспечивая надёжное хранение данных и высокую скорость работы.

## Функционал

### Пользовательский бот (bot.py)
- Отображает клавиатуру с основными разделами: "Каталог", "Корзина", "Мои заказы", "Мой баланс".
- При нажатии на "Каталог" загружает список товаров из базы данных и отправляет их пользователю с описанием и изображением.

### Административный бот (admin.py)
- Позволяет администратору добавлять товары через телеграм.
- Запрашивает у администратора название, описание, количество и изображение товара.
- Сохраняет изображение в локальную папку `images/goods/`.
- Записывает ссылку на сохранённое изображение в базу данных.

## Установка и настройка

### 1. Установка зависимостей

Убедитесь, что у вас установлен Python 3 и необходимые зависимости:
```sh
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корневой папке проекта и добавьте в него:
```
BOT_TOKEN=your_telegram_bot_token
ADMIN_PASSWORD=your_admin_password

DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=your_db_port
```

### 3. Настройка базы данных

В PostgreSQL создайте базу данных `your_db_name` и таблицы:`:
```sql
-- Таблица пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    balance NUMERIC(10, 2) DEFAULT 0
);

-- Таблица товаров
CREATE TABLE goods (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    quantity INT NOT NULL DEFAULT 0,
    price NUMERIC(10, 2) NOT NULL,
    image_url TEXT
);

-- Таблица корзины
CREATE TABLE carts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES goods(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0)
);

-- Таблица заказов
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    total_price NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица элементов заказа
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    price NUMERIC(10, 2) NOT NULL,
    total_price NUMERIC(10, 2) NOT NULL
);
```

### 4. Запуск ботов

Запуск пользовательского бота:
```sh
python bot.py
```

Запуск административного бота:
```sh
python admin.py
```

## Как использовать

### Для пользователей:
1. Напишите `/start` боту.
2. Выберите "Каталог" и просмотрите список товаров.

### Для администраторов:
1. Напишите `/start` боту.
2. Введите команду `/add_product` и следуйте инструкциям.

## Структура проекта
```
📂 telegram-shop-bot
├── 📂 app
│   ├── 📄 bot.py        # Основной пользовательский бот
│   ├── 📄 admin.py      # Бот для добавления товаров
├── 📄 .env              # Файл с переменными окружения
├── 📄 .gitignore        # Файл исключения для Git
├── 📄 requirements.txt  # Список зависимостей
├── 📄 README.md         # Документация проекта
```

## Улучшения в будущем
- Сделать работу бота асинхронной с помощью библиотеки aiogram
- Добавление товара в корзину (создание корзины в бд) и её отображение.
- В разделе баланс реализовать пополнение баланса
- В разделе корзины реализовать форму оплаты
- Создание в бд таблицу моих заказов и их отображения.
- Написание тестов.

---

Этот бот позволит быстро и удобно управлять каталогом товаров и взаимодействовать с покупателями прямо в Telegram! 🚀

