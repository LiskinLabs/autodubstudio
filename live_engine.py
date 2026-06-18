import queue

import numpy as np
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AudioCaptureThread(QThread):
    audio_signal = pyqtSignal(np.ndarray)

    def __init__(self, audio_source, sample_rate=16000, chunk_duration=3.0):
        super().__init__()
        self.audio_source = audio_source
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        self.is_running = True
        self.q = queue.Queue()

    def callback(self, indata, frames, time, status):
        if status:
            pass
        self.q.put(indata.copy())

    def run(self):
        try:
            import numpy as np
            import soundcard as sc
            import sounddevice as sd

            buffer = np.zeros((0, 1), dtype=np.float32)

            # If system sound or both, we use soundcard loopback
            is_system = "Системный" in self.audio_source or "Всё" in self.audio_source
            is_mic = "Микрофон" in self.audio_source or "Всё" in self.audio_source

            if is_system and not is_mic:
                speaker = sc.default_speaker()
                with speaker.recorder(samplerate=self.sample_rate, channels=1) as mic:
                    while self.is_running:
                        # Accumulate larger chunks (4 seconds) for better context and language detection
                        data = mic.record(numframes=int(self.sample_rate * 4.0))
                        if np.max(np.abs(data)) > 0.01:
                            self.audio_signal.emit(data.flatten())
            else:
                # Default to Mic via sounddevice (or both via mic array if stereo mix is enabled)
                with sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self.callback, dtype='float32'):
                    while self.is_running:
                        try:
                            data = self.q.get(timeout=0.1)
                            buffer = np.vstack((buffer, data))

                            if len(buffer) >= self.chunk_samples:
                                audio_data = buffer.flatten()
                                if np.max(np.abs(audio_data)) > 0.01:
                                    self.audio_signal.emit(audio_data)
                                buffer = np.zeros((0, 1), dtype=np.float32)
                        except queue.Empty:
                            continue
        except Exception as e:
            print(f"Audio error: {e}")

    def stop(self):
        self.is_running = False

class TranscribeThread(QThread):
    text_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, model_size, target_lang, translator_engine, gemini_key, deepseek_key, source_lang="en"):
        super().__init__()
        self.model_size = model_size
        self.target_lang = target_lang
        self.translator_engine = translator_engine
        self.gemini_key = gemini_key
        self.deepseek_key = deepseek_key
        self.source_lang = source_lang if source_lang != "auto" else None
        self.audio_queue = queue.Queue()
        self.is_running = True

    def process_audio(self, audio_data):
        self.audio_queue.put(audio_data)

    def translate_text(self, text):
        # We don't skip translation if engine is set
        if not text.strip() or "Без перевода" in self.translator_engine:
            return text

        try:
            prompt = f"Translate the following spoken text to {self.target_lang}. Only return the translation, nothing else. Text:\n{text}"
            if "Gemini" in self.translator_engine and self.gemini_key:
                from google import genai
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                return f"{text}\n---\n{response.text.strip()}"
            elif "DeepSeek" in self.translator_engine and self.deepseek_key:
                from openai import OpenAI
                client = OpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024
                )
                return f"{text}\n---\n{response.choices[0].message.content.strip()}"
            elif "Ollama" in self.translator_engine:
                import json
                import urllib.error
                import urllib.request
                url = "http://localhost:11434/api/generate"
                models_to_try = ["gemma4:e4b"]
                for model_name in models_to_try:
                    payload = json.dumps({
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": 0
                    }).encode('utf-8')
                    headers = {'Content-Type': 'application/json'}
                    req = urllib.request.Request(url, data=payload, headers=headers)
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            if response.status == 200:
                                result = json.loads(response.read().decode())
                                return f"{text}\n---\n{result.get('response', '').strip()}"
                    except Exception:
                        continue
                # If Ollama fails, fallback to Google Translate below
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='auto', target=self.target_lang).translate(text)
                return f"{text}\n---\n{translated}"
            else:
                from deep_translator import GoogleTranslator
                t_lang = self.target_lang
                translated = GoogleTranslator(source='auto', target=t_lang).translate(text)
                return f"{text}\n---\n{translated}"
        except Exception as e:
            self.log_signal.emit(f"⚠ Ошибка перевода: {e}")
            return text

    def run(self):
        try:
            import torch
            from faster_whisper import WhisperModel

            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"

            self.log_signal.emit(f"🔄 Загрузка Live модели Faster-Whisper ({self.model_size}) на {device}...")
            model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
            self.log_signal.emit("✅ Модель готова! Говорите/включите звук...")

            # If using translator engine, task="transcribe" to get original text first
            task_mode = "transcribe"
            if "Без перевода" not in self.translator_engine and self.target_lang == "en":
                task_mode = "translate" # Whisper natively translates TO EN, bypassing the LLM!

            while self.is_running:
                try:
                    audio_data = self.audio_queue.get(timeout=0.5)
                    segments, info = model.transcribe(
                        audio_data,
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=100),
                        condition_on_previous_text=False,
                        language=self.source_lang, # Принудительный язык или авто
                        task=task_mode
                    )

                    text = " ".join([segment.text for segment in segments])
                    text = text.strip()

                    if text:
                        translated = self.translate_text(text)
                        self.text_signal.emit(translated)

                except queue.Empty:
                    continue
        except Exception as e:
            self.error_signal.emit(f"Ошибка транскрибации: {str(e)}")

    def stop(self):
        self.is_running = False

