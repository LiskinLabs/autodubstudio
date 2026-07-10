import os
import subprocess
from backend.utils.helpers import _pipeline_t, kill_process_tree, _safe_subprocess_env, get_python_exe

def _download_youtube(self, url, out_dir):
    """Download video from YouTube/TikTok/Vimeo URL using yt-dlp."""
    from urllib.parse import urlparse  # noqa: PLC0415

    import yt_dlp  # noqa: PLC0415

    # SSRF Protection: Validate URL scheme and domain
    parsed = urlparse(url)
    allowed_domains = [
        "youtube.com",
        "youtu.be",
        "www.youtube.com",
        "tiktok.com",
        "www.tiktok.com",
        "vimeo.com",
        "www.vimeo.com",
    ]
    if (
        parsed.scheme not in ["http", "https"]
        or parsed.hostname not in allowed_domains
    ):
        raise ValueError(
            f"URL domain '{parsed.hostname}' is not allowed or invalid scheme. Only YouTube, TikTok, and Vimeo are supported."
        )

    self.log_signal.emit(
        _pipeline_t("downloading_video", self.ui_language, url=url[:60])
    )
    ydl_opts = {
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [getattr(self, "source_lang", "en"), "en"],
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "postprocessors": [
            {
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
            }
        ],
    }

    cookie_file = os.path.join(os.path.dirname(__file__), "backend", "youtube_cookies.txt")
    if os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith(".mp4"):
                filepath = filepath.rsplit(".", 1)[0] + ".mp4"
            if os.path.exists(filepath):
                self.log_signal.emit(
                    _pipeline_t(
                        "downloaded",
                        self.ui_language,
                        name=os.path.basename(filepath),
                    )
                )
                return filepath
    except yt_dlp.utils.DownloadError as e:
        if (
            "Too Many Requests" in str(e)
            or "HTTP Error 429" in str(e)
            or "subtitles" in str(e).lower()
        ):
            self.log_signal.emit(
                "⚠️ YouTube rate limited subtitles (HTTP 429). Retrying without subtitles (will use Whisper instead)..."
            )
            # Fallback: Disable subtitle download and try again
            ydl_opts["writesubtitles"] = False
            ydl_opts["writeautomaticsub"] = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                info = ydl_fallback.extract_info(url, download=True)
                filepath = ydl_fallback.prepare_filename(info)
                if not filepath.endswith(".mp4"):
                    filepath = filepath.rsplit(".", 1)[0] + ".mp4"
                if os.path.exists(filepath):
                    self.log_signal.emit(
                        _pipeline_t(
                            "downloaded",
                            self.ui_language,
                            name=os.path.basename(filepath),
                        )
                    )
                    return filepath
        else:
            raise e

    raise RuntimeError(f"Failed to download: {url}")

