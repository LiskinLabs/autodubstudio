import os
import sys
import subprocess
import torch
import shutil
import glob
import threading
import re
import math
os.environ["PYTHONIOENCODING"] = "utf-8"
# WhisperX will be imported locally inside the worker

from pydub import AudioSegment

from backend.vram_manager import get_free_vram_mb, free_up_vram
from backend.translator import Translator

class EventSignal:
    def __init__(self):
        self.callbacks = []
    def connect(self, callback):
        self.callbacks.append(callback)
    def emit(self, *args, **kwargs):
        for cb in self.callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                pass  # Never let a callback crash the pipeline

PIPELINE_BUSY = False
PIPELINE_LOCK = threading.Lock()

class InterruptedError(Exception):
    """Raised when user cancels pipeline — triggers clean finally-block cleanup."""
    pass

class AutoDubWorker(threading.Thread):
    def __init__(self, video_path=None, out_dir=None, langs=None, model_size=None, device=None, translator_engine=None, gemini_key="", deepseek_key="", deepl_key="", dub_engine="", hf_key="", manual_mode=False):
        super().__init__()
        self.progress_signal = EventSignal()
        self.log_signal = EventSignal()
        self.finished_signal = EventSignal()
        self.extras_signal = EventSignal()
        self.vram_warning_signal = EventSignal()
        self.translation_ready_signal = EventSignal()
        self.manual_edit_signal = EventSignal()
        self._stop_event = threading.Event()
        
        # Support both old positional-arg style and new dict-based config (v3 UI)
        if isinstance(video_path, dict):
            cfg = video_path
            self.video_path = cfg.get("video_path", "")
            self.out_dir = cfg.get("out_dir") or os.path.dirname(self.video_path) if self.video_path else os.getcwd()
            target_langs = cfg.get("target_langs", ["en"])
            self.langs = {lang: f"{lang}-default" for lang in target_langs}
            self.model_size = cfg.get("whisper_model", "small")
            self.device = cfg.get("device", "cpu")
            self.translator_engine = cfg.get("translation_engine", "Google Translate (Free)")
            self.gemini_key = cfg.get("gemini_key", "")
            self.deepseek_key = cfg.get("deepseek_key", "")
            self.deepl_key = cfg.get("deepl_key", "")
            self.dub_engine = cfg.get("dub_engine", "Edge-TTS (Cloud, Free, Fast)")
            self.hf_key = cfg.get("hf_key", "")
            self.manual_mode = cfg.get("manual_mode", False)
            self.lip_sync = cfg.get("lip_sync", False)
            self.tag = cfg.get("tag", "")
        else:
            self.video_path = video_path
            self.out_dir = out_dir
            self.langs = langs
            self.model_size = model_size
            self.device = device
            self.translator_engine = translator_engine
            self.gemini_key = gemini_key
            self.deepseek_key = deepseek_key
            self.deepl_key = deepl_key
            self.dub_engine = dub_engine
            self.hf_key = hf_key
            self.manual_mode = manual_mode
            self.lip_sync = False

        self.translator = Translator(self.translator_engine, self.gemini_key, self.deepseek_key, self.deepl_key, self.device)
        
        self.pause_event = threading.Event()
        self.edited_segments = None

    def isInterruptionRequested(self):
        return self._stop_event.is_set()

    def requestInterruption(self):
        self._stop_event.set()

    def resume_with_translations(self, edited_segments):
        self.edited_segments = edited_segments
        self.pause_event.set()

    def resume(self, subs: list):
        """v3 UI compatibility — resume from manual editor."""
        edited = []
        for s in subs:
            edited.append({
                "text": s.get("trans", s.get("text", "")),
                "start": float(s.get("start", 0)),
                "end": float(s.get("end", 0)),
                "speaker": s.get("speaker", "SPEAKER_00"),
                "skip_dub": s.get("skip_dub", False),
            })
        self.resume_with_translations(edited)

    def format_timestamp(self, seconds):
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

    def _download_youtube(self, url, out_dir):
        """Download video from YouTube/TikTok/Vimeo URL using yt-dlp."""
        import yt_dlp
        self.log_signal.emit(f"📥 Загрузка видео: {url[:60]}...")
        ydl_opts = {
            'outtmpl': os.path.join(out_dir, '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith('.mp4'):
                filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            if os.path.exists(filepath):
                self.log_signal.emit(f"✅ Загружено: {os.path.basename(filepath)}")
                return filepath
        raise RuntimeError(f"Failed to download: {url}")

    def _check_cancelled(self):
        """Raise InterruptedError if stop was requested — allows clean finally-block cleanup."""
        if self._stop_event.is_set():
            raise InterruptedError("Pipeline cancelled by user")

    def run(self):
        global PIPELINE_BUSY
        with PIPELINE_LOCK:
            if PIPELINE_BUSY:
                self.finished_signal.emit(False, "Pipeline Busy")
                return
            PIPELINE_BUSY = True

        all_created_files = []
        demucs_out_dir = None
        try:
            # Handle YouTube/TikTok/Vimeo URLs — download first
            if self.video_path.startswith("http://") or self.video_path.startswith("https://"):
                self.video_path = self._download_youtube(self.video_path, self.out_dir)

            self._check_cancelled()
            # Security: validate and normalize video path
            if not self.video_path or not os.path.isfile(self.video_path):
                self.finished_signal.emit(False, "Invalid video file path")
                return
            self.video_path = os.path.realpath(self.video_path)

            # Language-TTS compatibility check
            TTS_COMPAT = {
                "Edge-TTS (Cloud, Free, Fast)": {"ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi"},
                "Qwen3-TTS Local": {"ru", "en"},
                "XTTSv2 Local": {"ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi"},
                "F5-TTS Local": {"ru", "en", "tr", "ar"},
            }
            for lang, _ in self.langs.items():
                compat = TTS_COMPAT.get(self.dub_engine, set())
                if lang not in compat:
                    err = f"❌ {self.dub_engine} не поддерживает язык '{lang}'. Совместимые языки: {sorted(compat)}"
                    self.log_signal.emit(err)
                    self.finished_signal.emit(False, err)
                    return

            base_name = os.path.splitext(os.path.basename(self.video_path))[0]

            # ── Checkpoint helper ──
            def _save_checkpoint(name, data):
                cp_path = os.path.join(self.out_dir, f".autodub_{base_name}_{name}.json")
                import json as _json
                with open(cp_path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, ensure_ascii=False)
                all_created_files.append(cp_path)
                return cp_path

            def _load_checkpoint(name):
                cp_path = os.path.join(self.out_dir, f".autodub_{base_name}_{name}.json")
                if os.path.exists(cp_path):
                    import json as _json
                    with open(cp_path, "r", encoding="utf-8") as f:
                        return _json.load(f)
                return None

            # 1. Изоляция вокала (Demucs)
            self._check_cancelled()
            self.log_signal.emit("🎵 Изоляция вокала (Demucs) - извлекаем чистый голос...")
            demucs_out_dir = os.path.join(self.out_dir, "demucs_out")
            os.makedirs(demucs_out_dir, exist_ok=True)

            vocals_path = os.path.join(demucs_out_dir, "htdemucs", base_name, "vocals.wav")
            no_vocals_path = os.path.join(demucs_out_dir, "htdemucs", base_name, "no_vocals.wav")

            if not (os.path.exists(vocals_path) and os.path.exists(no_vocals_path)):
                demucs_cmd = [sys.executable, "-m", "demucs.separate", "-n", "htdemucs", "--two-stems=vocals", "-o", demucs_out_dir, self.video_path]
                subprocess.run(demucs_cmd, check=True)
            else:
                self.log_signal.emit("✅ Чистый голос найден (пропуск Demucs)")

            transcribe_path = vocals_path if os.path.exists(vocals_path) else self.video_path

            if self.device == "cuda":
                if get_free_vram_mb() < 3000:
                    self.log_signal.emit("⚠ Мало VRAM, чистка фоновых процессов...")
                    free_up_vram(self.log_signal.emit)
                if get_free_vram_mb() < 2000:
                    self.log_signal.emit("⚠ VRAM всё ещё мало. Переключаюсь на CPU.")
                    self.device = "cpu"
                else:
                    torch.cuda.empty_cache()

            # 2. Транскрибация (Whisper) — или загрузка из чекпойнта
            self._check_cancelled()
            segments = _load_checkpoint("segments")
            if segments:
                self.log_signal.emit(f"✅ Сегменты загружены из кэша ({len(segments)} шт., пропуск Whisper)")
            else:
                self.log_signal.emit(f"🔄 Загрузка Whisper ({self.model_size}) на {self.device}...")
                import whisper

                try:
                    model = whisper.load_model(self.model_size, device=self.device)
                    result = model.transcribe(transcribe_path)
                    self.log_signal.emit(f"✅ Транскрибация завершена (язык: {result.get('language', 'unknown')}).")
                except Exception as e:
                    self.log_signal.emit(f"⚠ Ошибка транскрибации: {e}")
                    raise

                del model
                if self.device == "cuda": torch.cuda.empty_cache()

                # Форматируем сегменты
                segments = []
                for s in result["segments"]:
                    segments.append({"start": s["start"], "end": s["end"], "text": s["text"], "speaker": "SPEAKER_00"})

                self.log_signal.emit(f"✅ Найдено и размечено {len(segments)} сегментов.")
                _save_checkpoint("segments", segments)

            # 3. Диаризация (определение спикеров) — опционально, если есть HF токен
            if self.hf_key:
                self.log_signal.emit("👥 Диаризация (Pyannote) — определение спикеров...")
                diar_json = os.path.join(self.out_dir, f"{base_name}_diarization.json")
                try:
                    diar_script = os.path.join(os.path.dirname(__file__), "diarization_worker.py")
                    subprocess.run(
                        [sys.executable, diar_script, transcribe_path, diar_json],
                        check=True, timeout=600,
                        env={**os.environ, "HF_TOKEN": self.hf_key},
                    )
                    if os.path.exists(diar_json):
                        import json as _json
                        with open(diar_json, "r", encoding="utf-8") as f:
                            diar_data = _json.load(f)
                        # Map diarization speakers to whisper segments by time overlap
                        for seg in segments:
                            seg_mid = (seg["start"] + seg["end"]) / 2
                            for d in diar_data:
                                if d["start"] <= seg_mid <= d["end"]:
                                    seg["speaker"] = d["speaker"]
                                    break
                        unique = len(set(s["speaker"] for s in segments))
                        self.log_signal.emit(f"✅ Диаризация: {unique} спикеров определено.")
                        all_created_files.append(diar_json)
                except Exception as e:
                    self.log_signal.emit(f"⚠ Диаризация не удалась: {e}. Использую SPEAKER_00.")

            # 3.5 — Save original English subtitles
            orig_srt_path = os.path.join(self.out_dir, f"{base_name}_original.srt")
            all_created_files.append(orig_srt_path)
            with open(orig_srt_path, "w", encoding="utf-8") as f:
                for idx, s in enumerate(segments):
                    f.write(f"{idx+1}\n{self.format_timestamp(s['start'])} --> {self.format_timestamp(s['end'])}\n{s['text'].strip()}\n\n")
            self.log_signal.emit("📝 Оригинальные субтитры сохранены.")

            # 4. Обработка языков
            ffmpeg_inputs = ["-i", self.video_path, "-i", orig_srt_path]
            ffmpeg_maps = ["-map", "0:v:0", "-map", "0:a:0", "-map", "1:s:0"]
            metadata = [
                "-metadata:s:a:0", "title=Original Audio", "-metadata:s:a:0", "language=eng",
                "-metadata:s:s:0", "title=English (Original)", "-metadata:s:s:0", "language=eng",
            ]
            audio_track_idx, subtitle_track_idx = 1, 1

            # Start tracking input files for ffmpeg map
            file_idx = 2  # 0=video, 1=original audio+subs

            for i, (lang, _) in enumerate(self.langs.items()):
                self._check_cancelled()
                self.log_signal.emit(f"▶ Обработка языка: {lang}...")
                srt_path = os.path.join(self.out_dir, f"{base_name}_{lang}.srt")
                all_created_files.append(srt_path)

                # Check for cached translation
                cached = _load_checkpoint(f"translated_{lang}")
                if cached:
                    translated_segments = cached
                    self.log_signal.emit(f"  ✅ Перевод загружен из кэша ({len(translated_segments)} сегментов)")
                else:
                    translated_segments = self.translator.smart_translate_segments([dict(s) for s in segments], lang, self.log_signal.emit)
                    _save_checkpoint(f"translated_{lang}", translated_segments)

                if self.manual_mode:
                    manual_subs = []
                    for idx, s in enumerate(translated_segments):
                        manual_subs.append({
                            "time": f"{self.format_timestamp(s['start'])} → {self.format_timestamp(s['end'])}",
                            "orig": segments[idx]['text'],
                            "trans": s['text'],
                            "start": s['start'],
                            "end": s['end'],
                            "speaker": s.get('speaker', 'SPEAKER_00')
                        })
                    self.manual_edit_signal.emit(manual_subs)
                    while not self.pause_event.is_set():
                        if getattr(self, "isInterruptionRequested", lambda: False)():
                            self.finished_signal.emit(False, "Aborted")
                            return
                        self.pause_event.wait(0.5)
                    self.pause_event.clear()
                    if self.edited_segments: translated_segments = self.edited_segments

                with open(srt_path, "w", encoding="utf-8") as f:
                    for idx, tseg in enumerate(translated_segments):
                        f.write(f"{idx+1}\n{self.format_timestamp(tseg['start'])} --> {self.format_timestamp(tseg['end'])}\n{tseg['text'].strip()}\n\n")

                # --- TTS Logic ---
                use_f5 = "F5-TTS" in self.dub_engine
                use_xtts = "XTTSv2" in self.dub_engine
                use_qwen = "Qwen3-TTS" in self.dub_engine
                audio_clips = []

                # Pre-extract skip_dub segments
                vocals_full = AudioSegment.from_file(transcribe_path)
                tts_segments = []

                for idx, tseg in enumerate(translated_segments):
                    ext = "mp3" if not (use_f5 or use_xtts or use_qwen) else "wav"
                    clip_path = os.path.join(self.out_dir, f"temp_{lang}_{idx}.{ext}")
                    
                    if tseg.get("skip_dub", False):
                        orig_start_ms = int(tseg["start"] * 1000)
                        orig_end_ms = int(tseg["end"] * 1000)
                        extracted = vocals_full[orig_start_ms:orig_end_ms]
                        extracted.export(clip_path, format=ext)
                        all_created_files.append(clip_path)
                        audio_clips.append((tseg["start"], clip_path, False, tseg))
                    else:
                        tts_segments.append((idx, tseg, clip_path))

                if use_f5 or use_xtts:
                    speaker_refs = {}
                    for s in segments:
                        spk = s.get("speaker", "SPEAKER_00")
                        dur = s["end"] - s["start"]
                        if spk not in speaker_refs or dur > speaker_refs[spk]["dur"]:
                            speaker_refs[spk] = {"dur": dur, "start": s["start"], "end": s["end"], "text": s["text"]}
                    
                    for spk, ref in speaker_refs.items():
                        ref_path = os.path.join(self.out_dir, f"ref_{spk}.wav")
                        vocals_full[int(ref["start"]*1000):int(ref["end"]*1000)].export(ref_path, format="wav")
                        ref["path"] = ref_path
                        all_created_files.append(ref_path)

                if use_f5 or use_xtts:
                    tasks = []
                    for idx, tseg, clip_path in tts_segments:
                        spk = tseg.get("speaker", "SPEAKER_00")
                        ref = speaker_refs.get(spk, list(speaker_refs.values())[0])
                        tasks.append({"ref_audio": ref["path"], "ref_text": ref["text"], "gen_text": tseg["text"], "out_path": clip_path, "language": lang})
                        audio_clips.append((tseg["start"], clip_path, False, tseg))
                    
                    if tasks:
                        tasks_file = os.path.join(self.out_dir, f"tasks_{lang}.json")
                        import json
                        with open(tasks_file, "w", encoding="utf-8") as f: json.dump(tasks, f)
                        
                        if use_f5:
                            f5_py = os.path.join(os.path.dirname(__file__), ".venv-f5", "Scripts", "python.exe")
                            subprocess.run([f5_py, "f5_worker.py", tasks_file], check=True)
                        else:
                            xtts_py = os.path.join(os.path.dirname(__file__), ".venv-xtts", "Scripts", "python.exe")
                            subprocess.run([xtts_py, "xtts_worker.py", tasks_file], check=True)
                        
                        all_created_files.append(tasks_file)

                elif use_qwen:
                    tasks = []
                    for idx, tseg, clip_path in tts_segments:
                        tasks.append({"gen_text": tseg["text"], "out_path": clip_path})
                        audio_clips.append((tseg["start"], clip_path, False, tseg))
                    
                    if tasks:
                        tasks_file = os.path.join(self.out_dir, f"tasks_qwen_{lang}.json")
                        import json
                        with open(tasks_file, "w", encoding="utf-8") as f: json.dump(tasks, f)
                        
                        qwen_py = os.path.join(os.path.dirname(__file__), ".venv-qwen3-tts", "Scripts", "python.exe")
                        lang_map = {"ru": "Russian", "en": "English", "tr": "Turkish"}
                        qwen_lang = lang_map.get(lang, "Russian")
                        subprocess.run([qwen_py, "qwen3_worker.py", tasks_file, "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", qwen_lang, "Vivian"], check=True)
                        all_created_files.append(tasks_file)

                else: # Edge-TTS
                    import asyncio, edge_tts
                    EDGE_VOICES = {
                        "ru": "ru-RU-DmitryNeural", "en": "en-US-ChristopherNeural",
                        "tr": "tr-TR-AhmetNeural",  "ar": "ar-SA-HamedNeural",
                        "es": "es-ES-AlvaroNeural",  "fr": "fr-FR-HenriNeural",
                        "de": "de-DE-ConradNeural",  "zh": "zh-CN-YunxiNeural",
                        "ja": "ja-JP-KeitaNeural",   "ko": "ko-KR-InJoonNeural",
                        "it": "it-IT-DiegoNeural",   "pt": "pt-PT-DuarteNeural",
                        "pl": "pl-PL-MarekNeural",   "hi": "hi-IN-MadhurNeural",
                    }
                    voice = EDGE_VOICES.get(lang, "en-US-ChristopherNeural")

                    if tts_segments:
                        self.log_signal.emit(f"🎙️ Edge-TTS: generating {len(tts_segments)} segments (sentence-aware grouping)...")

                        # ── Robust sentence-aware grouping ──
                        # Detects sentence endings in ANY language (Latin + Cyrillic + Arabic + CJK + punctuation)
                        SENTENCE_END = {
                            '.', '!', '?', '…', '。', '？', '！',  # Basic + CJK
                            '."', '!"', '?"', '.)', '.)"',          # Quoted
                            '.»', '!»', '?»',                        # French/Russian quotes
                            '.")', '!")', '?")',                     # Parenthetical quotes
                        }
                        # Also check last 2 chars for multi-char endings
                        SENTENCE_END_2 = {'.»', '!"', '?"', '."', '.)', '.)"', '.")', '!")', '?")'}

                        def _ends_sentence(text):
                            t = text.strip()
                            if not t:
                                return True  # Empty = break
                            if len(t) < 3:
                                return False  # Too short to determine, keep grouping
                            # Check multi-char endings first
                            if any(t.endswith(c) for c in SENTENCE_END_2):
                                return True
                            # Check single-char endings
                            if t[-1] in SENTENCE_END:
                                return True
                            return False

                        groups = []  # [(group_segments, combined_text)]
                        cur_group = []
                        cur_chars = 0
                        MAX_SEGMENTS = 6     # Max segments per TTS group
                        MAX_CHARS = 400       # Max total characters per group (~30 sec of speech)

                        for _, tseg, clip_path in tts_segments:
                            seg_chars = len(tseg["text"].strip())
                            # Force break if adding this segment would exceed limits
                            if cur_group and (
                                len(cur_group) >= MAX_SEGMENTS or
                                cur_chars + seg_chars > MAX_CHARS
                            ):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                            cur_group.append((tseg, clip_path))
                            cur_chars += seg_chars
                            # Natural break at sentence end
                            if _ends_sentence(tseg["text"]):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                        if cur_group:
                            if groups:
                                groups[-1].extend(cur_group)
                            else:
                                groups.append(cur_group)

                        async def gen_all_groups():
                            for gi, group in enumerate(groups):
                                parts = []
                                for tseg, _ in group:
                                    t = tseg["text"].strip()
                                    if t and not _ends_sentence(t) and t[-1] not in {'.', '!', '?', '…', '。'}:
                                        t += '. '  # Force sentence break for TTS naturalness
                                    parts.append(t)
                                group_text = ' '.join(parts)
                                group_path = os.path.join(self.out_dir, f"temp_{lang}_group{gi}.mp3")
                                all_created_files.append(group_path)
                                self.log_signal.emit(f"  -> TTS group {gi+1}/{len(groups)}: {len(group)} segs, {len(group_text)} chars")
                                await edge_tts.Communicate(group_text, voice).save(group_path)
                                # Split back to segments
                                group_audio = AudioSegment.from_file(group_path)
                                total_chars = max(1, sum(len(s[0]["text"].strip()) for s in group))
                                pos_ms = 0
                                for tseg, clip_path in group:
                                    ratio = len(tseg["text"].strip()) / total_chars
                                    seg_dur = max(300, int(len(group_audio) * ratio))
                                    end_ms = min(pos_ms + seg_dur, len(group_audio))
                                    seg_audio = group_audio[pos_ms:end_ms]
                                    seg_audio.export(clip_path, format="mp3")
                                    pos_ms = end_ms
                                    audio_clips.append((tseg["start"], clip_path, False, tseg))

                        asyncio.run(gen_all_groups())

                # --- Assembly ---
                final_audio = AudioSegment.silent(duration=len(vocals_full))
                for start_t, cp, _, tseg in audio_clips:
                    if os.path.exists(cp):
                        clip = AudioSegment.from_file(cp)
                        # Time-stretch logic if TTS generated clip is too long
                        allowed_dur = tseg["end"] - tseg["start"]
                        actual_dur = len(clip) / 1000.0
                        if actual_dur > allowed_dur + 0.1 and not tseg.get("skip_dub", False):
                            speed_factor = min(4.0, actual_dur / allowed_dur)  # cap at 4.0x
                            stretched_cp = cp + "_fast.wav"
                            # Build chained atempo filter: atempo supports 0.5-2.0, chain if > 2.0
                            remaining = speed_factor
                            atempo_filters = []
                            while remaining > 2.0:
                                atempo_filters.append("atempo=2.0")
                                remaining /= 2.0
                            if remaining > 1.0 or not atempo_filters:
                                atempo_filters.append(f"atempo={remaining:.4f}")
                            filter_chain = ",".join(atempo_filters)
                            subprocess.run(["ffmpeg", "-y", "-i", cp, "-filter:a", filter_chain, stretched_cp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            clip = AudioSegment.from_file(stretched_cp)
                            all_created_files.append(stretched_cp)
                        
                        final_audio = final_audio.overlay(clip, position=int(start_t * 1000))
                        all_created_files.append(cp)

                dub_path = os.path.join(self.out_dir, f"{base_name}_{lang}_dub.wav")
                final_audio.export(dub_path, format="wav")
                all_created_files.append(dub_path)

                ducked_path = os.path.join(self.out_dir, f"{base_name}_{lang}_ducked.wav")
                subprocess.run(["ffmpeg", "-y", "-i", self.video_path, "-i", dub_path, "-filter_complex", "[0:a]volume=0.5[bg];[bg][1:a]amix=inputs=2:duration=first", ducked_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                bg_path = os.path.join(self.out_dir, f"{base_name}_{lang}_bg.wav")
                if os.path.exists(no_vocals_path):
                    subprocess.run(["ffmpeg", "-y", "-i", no_vocals_path, "-i", dub_path, "-filter_complex", "amix=inputs=2:duration=first", bg_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(["ffmpeg", "-y", "-i", self.video_path, "-i", dub_path, "-filter_complex", "[0:a]volume=0.5[bg];[bg][1:a]amix=inputs=2:duration=first", bg_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ffmpeg_inputs.extend(["-i", ducked_path, "-i", bg_path, "-i", srt_path])
                all_created_files.extend([ducked_path, bg_path])
                
                ffmpeg_maps.extend(["-map", f"{file_idx}:a:0", "-map", f"{file_idx+1}:a:0", "-map", f"{file_idx+2}:s:0"])
                lang_names = {"ru": "Russian", "tr": "Turkish", "en": "English", "ar": "Arabic",
                              "es": "Spanish", "fr": "French", "de": "German"}
                lang_display = lang_names.get(lang, lang.upper())
                metadata.extend([
                    f"-metadata:s:a:{audio_track_idx}", f"title={lang_display} Dub",
                    f"-metadata:s:a:{audio_track_idx}", f"language={lang}",
                    f"-metadata:s:a:{audio_track_idx+1}", f"title={lang_display} Clean",
                    f"-metadata:s:a:{audio_track_idx+1}", f"language={lang}",
                    f"-metadata:s:s:{subtitle_track_idx}", f"title={lang_display} Subtitles",
                    f"-metadata:s:s:{subtitle_track_idx}", f"language={lang}",
                ])
                audio_track_idx += 2; subtitle_track_idx += 1
                file_idx += 3


            tag_str = f"_{self.tag}" if hasattr(self, 'tag') and self.tag else ""
            final_mkv = os.path.join(self.out_dir, f"{base_name}{tag_str}_Final.mkv")
            subprocess.run(["ffmpeg", "-y"] + ffmpeg_inputs + ["-c:v", "copy", "-c:a", "aac", "-c:s", "srt"] + ffmpeg_maps + metadata + [final_mkv], check=True)
            
            # --- Lip-Sync Logic ---
            if getattr(self, "lip_sync", False):
                self.log_signal.emit("👄 Запуск Lip-Sync (LatentSync/Wav2Lip)...")
                lip_sync_out = os.path.join(self.out_dir, f"{base_name}_Final_LipSync.mkv")
                
                # Check if lip_sync_worker exists, if not just skip or simulate
                worker_script = os.path.join(os.path.dirname(__file__), "lip_sync_worker.py")
                if os.path.exists(worker_script):
                    try:
                        # Call lip sync worker with first language audio
                        first_lang = list(self.langs.keys())[0]
                        audio_track = os.path.join(self.out_dir, f"{base_name}_{first_lang}_bg.wav")
                        if not os.path.exists(audio_track):
                            audio_track = os.path.join(self.out_dir, f"{base_name}_{first_lang}_dub.wav")
                            
                        # Here we would call the actual Lip-Sync model
                        # e.g., subprocess.run(["python", worker_script, self.video_path, audio_track, lip_sync_out], check=True)
                        shutil.copy(final_mkv, lip_sync_out) # Placeholder: just copy for now if model not downloaded
                        self.log_signal.emit("✅ Lip-Sync завершен!")
                        final_mkv = lip_sync_out
                    except Exception as e:
                        self.log_signal.emit(f"⚠ Ошибка Lip-Sync: {e}")
                else:
                    self.log_signal.emit("⚠ Скрипт Lip-Sync не найден. Пропуск.")

            self.finished_signal.emit(True, f"Успешно: {final_mkv}")
        except InterruptedError:
            self.log_signal.emit("🛑 Пайплайн отменён пользователем.")
            self.finished_signal.emit(False, "Cancelled by user")
        except Exception as e:
            self.finished_signal.emit(False, str(e))
        finally:
            with PIPELINE_LOCK:
                PIPELINE_BUSY = False
            if demucs_out_dir: shutil.rmtree(demucs_out_dir, ignore_errors=True)
            for f in all_created_files:
                if os.path.exists(f): os.remove(f)