class LiveSubtitleOverlay(QWidget):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, model_size="small", target_lang="ru", translator_engine="Google Translate (Free)", gemini_key="", deepseek_key="", audio_source="🎤 Микрофон", source_lang="en"):
        super().__init__()

        # Transparent background and always on top
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Place at bottom of screen
        screen = self.screen().geometry()
        width = int(screen.width() * 0.8)
        height = 150
        x = int((screen.width() - width) / 2)
        y = screen.height() - height - 100
        self.setGeometry(x, y, width, height)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)

        self.subtitle_label = QLabel("Ожидание речи...")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)

        # Styling for cinematic subtitles
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 180);
                padding: 15px 30px;
                border-radius: 15px;
            }
        """)
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        self.subtitle_label.setFont(font)

        self.layout.addWidget(self.subtitle_label)

        # Threads
        self.audio_thread = None
        self.transcribe_thread = None

        self.model_size = model_size
        self.target_lang = target_lang
        self.translator_engine = translator_engine
        self.gemini_key = gemini_key
        self.deepseek_key = deepseek_key
        self.audio_source = audio_source
        self.source_lang = source_lang

        self.clear_timer = QTimer()
        self.clear_timer.setInterval(5000)
        self.clear_timer.timeout.connect(self.clear_subtitle)

    def start_listening(self):
        self.transcribe_thread = TranscribeThread(
            self.model_size, self.target_lang, self.translator_engine,
            self.gemini_key, self.deepseek_key, self.source_lang
        )
        self.transcribe_thread.text_signal.connect(self.update_subtitle)
        self.transcribe_thread.log_signal.connect(self.log_signal.emit)
        self.transcribe_thread.error_signal.connect(self.error_signal.emit)
        self.transcribe_thread.start()

        self.audio_thread = AudioCaptureThread(audio_source=self.audio_source)
        self.audio_thread.audio_signal.connect(self.transcribe_thread.process_audio)
        self.audio_thread.start()

    def update_subtitle(self, text):
        if text:
            # Prevent overflow by keeping only the last 3-4 lines
            lines = text.split("\n")
            if len(lines) > 4:
                text = "\n".join(lines[-4:])
            self.subtitle_label.setText(text)
            self.clear_timer.start()

    def clear_subtitle(self):
        self.subtitle_label.setText("")

    def stop_listening(self):
        if self.audio_thread:
            self.audio_thread.stop()
            self.audio_thread.wait()
        if self.transcribe_thread:
            self.transcribe_thread.stop()
            self.transcribe_thread.wait()
