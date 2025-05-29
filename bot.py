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

# --- Настройки ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN в .env")

AUTHORIZED_USERS = set()
user_data = {}

# --- Команда /start ---
async def start_handler(message: types.Message):
    chat_id = message.chat.id
    AUTHORIZED_USERS.add(chat_id)
    user_data[chat_id] = set()
    logger.info(f"Пользователь {chat_id} начал отслеживание")
    await message.answer("✅ Вы добавлены в прослеживание комменатриев!")

# --- Фоновая проверка совпадений ---
async def check_new_matches(bot: Bot):
    while True:
        try:
            tasks = []

            # --- Отправляем всем пользователям "Проверка началась..." ---
            for chat_id in AUTHORIZED_USERS.copy():
                task = asyncio.create_task(
                    bot.send_message(chat_id, '🔍 Проверка началась...')
                )
                tasks.append(task)

            await asyncio.gather(*tasks)  # Ждём, пока все получат стартовое сообщение
            tasks.clear()

            # --- Запуск парсера ---
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, run_parser)
            print(f"[DEBUG] Найдено совпадений: {len(matches)}")

            # --- Подготавливаем задачи для всех пользователей ---
            send_tasks = []
            user_has_new = {chat_id: False for chat_id in AUTHORIZED_USERS}

            for match in matches:
                asyncio.sleep(0.333)
                key = match["comment_link"]
                for chat_id in AUTHORIZED_USERS.copy():
                    if key not in user_data.get(chat_id, set()):
                        message = (
                            f"{match['text']}\n"
                            f"{match['comment_link']}\n"
                            f"Теги: {match['tags']}"
                        )
                        send_tasks.append(
                            bot.send_message(chat_id, message)
                        )
                        # Сохраняем, что пользователь получил это
                        user_data.setdefault(chat_id, set()).add(key)
                        user_has_new[chat_id] = True  # Указываем, что были новые совпадения

            # --- Параллельная отправка новых совпадений ---
            if send_tasks:
                await asyncio.gather(*send_tasks)
            send_tasks.clear()

            # --- Отправка ❌ Новых совпадений не найдено тем, кто ничего не получил ---
            no_matches_tasks = []
            for chat_id in AUTHORIZED_USERS.copy():
                if not user_has_new.get(chat_id, True):  # Если не было новых совпадений
                    no_matches_tasks.append(
                        bot.send_message(chat_id, '❌ Новых совпадений не найдено')
                    )

            # --- Параллельная отправка "нет совпадений" ---
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