# 🎬 AutoDub Studio v0.0.1

**AI-Powered Video Dubbing Pipeline** — Windows 11 desktop app for professional video dubbing using local AI.

> Transcription → Translation → TTS (14 languages) → MKV with subtitles.
> All local. All free. UI: EN 🇬🇧 / RU 🇷🇺 / TR 🇹🇷

<p align="center">
  <img src="gui/public/logo-icon.png" alt="AutoDub Studio" width="128"/>
</p>

---

## 🪟 Windows 11 Native

- **Fluent UI v9** — Microsoft's official React component library
- **Mica effect** — native Windows 11 window transparency
- **3 themes** — Light, Dark, Dim (Teams Dark)
- **Win11 Settings layout** — sidebar navigation, card-based content, form rows
- **Indistinguishable from native Windows apps**

---

## 🚀 Features

### Pipeline

| Step | Tech | Description |
|------|------|-------------|
| 📥 **Download** | yt-dlp | YouTube / TikTok / Vimeo URL or local file |
| 🎵 **Vocal Isolation** | Demucs (htdemucs) | Separate voice from background |
| 📝 **Transcription** | Faster-Whisper (tiny→large-v3) | Speech recognition with checkpoints |
| 👥 **Diarization** | Pyannote 3.1 | Speaker identification (HF token) |
| 🧠 **AI Translation** | 5 engines | Gemma 4, Gemini, DeepSeek, Google, DeepL |
| 🎙️ **TTS** | 5 engines | Qwen3-TTS, XTTSv2, F5-TTS, Edge-TTS, Azure |
| 👄 **Lip-Sync** | FFmpeg Audio Swap | Replace audio track |
| 🎬 **Assembly** | FFmpeg MKV | Multi-track: original + dub + subtitles |

### 14 Languages
🇷🇺 🇹🇷 🇬🇧 🇸🇦 🇪🇸 🇫🇷 🇩🇪 🇨🇳 🇯🇵 🇰🇷 🇮🇹 🇵🇹 🇵🇱 🇮🇳

### UI
- **Fluent UI v9** — native Windows 11 components
- **3 UI languages** — EN, RU, TR (full i18n, 300+ keys)
- **Command Palette** — Ctrl+K search & navigation
- **Keyboard shortcuts** — Ctrl+1/2/3/, for tabs
- **Page transitions** — Win11-style slide animations
- **GPU/VRAM/RAM monitor** — real-time in status bar
- **Virtual log viewer** — 60fps at any log volume
- **ARIA accessibility** — screen reader support

### Smart Features
- **Auto-updater** — background download with progress
- **Crash reports** — auto-submit to GitHub Issues
- **Model Manager** — download/delete AI models with progress
- **Advanced settings** — 6 toggles (SRT export, keep temp files, etc.)
- **Live Subtitles** — real-time translation overlay
- **AI Chat** — local LLM via Ollama with Markdown rendering

### Security
- API keys in Tauri Secure Store (OS keychain)
- WebSocket token auth (regenerated each startup)
- Safe Subprocess Environment (keys not inherited)
- Log redaction (secrets filtered)
- CORS, CSP, path validation, SSRF protection
- Origin validation on sensitive endpoints

---

## 🏗️ Architecture

```
AutoDubStudio/
├── backend/
│   ├── main.py              # FastAPI + WebSocket + 12 endpoints
│   ├── translator.py        # 5 translation engines
│   ├── workers.py           # Background tasks
│   ├── agent.py             # AI agent
│   └── vram_manager.py      # VRAM optimization
├── engine.py                # Main pipeline (AutoDubWorker)
├── live_engine.py           # Live subtitles
├── *_worker.py              # TTS workers (f5, qwen3, xtts, lip_sync, diarization)
├── gui/
│   ├── src/
│   │   ├── App.tsx          # Win11 layout (Mica titlebar + sidebar + content)
│   │   ├── main.tsx         # FluentProvider root
│   │   ├── theme.ts         # Fluent themes (Light/Dark/Dim)
│   │   ├── index.css        # Win11 styles (scrollbar, forms, cards, animations)
│   │   ├── store.ts         # i18n (300+ keys, 3 languages) + Tauri Store
│   │   ├── pages/           # DubbingStudio, LiveSubtitles, AIChat, Settings
│   │   ├── components/      # StatusBar, CommandPalette, ModelDownloader...
│   │   ├── hooks/           # useOllama, usePipelineWebSocket, useModelStatus...
│   │   └── lib/             # errorReporter, toast, utils
│   └── src-tauri/           # Rust: Mica, watchdog, single-instance, updater
└── config.json              # GitHub token for crash reports
```

---

## 📦 Setup

### Requirements
- Windows 10/11
- Python 3.12 · Node.js 20+ · Rust · Ollama · FFmpeg
- NVIDIA GPU 4+ GB VRAM (recommended)

### Dev

```bash
git clone https://github.com/LiskinLabs/autodubstudio.git
cd AutoDubStudio

# Backend
uv sync
python backend/main.py

# Frontend (separate terminal)
cd gui
npm install
npm run tauri dev
```

### Build .exe

```bash
cd gui
npm run tauri build
# Installer: gui/src-tauri/target/release/bundle/nsis/
```

---

## 🛠️ Design System

See [`gui/DESIGN.md`](gui/DESIGN.md) — full Fluent UI v9 design system documentation.

- **100% Fluent UI v9** — zero custom UI components
- **Design tokens** — `colorNeutralBackground1`, `colorBrandForeground1`
- **typographyStyles** — Win11 Type Ramp
- **Minimal CSS** — only scrollbars, drag regions, animations, layout

---

## 🗺️ Roadmap

### v0.0.1 ✅ Current
- [x] Full Fluent UI v9 migration
- [x] Win11 Settings layout
- [x] GPU/VRAM/RAM monitor
- [x] Advanced settings (6 options)
- [x] i18n audit (100% EN/RU/TR)
- [x] Backend crash-loop fix
- [x] Page transitions
- [x] Circular dependency fix (theme.ts ↔ store.ts)

### v0.0.2 📋 Planned
- [ ] System tray minimize
- [ ] Config presets (save/load settings)
- [ ] TTS voice preview
- [ ] Pipeline history (recent projects)
- [ ] Collapsible sidebar
- [ ] Context menu (right-click)
- [ ] Hotkeys for pipeline (Ctrl+Enter start, Escape stop)
- [ ] Dark/light schedule (auto-switch by time)

### v0.1.0 🎯 Future
- [ ] Publish on GitHub Releases
- [ ] Auto-update from GitHub
- [ ] Code signing
- [ ] MSI installer
- [ ] Mac/Linux support

---

## 🔗 Links

- **GitHub:** https://github.com/LiskinLabs/autodubstudio
- **GitLab:** https://gitlab.com/LiskinLabs/autodubstudio

---

## 🤝 Author

**Silvestr Liskin** — Senior Automation Engineer / Industrial Robot Programmer
Teknorob Robot ve Otomasyon — Bursa, TR
[GitHub](https://github.com/LiskinLabs) · [LinkedIn](https://www.linkedin.com/in/silvestr-liskin-ab712920b)

---

MIT License
