import os
import subprocess


class VideoProcessor:
    @staticmethod
    async def process_video_to_circle(
        file_path: str, output_path: str = "output.mp4"
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
           '-vf', "scale=512:512, drawbox=color=white@1:t=fill[bg]; [bg]overlay=(W-w)/2:(H-h)/2",
    '-c:v', 'libx264',
            "-y",  # Перезаписать, если файл существует
            output_path,
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error: {e}")
