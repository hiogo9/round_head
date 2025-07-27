from __future__ import annotations

import os
import sys
import time
import mimetypes
from pathlib import Path
from typing import Iterable, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

API_HEYGEN = os.environ["API_HEYGEN"]
DEFAULT_VOICE_ID = os.environ["HEYGEN_VOICE_ID"]
TIMEOUT = httpx.Timeout(30.0, read=60.0)
HEADERS = {"x-api-key": API_HEYGEN}
API_URL = "https://api.heygen.com"
UPLOAD_ULR = "https://upload.heygen.com"


class HeygenError(RuntimeError):
    pass


class HeygenProcessor:

    def __init__(self):
        pass

    def guess_mime(self, path: Path) -> str:
        mime, _ = mimetypes.guess_type(str(path))
        if mime not in ("image/jpeg", "image/png"):
            # default to jpeg; server accepts jpeg/png only
            return "image/jpeg"
        return mime

    def upload_talking_photo(
        self, client: httpx.Client, image_path: Path, mime: str
    ) -> str:
        with open(image_path, "rb") as f:
            data = f.read()
        r = client.post(
            f"{UPLOAD_ULR}/v1/talking_photo",
            headers={**HEADERS, "Content-Type": mime},
            content=data,
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            # try to display server message
            msg = r.text
            try:
                js = r.json()
                msg = js.get("message") or js.get("error") or msg
            except Exception:
                pass
            raise HeygenError(f"Upload failed: HTTP {r.status_code}: {msg}")
        
        js = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        tp_id = (
            (js.get("data") or {}).get("talking_photo_id")
            if isinstance(js, dict)
            else None
        )
        if not tp_id:
            tp_id = js.get("talking_photo_id") if isinstance(js, dict) else None
        if not tp_id:
            raise HeygenError(f"No talking_photo_id in response: {js}")
        print('talking_photo_id=',tp_id)
        print('talking_photo_all_json = ',r.json())
        return tp_id

    def create_video(
        self, client: httpx.Client, talking_photo_id: str, text: str|None, voice_id: str
    ) -> str:
        print(talking_photo_id)
        print(text)
        payload = {
            "dimension": {"width": 720, "height": 720},
            "video_inputs": [
                {
                    "character": {
                        "type": "talking_photo",
                        "talking_photo_id": talking_photo_id,
                        "talking_style": "expressive",
                        "expression": "happy",
                        "talking_photo_style": "square",
                        "scale": 1,
                        "offset": {"x": 0.0, "y": 0.0},
                    },
                    "voice": {
                        "type": "text",
                        "voice_id": voice_id,
                        "input_text": text[:1000],
                        "speed": 1,
                        "locale": "ru-RU",
                        "emotion": "Excited",
                    },
                    "background": {"type": "color", "value": "#0E0E12"},
                }
            ],
        }
        r = client.post(
            f"{API_URL}/v2/video/generate",
            headers=HEADERS,
            json=payload,
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            raise HeygenError(f"video.generate failed: HTTP {r.status_code}: {r.text}")
        j = r.json() or {}
        print(j)
        video_id = j["data"]["video_id"]
        if not video_id:
            raise HeygenError(f"No video_id in response: {j}")
        return video_id

    def get_video_url(self, client: httpx.Client, video_id: str) -> Optional[str]:
        # print('внутри ЗАПРОСА К ВИДЕО, video_id=', video_id)
        r = client.get(
            f"{API_URL}/v1/video_status.get",
            params={"video_id": video_id},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        j = r.json() or {}
        print(j)
        status = j["data"]["status"]
        if status == "completed":
            return j["data"]["video_url"]
        if status in {"failed", "error"}:
            # raise with details if present
            raise HeygenError(f"Render failed: {j}")
        return None

    def wait_and_download(
        self,
        client: httpx.Client,
        video_id: str,
        out_path: Path,
        delays: Iterable[float] = (3, 5, 8, 8, 8, 13, 21, 34, 55),
    ) -> None:
        url: Optional[str] = None
        for d in delays:
            time.sleep(d)
            url = self.get_video_url(client, video_id)
            if url:
                break
        if not url:
            raise HeygenError("Timeout: video is not ready")

        # download
        with client.stream("GET", url, timeout=TIMEOUT) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
