import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
API_HEYGEN = os.environ["API_HEYGEN"]
print(TOKEN, API_HEYGEN)


button = KeyboardButton(text="Example button")



dp = Dispatcher()


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer("Prive Andrey ti ochen ymny chel")


# Run the bot
async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
