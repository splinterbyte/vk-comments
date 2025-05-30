# bot.py

import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from parser import run_parser
import os
from dotenv import load_dotenv
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- Настройки ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN в .env")

AUTHORIZED_USERS = set()
user_data = {}

def get_start_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="/start"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

# --- Команда /start ---
async def start_handler(message: types.Message):
    if message.chat.id not in AUTHORIZED_USERS:
        chat_id = message.chat.id
        AUTHORIZED_USERS.add(chat_id)
        user_data[chat_id] = set()
        logger.info(f"Пользователь {chat_id} начал отслеживание")
        await message.answer("✅ Вы добавлены в отслеживание комменатриев!", reply_markup=get_start_keyboard())
    else:
        await message.answer("Вы уже добавлены в отслеживание!", reply_markup=get_start_keyboard())

# --- Команда /stop ---
async def stop_handler(message: types.Message):
    if message.chat.id in AUTHORIZED_USERS:
        AUTHORIZED_USERS.remove(message.chat.id)
        user_data.pop(message.chat.id, None)
        

# --- Фоновая проверка совпадений ---
# Где-то глобально или в хранилище
last_bot_message_id = {}  # chat_id -> message_id


async def check_new_matches(bot: Bot):
    while True:
        try:
            tasks = []
            start_message_ids = {}  # chat_id -> message_id (новые "Проверка началась...")
            
            # --- Удаление старого статусного сообщения (если есть) ---
            delete_old_tasks = []
            for chat_id in AUTHORIZED_USERS.copy():
                msg_id = last_bot_message_id.get(chat_id)
                if msg_id:
                    delete_old_tasks.append(bot.delete_message(chat_id, msg_id))
            
            if delete_old_tasks:
                await asyncio.gather(*delete_old_tasks, return_exceptions=True)

            # --- Отправляем всем пользователям "Проверка началась..." ---
            for chat_id in AUTHORIZED_USERS.copy():
                try:
                    message = await bot.send_message(
                        chat_id,
                        '🔍 Проверка началась...',
                        reply_markup=get_start_keyboard()
                    )
                    start_message_ids[chat_id] = message.message_id
                    # Обновляем ID текущего бот-сообщения
                    last_bot_message_id[chat_id] = message.message_id
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")

            # --- Запуск парсера ---
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, run_parser)
            print(f"[DEBUG] Найдено совпадений: {len(matches)}")

            # --- Подготавливаем задачи для всех пользователей ---
            send_tasks = []
            user_has_new = {chat_id: False for chat_id in AUTHORIZED_USERS}

            for match in matches:
                await asyncio.sleep(0.333)
                key = match["comment_link"]
                for chat_id in AUTHORIZED_USERS.copy():
                    if key not in user_data.get(chat_id, set()):
                        message_text = (
                            f"{match['text']}\n"
                            f"{match['comment_link']}\n"
                            f"Теги: {match['tags']}"
                        )
                        send_tasks.append(
                            bot.send_message(chat_id, message_text, reply_markup=get_start_keyboard())
                        )
                        user_data.setdefault(chat_id, set()).add(key)
                        user_has_new[chat_id] = True

            # --- Параллельная отправка новых совпадений ---
            if send_tasks:
                await asyncio.gather(*send_tasks)
            send_tasks.clear()

            # --- Отправка ❌ Новых совпадений не найдено тем, кто ничего не получил ---
            # --- Отправка ❌ Новых совпадений не найдено тем, кто ничего не получил ---
            no_matches_tasks = []
            delete_start_tasks = []

            for chat_id in AUTHORIZED_USERS.copy():
                if not user_has_new.get(chat_id, True):  # Не было новых совпадений
                    # Удалить начальное сообщение "Проверка началась..."
                    msg_id = start_message_ids.get(chat_id)
                    if msg_id:
                        delete_start_tasks.append(bot.delete_message(chat_id, msg_id))

                    # Отправить новое сообщение
                    try:
                        message = await bot.send_message(
                            chat_id,
                            '❌ Новых совпадений не найдено',
                            reply_markup=get_start_keyboard()
                        )
                        last_bot_message_id[chat_id] = message.message_id  # Сохраняем ID нового сообщения
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")

            # Выполняем удаление старых сообщений
            if delete_start_tasks:
                await asyncio.gather(*delete_start_tasks, return_exceptions=True)
            if no_matches_tasks:
                await asyncio.gather(*no_matches_tasks)

        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}")

        await asyncio.sleep(60)

# --- Основная функция запуска ---
async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start_handler, lambda m: m.text == "/start")

    # Запуск бота и фоновой задачи
    asyncio.create_task(check_new_matches(bot))
    logger.info("Бот запущен. Ожидание команды /start...")

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())