import os
from dotenv import load_dotenv
import logging
import httpx
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType, BufferedInputFile, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import VideoProcessor
import HeygenProcessor

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
API_HEYGEN = os.environ["API_HEYGEN"]
DEFAULT_VOICE_ID = os.environ["HEYGEN_VOICE_ID"]
TIMEOUT = httpx.Timeout(30.0, read=60.0)
HEADERS = {"x-api-key": API_HEYGEN}
API_URL = "https://api.heygen.com"
UPLOAD_ULR = "https://upload.heygen.com"
print(TOKEN, API_HEYGEN)

bot = Bot(token=TOKEN)
dp = Dispatcher()

TEMP_VIDEO_PATH = "simple.mp4"


# Состояния (FSM - Finite State Machine)
class Form(StatesGroup):
    waiting_for_photo = State()
    waiting_for_caption = State()
    sending_video = State()


# Command handler
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Привет, это Андрей. Отправь мне своё фото, чтобы найти себя в прошмандовках Азербайджана"
    )
    await state.set_state(Form.waiting_for_photo)


# Video handler
@dp.message(Command("video"))
async def video(message: Message, state: FSMContext) -> None:
    await message.answer("Пытаюсь отправить видео")
    with open(TEMP_VIDEO_PATH, "rb") as video_file:
        input_file = BufferedInputFile(
            file=video_file.read(), filename="circular_video.mp4"
        )
        await bot.send_video_note(chat_id=message.chat.id, video_note=input_file)
    # video_temporary = await VideoProcessor.VideoProcessor.process_video_to_circle(file_path=)


# Video handler
@dp.message(Command("circle_video"))
async def video_circle(message: Message, state: FSMContext) -> None:
    await message.answer("Пытаюсь отправить круглое видео")
    new_video_path = await VideoProcessor.VideoProcessor.process_video_to_circle(
        file_path=TEMP_VIDEO_PATH, output_path="circle_" + TEMP_VIDEO_PATH
    )
    with open(new_video_path, "rb") as video_file:
        input_file = BufferedInputFile(
            file=video_file.read(), filename="circular_video.mp4"
        )
        await bot.send_video_note(chat_id=message.chat.id, video_note=input_file)


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
    await message.answer("---берем загруженное фото---")
    # Достаем сохраненное фото
    data = await state.get_data()
    photo_id = data["photo"]
    caption = message.text

    photo_file = await bot.get_file(photo_id)
    if photo_file.file_path is None:
        await message.answer("Ошибка: не удалось получить путь к файлу фото")
        return
    photo_path = f"temp_photo_{photo_id}.jpg"

    await bot.download_file(photo_file.file_path, destination=photo_path)
    await message.answer("---грузим его на сервис нейронок---")

    # Создаем экземпляр процессора и HTTP-клиент
    processor = HeygenProcessor.HeygenProcessor()
    client = httpx.Client()

    video_path = None  # Инициализируем переменную для пути к видео
    try:
        await message.answer("---пупупу....---")

        # 1. Загружаем фото в Heygen
        mime = processor.guess_mime(Path(photo_path))
        talking_photo_id= None
        talking_photo_id = processor.upload_talking_photo(
            client, Path(photo_path), mime
        )
        await message.answer("---нейронка ПОШЛА---")

        # 2. Создаем видео (используем голос из .env)
        voice_id = os.environ.get("HEYGEN_VOICE_ID", "")
        if not voice_id:
            await message.answer("Ошибка: не настроен голосовой ID")
            return

        video_id = processor.create_video(
            client, talking_photo_id, caption, DEFAULT_VOICE_ID
        )
        await message.answer("---генерирует видиво---")
        

        # 3. Ждем и скачиваем результат

        video_path = f"result_{photo_id}.mp4"
        print(video_path)
        await message.answer("---ждем...=(---")
        processor.wait_and_download(client, video_id, Path(video_path))
        await message.answer("---жмем видосик в кругляху---")
        print('loaded video')
        # Отправляем видео пользователю
        # with open(video_path, "rb") as video_file:
        #     video_data = video_file.read()
        # await message.answer_video(
        #     video=BufferedInputFile(video_data, filename="result.mp4")
        # )
        new_video_path = None
        new_video_path = await VideoProcessor.VideoProcessor.process_video_to_circle(
            file_path=video_path, output_path="circle_" + video_path
        )
        with open(new_video_path, "rb") as video_file:
            input_file = BufferedInputFile(
                file=video_file.read(), filename="circular_video.mp4"
            )
            await bot.send_video_note(chat_id=message.chat.id, video_note=input_file)

    except HeygenProcessor.HeygenError as e:
        await message.answer(f"Ошибка Heygen: {str(e)}")
    except Exception as e:
        await message.answer(f"Неизвестная ошибка: {str(e)}")
    finally:
        # Удаляем временные файлы
        
        if os.path.exists(photo_path):
            os.remove(photo_path)
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if new_video_path and os.path.exists(new_video_path):
            os.remove(new_video_path)
        
        r = client.delete(
            f"{API_URL}/v2/photo_avatar/{talking_photo_id}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        j = r.json() or {}
        print(j)
        client.close()

    await state.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
