import os
import subprocess

class VideoProcessor:
    @staticmethod
    async def process_video_to_circle(file_path: str, output_path: str = "output.mp4") -> str:
        """
        Обрабатывает видео в круглый формат (1:1 с прозрачным фоном).
        
        :param file_path: Путь к исходному видео
        :param output_path: Путь для сохранения результата
        :return: Путь к обработанному видео
        """
        # Создаём маску в виде круга
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', file_path,
            '-vf', 
            'scale=w=min(iw\,ih):h=min(iw\,ih),crop=iw:ih,'
            'format=rgba,split[bg][fg];'
            '[bg]drawbox=color=black@0.0:replace=1:t=fill[bg];'
            '[bg][fg]overlay=(W-w)/2:(H-h)/2,'
            'format=rgba,'
            'geq=lum=0:cb=0:cr=0,'
            'colorkey=0x000000:0.01:0.1',
            '-c:v', 'libvpx-vp9',  # Кодек для прозрачности (WebM)
            '-pix_fmt', 'yuva420p',
            '-y',  # Перезаписать файл, если существует
            output_path
        ]
        
        try:
            subprocess.run(ffmpeg_cmd, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error: {e}")


