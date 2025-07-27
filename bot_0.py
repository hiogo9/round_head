import asyncio, os, tempfile, uuid, json, math, shutil, sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
HEYGEN_KEY = os.environ["API_HEYGEN"]
DEFAULT_VOICE_ID = os.environ.get("HEYGEN_VOICE_ID") or ""

API_BASE = "https://api.heygen.com"
UPLOAD_BASE = "https://upload.heygen.com"
TIMEOUT = httpx.Timeout(30.0, read=60.0)
HEADERS = {"X-Api-Key": HEYGEN_KEY}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# --- простое состояние на словаре (без БД) ---
USER_CTX: dict[int, dict] = {}

@dataclass
class HeygenResult:
    video_id: str
    video_url: Optional[str] = None


async def ffmpeg_square_640(input_path: Path, output_path: Path) -> None:
    """Простой рескейл 720→640, 25 fps, H.264 Baseline + AAC"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", "scale=640:640",
        "-r", "25",
        "-c:v", "libx264",
        "-profile:v", "baseline", "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err.decode('utf-8', 'ignore')}")


async def pick_ru_voice(client: httpx.AsyncClient) -> Optional[str]:
    """Выбирает voice_id с поддержкой ru, используя корректную схему ответов API.
    /v2/voices/locales → { data: { locales: [...] } }
    /v2/voices          → { voices: [...] }
    """
    if DEFAULT_VOICE_ID:
        return DEFAULT_VOICE_ID

    # 1) Получаем локали и собираем ru-набор
    resp = await client.get(f"{API_BASE}/v2/voices/locales", headers=HEADERS)
    resp.raise_for_status()
    j = resp.json() or {}
    print(j)
    locales = (j.get("data") or {}).get("locales") or []
    ru_locales = {loc.get("locale") for loc in locales
                  if isinstance(loc, dict) and "ru" in (loc.get("locale") or "").lower()}

    # 2) Получаем список голосов
    resp = await client.get(f"{API_BASE}/v2/voices", headers=HEADERS)
    resp.raise_for_status()
    j = resp.json() or {}
    voices = j.get("voices") or []

    # 2a) Сначала — голоса с явной поддержкой локалей и пересечением с ru
    for v in voices:
        if not isinstance(v, dict):
            continue
        if v.get("support_locale"):
            v_locs = {l.get("locale") for l in (v.get("locales") or []) if isinstance(l, dict)}
            if v_locs & ru_locales:
                return v.get("voice_id")

    # 2b) Затем — по языку/имени
    for v in voices:
        if not isinstance(v, dict):
            continue
        lang = (v.get("language") or "").lower()
        name = (v.get("name") or "").lower()
        if "russian" in lang or lang == "ru" or "russian" in name:
            return v.get("voice_id")

    # 2c) Фолбэк — первый доступный
    return voices[0].get("voice_id") if voices else None


async def upload_talking_photo(client: httpx.AsyncClient, content: bytes, mime: str) -> str:
    r = await client.post(f"{UPLOAD_BASE}/v1/talking_photo",
                          headers={**HEADERS, "Content-Type": mime},
                          content=content)
    r.raise_for_status()
    data = r.json()
    tp_id = data.get("talking_photo_id") or data.get("id") or ""
    if not tp_id:
        raise RuntimeError("No talking_photo_id in response")
    return tp_id  # /v1 endpoint, быстрый путь. ([docs.heygen.com](https://docs.heygen.com/discuss/676308cbe4fd890041128d27?utm_source=chatgpt.com))


async def create_video(client: httpx.AsyncClient, talking_photo_id: str, text: str, voice_id: str) -> HeygenResult:
    payload = {
        "dimension": {"width": 720, "height": 720},
        "title": f"tg-{uuid.uuid4()}",
        "callback_id": str(uuid.uuid4()),
        "video_inputs": [{
            "character": {
                "type": "talking_photo",
                "talking_photo_id": talking_photo_id,
                "talking_style": "expressive",
                "expression": "happy",
                "talking_photo_style": "square",
                "scale": 1.1,
                "offset": {"x": 0.0, "y": 0.0},
            },
            "voice": {
                "type": "text",
                "voice_id": voice_id,
                "input_text": text[:2000],  # некоторые инстансы валидируют на 2000 симв. ([docs.heygen.com](https://docs.heygen.com/discuss/674292a5124fe50018a3b207?utm_source=chatgpt.com))
                "speed": 1.3,
                "locale": "ru-RU",
                "emotion": "Excited"
            },
            "background": {"type": "color", "value": "#0E0E12"}
        }]
    }
    r = await client.post(f"{API_BASE}/v2/video/generate", headers=HEADERS, json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        # пробрасываем текст ошибки пользователю
        raise RuntimeError(f"HeyGen error {r.status_code}: {r.text}")
    data = r.json()
    vid = data.get("video_id") or data.get("id")
    if not vid:
        raise RuntimeError("No video_id returned")
    return HeygenResult(video_id=vid)


async def get_video_url(client: httpx.AsyncClient, video_id: str) -> Optional[str]:
    # URL истекает через 7 дней; при повторном запросе выдаётся новый. ([docs.heygen.com](https://docs.heygen.com/reference/video-status?utm_source=chatgpt.com), [docs.heygen.com](https://docs.heygen.com/discuss/67361ac3ca7398002a62316c?utm_source=chatgpt.com))
    r = await client.get(f"{API_BASE}/v1/video_status.get", params={"video_id": video_id}, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    status = (data.get("status") or "").lower()
    if status == "completed":
        return data.get("video_url")
    if status in {"failed", "error"}:
        raise RuntimeError(f"Render failed: {data}")
    return None


@dp.message(CommandStart())
async def on_start(m: Message):
    USER_CTX[m.from_user.id] = {"stage": "await_photo"}
    await m.answer(
        "Привет! Пришли портретное фото (JPG/PNG, одно лицо). "
        "После этого я попрошу текст для озвучки."
    )


@dp.message(F.photo | F.document)
async def on_photo(m: Message):
    ctx = USER_CTX.setdefault(m.from_user.id, {})
    if ctx.get("stage") not in {None, "await_photo"}:
        return
    # вытаскиваем файл
    file = None
    is_doc = False
    if m.photo:
        file = await bot.get_file(m.photo[-1].file_id)
    elif m.document:
        is_doc = True
        file = await bot.get_file(m.document.file_id)
    if not file:
        return await m.reply("Не нашёл файл. Пришли фото ещё раз.")

    # загружаем байты
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content = resp.content

    # MIME
    mime = "image/jpeg"
    if is_doc and m.document.mime_type:
        mime = m.document.mime_type
    elif file.file_path and file.file_path.endswith(".png"):
        mime = "image/png"

    ctx["photo_bytes"] = content
    ctx["photo_mime"] = mime
    ctx["stage"] = "await_text"
    await m.reply("Фото получил. Теперь пришли **текст** для озвучки (25–60 слов).", parse_mode="Markdown")


@dp.message(F.text)
async def on_text(m: Message):
    ctx = USER_CTX.setdefault(m.from_user.id, {})
    if ctx.get("stage") != "await_text":
        return
    text = m.text.strip()
    if not text:
        return await m.reply("Пустой текст. Пришли нормальный текст, пожалуйста.")

    await m.reply("Генерирую видео… Обычно это 1–3 минуты.")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # выбрать голос
        voice_id = await pick_ru_voice(client)
        if not voice_id:
            return await m.reply("Не нашёл голос для TTS. Попробуй позже.")

        # загрузить talking photo
        try:
            tp_id = await upload_talking_photo(client, ctx["photo_bytes"], ctx["photo_mime"])
        except Exception as e:
            return await m.reply("Не вышло загрузить фото в HeyGen. Попробуй другое фото.")
        # создать видео
        try:
            res = await create_video(client, tp_id, text, voice_id)
        except Exception as e:
            # типичные причины: лимиты, модерация, неверный voice_id. ([docs.heygen.com](https://docs.heygen.com/reference/limits?utm_source=chatgpt.com), [docs.heygen.com](https://docs.heygen.com/reference/video-status?utm_source=chatgpt.com))
            return await m.reply(f"Ошибка генерации в HeyGen: {e}")

        # ждать готовности (поллинг с backoff; можно заменить на вебхуки)
        url = None
        for delay in (3, 5, 8, 13, 21, 34):
            await asyncio.sleep(delay)
            try:
                url = await get_video_url(client, res.video_id)
            except Exception as e:
                return await m.reply(f"Ошибка получения статуса: {e}")
            if url:
                break
        if not url:
            return await m.reply("Слишком долго генерируется. Попробуй позже.")

        # скачать видео
        with tempfile.TemporaryDirectory() as td:
            tmp_in = Path(td) / "in.mp4"
            tmp_out = Path(td) / "out_640.mp4"
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(tmp_in, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)

            # конвертация в кружок (квадрат 640×640, baseline)
            try:
                await ffmpeg_square_640(tmp_in, tmp_out)
            except Exception as e:
                return await m.reply(f"Ошибка ffmpeg: {e}")

            # отправка как video note (по URL нельзя). ([hackage.haskell.org](https://hackage.haskell.org/package/telegram-bot-api/docs/Telegram-Bot-API-Methods-SendVideoNote.html?utm_source=chatgpt.com))
            with open(tmp_out, "rb") as f:
                await bot.send_video_note(chat_id=m.chat.id, video_note=f, length=640)

    ctx.clear()
    await m.reply("Готово! Хочешь сделать ещё один клип? Пришли новое фото.")


def main():
    # Быстрая проверка наличия ffmpeg
    if shutil.which("ffmpeg") is None:
        print("ffmpeg не найден в PATH", file=sys.stderr)
        sys.exit(1)
    dp.run_polling(bot)


if __name__ == "__main__":
    main()