import os
import uuid
from yt_dlp import YoutubeDL

def download_video(url):
    video_id = str(uuid.uuid4())
    output_path = f"{video_id}.%(ext)s"
    thumbnail_path = f"{video_id}.jpg"

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": output_path,
        "writethumbnail": True,
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "EmbedThumbnail"},
            {"key": "FFmpegMetadata"},
        ],
        "quiet": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Video")
            filename = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".mkv", ".mp4")
            if os.path.exists(filename):
                if os.path.exists(thumbnail_path):
                    return filename, thumbnail_path, title
                return filename, None, title
    except Exception as e:
        print(f"Download error: {e}")
    return None
