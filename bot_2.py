import os
import logging
from io import BytesIO

import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType
from aiogram.utils import executor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HeygenClient:
    """
    Client for generating videos from photo avatars using the HeyGen API.
    """
    def __init__(self, api_key: str, base_url: str, voice_id: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.voice_id = voice_id

    def generate_video(self, talking_photo_id: str, script: str) -> bytes:
        """
        Generate a video from a photo avatar ID and script text.

        :param talking_photo_id: The ID of the pre-created photo avatar
        :param script: Text to convert to speech in the video
        :return: Raw video bytes
        """
        # Prepare request
        url_generate = f"{self.base_url}/v2/video/generate"
        headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            "video_inputs": [
                {
                    "character": {"type": "talking_photo", "talking_photo_id": talking_photo_id},
                    "voice": {"type": "text", "input_text": script, "voice_id": self.voice_id}
                }
            ]
        }

        # Request video creation
        resp = requests.post(url_generate, headers=headers, json=payload)
        resp.raise_for_status()
        video_id = resp.json().get('data', {}).get('video_id')
        if not video_id:
            raise RuntimeError('Failed to get video_id from HeyGen response')

        # Fetch generated video
        url_fetch = f"{self.base_url}/v2/video/fetch/{video_id}"
        resp2 = requests.get(url_fetch, headers={'X-Api-Key': self.api_key}, stream=True)
        resp2.raise_for_status()
        return resp2.content

class TelegramBot:
    """
    Telegram bot handling photo-to-video commands.
    """
    def __init__(self, token: str, heygen_client: HeygenClient):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(self.bot)
        self.heygen = heygen_client
        self.dp.register_message_handler(self.handle_photo, content_types=ContentType.PHOTO)

    async def handle_photo(self, message: types.Message):
        """
        Handle '/generate' command: expect photo with caption as script.

        :param message: Incoming Telegram message containing photo + caption
        """
        script = message.caption
        if not script:
            await message.reply("Пожалуйста, отправьте фото с текстом в подписи.")
            return

        # Save photo to temp file
        photo = message.photo[-1]
        download_path = f"temp_{photo.file_id}.jpg"
        await photo.download(destination_file=download_path)
        logger.info(f"Image downloaded to {download_path}")

        try:
            # Use photo file name as talking_photo_id for simplicity
            talking_photo_id = os.path.splitext(os.path.basename(download_path))[0]
            video_bytes = self.heygen.generate_video(talking_photo_id, script)

            # Send video
            video_io = BytesIO(video_bytes)
            video_io.name = "output.mp4"
            await message.reply_video(video=video_io)
        except Exception as e:
            logger.error(f"Error: {e}")
            await message.reply("Не удалось сгенерировать видео.")
        finally:
            if os.path.exists(download_path):
                os.remove(download_path)

    def run(self):
        """
        Start the Telegram polling loop.
        """
        executor.start_polling(self.dp, skip_updates=True)

if __name__ == '__main__':
    load_dotenv()

    TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
    HEYGEN_API_KEY = os.getenv('API_HEYGEN')
    HEYGEN_API_URL = os.getenv('HEYGEN_API_URL', 'https://api.heygen.com')
    HEYGEN_VOICE_ID = os.getenv('HEYGEN_VOICE_ID')

    if not all([TELEGRAM_TOKEN, HEYGEN_API_KEY, HEYGEN_VOICE_ID]):
        logger.error("Missing environment variables. Please set TELEGRAM_TOKEN, HEYGEN_API_KEY, and HEYGEN_VOICE_ID.")
        exit(1)

    client = HeygenClient(api_key=HEYGEN_API_KEY, base_url=HEYGEN_API_URL, voice_id=HEYGEN_VOICE_ID)
    bot = TelegramBot(token=TELEGRAM_TOKEN, heygen_client=client)
    bot.run()
