import os
import subprocess


class VideoProcessor:
    @staticmethod
    async def process_video_to_circle(
        file_path: str, output_path: str = "output.mp4",  bg_color="white"
    ) -> str:
        """
        Обрабатывает видео в круглый формат (1:1 с прозрачным фоном).

        :param file_path: Путь к исходному видео
        :param output_path: Путь для сохранения результата
        :return: Путь к обработанному видео
        """
        # Создаём маску в виде круга
        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            file_path,
        '-vf', f"scale=w=512:h=512:force_original_aspect_ratio=decrease,"
               f"pad=w=512:h=512:x=(ow-iw)/2:y=(oh-ih)/2:color={bg_color}",
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-movflags', '+faststart',
        '-y',  # Перезаписать если существует
            output_path,
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error: {e}")
