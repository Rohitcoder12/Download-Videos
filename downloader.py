import os
import uuid
from yt_dlp import YoutubeDL

def download_video(url):
    """
    Download a video from the given URL using yt-dlp.
    Returns (video_path, title) on success, or None on failure.
    """
    # Unique temporary filename
    temp_id = str(uuid.uuid4())
    output = f"downloads/{temp_id}.%(ext)s"
    options = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            ext = info.get('ext', 'mp4')
            if not file_path.endswith(f".{ext}"):
                file_path += f".{ext}"
            title = info.get("title", "Downloaded Video")
            return file_path, title
    except Exception as e:
        print(f"[downloader error] {e}")
        return None
