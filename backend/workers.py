import os

import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal


class YouTubeDownloadWorker(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url, download_dir):
        super().__init__()
        self.url = url
        self.download_dir = download_dir

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0)
                if total and total > 0:
                    percent = int((downloaded / total) * 100)
                    self.progress_signal.emit(percent)
                elif 'fragment_count' in d and 'fragment_index' in d:
                    if d['fragment_count'] > 0:
                        percent = int((d['fragment_index'] / d['fragment_count']) * 100)
                        self.progress_signal.emit(percent)
            except (KeyError, ValueError, TypeError):
                pass

    def run(self):
        import ipaddress
        import socket
        from urllib.parse import urlparse

        # SSRF Protection: Validate URL scheme and domain
        parsed = urlparse(self.url)
        allowed_domains = ["youtube.com", "youtu.be", "www.youtube.com", "tiktok.com", "www.tiktok.com", "vimeo.com", "www.vimeo.com"]
        if parsed.scheme not in ["http", "https"] or parsed.hostname not in allowed_domains:
            err_msg = f"URL domain '{parsed.hostname}' is not allowed. Only YouTube, TikTok, and Vimeo are supported."
            self.log_signal.emit(f"❌ {err_msg}")
            self.finished_signal.emit(False, err_msg)
            return

        # DNS rebinding protection: resolve hostname and verify no private IPs
        try:
            addrs = socket.getaddrinfo(parsed.hostname, None)
            for addr in addrs:
                ip_str = addr[4][0]
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    err_msg = f"URL '{parsed.hostname}' resolves to private IP ({ip_str}). Blocked."
                    self.log_signal.emit(f"❌ {err_msg}")
                    self.finished_signal.emit(False, err_msg)
                    return
        except Exception:
            pass  # DNS resolution failed — let yt-dlp handle the error naturally

        self.log_signal.emit(f"⏳ Скачивание: {self.url}")
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self.progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filename = ydl.prepare_filename(info)
                self.log_signal.emit(f"✅ Скачано: {os.path.basename(filename)}")
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, filename)
        except Exception as e:
            self.log_signal.emit(f"❌ Ошибка: {e}")
            self.finished_signal.emit(False, str(e))
