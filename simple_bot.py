import os
from dotenv import load_dotenv
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
API_HEYGEN = os.environ["API_HEYGEN"]
print(TOKEN, API_HEYGEN)

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Состояния (FSM - Finite State Machine)
class Form(StatesGroup):
    waiting_for_photo = State()
    waiting_for_caption = State()


# Command handler
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Привет, это Андрей. Отправь мне своё фото, чтобы найти себя в прошмандовках Азербайджана"
    )
    await state.set_state(Form.waiting_for_photo)


# Обработка фото
@dp.message(Form.waiting_for_photo, F.content_type == ContentType.PHOTO)
async def process_photo(message: Message, state: FSMContext):
    # Сохраняем file_id фото
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Теперь отправь текст для подписи.")
    await state.set_state(Form.waiting_for_caption)


# Если прислали не фото
@dp.message(Form.waiting_for_photo)
async def not_photo(message: Message):
    await message.answer("Это не фото! Отправь фото.")


# Обработка текста (подписи)
@dp.message(Form.waiting_for_caption)
async def process_caption(message: Message, state: FSMContext):
    # Достаем сохраненное фото
    data = await state.get_data()
    photo_id = data["photo"]
    caption = message.text

    # Отправляем фото с подписью
    await bot.send_photo(chat_id=message.chat.id, photo=photo_id, caption=caption)
    await state.clear()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
