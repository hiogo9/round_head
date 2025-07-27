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
            "-vf",
            (
                # 1. Делаем квадрат
                "scale=w='min(iw,ih)':h='min(iw,ih)',"
                "crop=w=ih:h=ih,"
                "scale=512:512,"
                # 2. Создаем круглую маску
                "format=rgba,"
                "split[vid][alpha];"
                "[alpha]geq=lum=0:cb=0:cr=0,"
                "geq=a='if(gt(sqrt((X-256)^2+(Y-256)^2),256,255)',"
                "curves=psfile='color_curves.acv'[mask];"
                # 3. Накладываем маску
                "[vid][mask]alphamerge"
            ),
            "-c:v",
            "libvpx-vp9",  # Кодек с поддержкой прозрачности
            "-pix_fmt",
            "yuva420p",  # Формат с альфа-каналом
            "-auto-alt-ref",
            "0",
            output_path,
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error: {e}")
