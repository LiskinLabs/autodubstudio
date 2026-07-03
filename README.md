# 🎬 AutoDub Studio v0.0.2 Beta

**AI-Powered Video Dubbing Pipeline** / **Система ИИ-Дубляжа Видео**
Desktop app (Windows 11) for professional AI video translation and dubbing.

> Transcription → Translation → Voice-over (14+ languages) → MKV
> Fully local. Free. UI: EN 🇬🇧 / RU 🇷🇺 / TR 🇹🇷

<p align="center">
  <img src="gui/public/logo-icon.png" alt="AutoDub Studio" width="128"/>
</p>

---

## 🆕 v0.0.2 — What's New

- **Bilingual Video Support** — Auto-detect multiple languages in a single video (ES+EN, RU+EN, etc.). Each segment tagged with correct language.
- **Smart Skip** — When dubbing to language X, segments already in language X are kept as original (not re-dubbed).
- **WhisperX (Default)** — Word-level alignment for higher quality transcription. Falls back to standard Faster-Whisper.
- **NLP Sentence Splitter** — Spacy-based smart segmentation (EN/RU/ES + multi-lang fallback). Splits long Whisper segments into natural sentences.
- **Gender Detection v2** — Cross-lingual XLSR-53 model + pitch-based fallback. Works for ALL TTS engines (XTTSv2 AND Edge-TTS).
- **Dual-Language Subtitles** — Output includes `_original.srt` (with language tags), `_LANG.srt` (translation), and `_LANG_bilingual.srt` (original + translation side-by-side).
- **Subtitles-Only Mode** — `dub_engine=none` now truly skips TTS generation.
- **Quality Fallback Chain** — Translation: DeepL → Gemini/DeepSeek → Google Translate → Ollama. TTS: XTTSv2 → Edge-TTS → Subtitles-only.
- **langdetect Integration** — 55-language text-based detection for accurate per-segment language tagging.

---

## 🪟 Windows 11 Native Interface

- **Fluent UI v9** — Microsoft's official component library.
- **Mica effect** — Native Windows 11 window transparency.
- **3 Themes** — Light, Dark, Dim (Teams Dark).
- **3 Languages** — Full RU, EN, TR localization.

---

## 🚀 Pipeline

| Step | Technology | Description |
|------|-----------|-------------|
| 📥 **Download** | yt-dlp | YouTube, X, TikTok, local files |
| 🎵 **Voice Isolation** | Demucs (htdemucs_ft) | Studio-quality vocal extraction (4 models) |
| 📝 **Transcription** | WhisperX / Faster-Whisper | Word-level alignment, 99 languages, CUDA |
| 👥 **Diarization** | Pyannote 3.1 | Speaker separation (requires HF token) |
| 🧠 **Translation** | DeepL / Gemini / DeepSeek / Google / Ollama | Hybrid with auto-error-correction |
| 🎙️ **TTS** | XTTS v2 / Edge-TTS | Voice cloning + neural voices, gender-matched |
| 🎬 **Assembly** | FFmpeg MKV | Original + Dub + Clean Dub + SRT Subtitles |

### 14+ Supported TTS Languages
🇷🇺 🇹🇷 🇬🇧 🇸🇦 🇪🇸 🇫🇷 🇩🇪 🇨🇳 🇯🇵 🇰🇷 🇮🇹 🇵🇹 🇵🇱 🇮🇳

### Smart Features
- **Bilingual Detection** — Multi-language video support with per-segment language tagging
- **Smart Skip** — Native-language segments preserved during dubbing
- **Gender-Matched Voices** — Cross-lingual AI gender detection for natural voice selection
- **Dual-Language Subtitles** — Original + Translation in a single SRT file
- **VRAM Manager** — Real-time GPU/VRAM/RAM monitoring and cleanup
- **Smart Sentence Grouping** — NLP-based segmentation for natural-sounding speech

---

## 🏗️ Architecture

```
AutoDubStudio/
├── backend/                  # FastAPI + WebSocket
│   ├── main.py               # Server, API routes, WebSocket
│   ├── translator.py         # Multi-engine translation (DeepL/Gemini/DeepSeek/Google/Ollama)
│   ├── whisper_multi_worker.py  # WhisperX/Faster-Whisper with bilingual detection
│   ├── nlp_splitter.py       # Spacy-based sentence segmentation (per-segment language)
│   └── *_worker.py           # Isolated workers (TTS, diarization, gender, VRAM)
├── gui/
│   ├── src/                  # React + Fluent UI v9 + TypeScript
│   │   ├── pages/            # DubbingStudio, LiveSubtitles, AIChat, Settings
│   │   └── store.ts          # Global state + i18n (RU/EN/TR)
│   └── src-tauri/            # Rust backend (native windows, auto-updates)
├── engine.py                 # Main dubbing pipeline (AutoDubWorker)
├── gender_worker.py          # Cross-lingual gender detection (XLSR-53 + pitch)
├── cli.py                    # CLI interface for batch processing
└── config.json               # API keys and settings
```

---

## 📦 CLI Usage

```bash
# Subtitles only, fully local
python cli.py "video.mp4" --langs ru,tr --dub_engine none

# Full dub with WhisperX + XTTSv2 voice cloning
python cli.py "video.mp4" --langs ru --dub_engine xttsv2 --whisper_engine whisperX

# YouTube video, Google Translate, Edge-TTS
python cli.py "https://youtube.com/watch?v=..." --langs ru,tr --dub_engine edge-tts --translator_engine google

# Quick test (first 60 seconds)
python cli.py "video.mp4" --langs ru --max_duration 60 --dub_engine none

# With HuggingFace token (for SpeechBrain + Pyannote)
python cli.py "video.mp4" --langs ru --hf_key "hf_..."
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--langs` | `ru` | Target languages (comma-separated) |
| `--dub_engine` | `edge-tts` | `none` / `edge-tts` / `xttsv2` |
| `--translator_engine` | `google` | `google` / `ollama` / `deepl` / `gemini` / `deepseek` |
| `--whisper_engine` | `whisperX` | `whisper` (fast) / `whisperX` (word-level) |
| `--local_only` | — | Force local AI only (Ollama + XTTSv2) |
| `--max_duration` | `0` | Trim to N seconds (0 = full video) |
| `--hf_key` | — | HuggingFace token for gated models |
| `--no_youtube_subs` | — | Force Whisper instead of YouTube subtitles |

### Output Files

| File | Content |
|------|---------|
| `*_original.srt` | Original transcription with `[EN]`/`[ES]` language tags |
| `*_LANG.srt` | Translated subtitles (smart skip applied) |
| `*_LANG_bilingual.srt` | Original + Translation side-by-side |
| `*_LANG.mkv` | Final video with embedded audio + subtitles |

---

## 📦 Build

### Requirements
- Windows 10/11
- Python 3.12 · Node.js 20+ · Rust · FFmpeg
- NVIDIA GPU 4+ GB VRAM (strongly recommended)

```bash
git clone https://github.com/LiskinLabs/autodubstudio.git
cd AutoDubStudio/gui

npm install
npm run tauri build
# Installers: gui/src-tauri/target/release/bundle/nsis/
```

---

## 🤝 Author

**Silvestr Liskin** — Senior Automation Engineer / Industrial Robot Programmer
Teknorob Robot ve Otomasyon — Bursa, TR
[GitHub](https://github.com/LiskinLabs) · [LinkedIn](https://www.linkedin.com/in/silvestr-liskin-ab712920b)

---

MIT License
