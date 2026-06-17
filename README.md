# 🎬 AutoDub Studio

**AI-Powered Video Dubbing Pipeline** — десктопное приложение для профессионального дубляжа видео с использованием локального ИИ.

> Транскрибация → Перевод → Озвучка (14 языков) → Сборка в MKV с субтитрами.  
> Всё локально. Всё бесплатно. 3 языка интерфейса.

<p align="center">
  <img src="gui/public/logo-icon.png" alt="AutoDub Studio" width="128"/>
</p>

---

## 🚀 Возможности

### 🎯 Основной пайплайн

| Шаг | Технология | Описание |
|-----|-----------|----------|
| 🎵 **Изоляция вокала** | Demucs (htdemucs) | Отделение голоса от фона |
| 📝 **Транскрибация** | OpenAI Whisper (tiny→large-v3) | Распознавание речи |
| 👥 **Диаризация** | Pyannote 3.1 (опционально) | Определение спикеров (требуется HF токен) |
| 🧠 **ИИ-перевод** | Gemma 4 + Google + DeepSeek + Gemini + DeepL | 5 движков на выбор |
| 🎙️ **Озвучка** | 5 движков (3 локальных, 2 облачных) | Qwen3-TTS, XTTSv2, F5-TTS, Edge-TTS, Azure |
| 👄 **Lip-Sync** | FFmpeg Audio Swap | Замена аудиодорожки в видео |
| 🎬 **Сборка** | FFmpeg MKV | Мультитрековый файл: оригинал + дубляж + субтитры |

### 🌍 Языки перевода + озвучки: 14

Русский 🇷🇺 · Турецкий 🇹🇷 · Английский 🇬🇧 · Арабский 🇸🇦 · Испанский 🇪🇸 · Французский 🇫🇷 · Немецкий 🇩🇪 · Китайский 🇨🇳 · Японский 🇯🇵 · Корейский 🇰🇷 · Итальянский 🇮🇹 · Португальский 🇵🇹 · Польский 🇵🇱 · Хинди 🇮🇳

### 🎙️ Движки озвучки (TTS)

| Движок | Тип | Voice Cloning |
|--------|-----|---------------|
| **Qwen3-TTS** | Локальный | ✅ |
| **XTTSv2** | Локальный | ✅ |
| **F5-TTS** | Локальный | ✅ Zero-shot |
| **Edge-TTS** | Облачный, бесплатный | ❌ |
| **Azure Speech** | Облачный, $ | ❌ |

### 🧠 Движки перевода

| Движок | Тип | Качество |
|--------|-----|----------|
| **Gemma 4** | Локальный (Ollama) | ⭐⭐⭐⭐⭐ |
| **Google Gemini** | API, $ | ⭐⭐⭐⭐⭐ |
| **DeepSeek** | API, $ | ⭐⭐⭐⭐ |
| **Google Translate** | Бесплатный | ⭐⭐⭐ |
| **DeepL** | API, $ | ⭐⭐⭐⭐⭐ |

### 🖥️ Интерфейс

| Фича | Описание |
|------|----------|
| **Tauri v2 + React 19** | Нативный десктоп (Windows), 8 MB инсталлятор |
| **3 языка UI** | English, Русский, Türkçe — ПОЛНЫЙ перевод |
| **Темы оформления (DaisyUI)** | Поддержка множества цветовых схем (CSS variables), переключение "на лету" |
| **Адаптивный дизайн** | @media для 900px и 600px |
| **Command Palette** | Ctrl+K — поиск по командам, навигация |
| **Клавиатурные сокращения** | Ctrl+1/2/3/, — вкладки, подсказки в сайдбаре |
| **Toast-уведомления** | Sonner: пайплайн, обновления, ошибки |
| **Микро-анимации** | Motion: переходы страниц, отклик кнопок, анимация шагов |
| **Виртуальный лог-вьювер** | 60fps при любом количестве записей |
| **ARIA accessibility** | Клавиатурная навигация, screen reader support |
| **YouTube URL** | Вставь ссылку → авто-загрузка и дубляж |
| **Manual Mode** | Ручная корректировка субтитров перед озвучкой с авто-синхронизацией |

### 🎤 Live Subtitles

- Синхронный перевод поверх любых окон (Zoom, Teams, Google Meet)
- Захват системного звука
- Настройка позиции и размера субтитров
- WebSocket-подключение к бэкенду

### 💬 AI Chat

- Чат с локальными LLM через Ollama
- Стриминг ответов (real-time)
- Выбор модели из выпадающего списка
- Поддержка fallback-моделей

### 🔄 Авто-апдейтер

- Проверка обновлений при каждом запуске
- Фоновая загрузка с индикатором прогресса
- Уведомление о готовности установки
- Перезапуск в один клик

### 🐛 Авто-репорты ошибок

- Глобальный перехват ошибок (ErrorBoundary + window.onerror)
- Авто-отправка логов и стектрейсов напрямую в бэкенд (FastAPI)
- Бэкенд создает Issue в `LiskinLabs/autodubstudio` через GitHub PAT
- Стек-трейс + логи терминала + версия ОС
- **Ноль действий от пользователя**

### 📥 Model Downloader

При первом запуске — диалог установки AI-моделей:
- Whisper large-v3 (~3.1 GB)
- Whisper base (~290 MB)
- Pyannote Segmentation (~500 MB)
- XTTSv2 (~1.9 GB)
- Qwen3-TTS (~1.5 GB)
- F5-TTS (~1.2 GB)
- Gemma 4 e4b (~4.6 GB)

Установка через Python-бэкенд / Ollama CLI. Чекбоксы, прогресс-бары, пропуск.

### 🎬 Выходной формат

**MKV с дорожками:**
- Оригинальное видео (copy, без перекодирования)
- Original Audio
- RU/TR Dub (дубляж + фон)
- RU/TR Clean (чистый дубляж)
- Оригинальные + переведённые субтитры

### 🔐 Безопасность

- API-ключи в **Tauri Secure Store** (не localStorage!)
- WebSocket с **token-аутентификацией** (secrets.token_urlsafe)
- `/api/report-error` требует Bearer токен + rate limit
- CORS: только localhost origins
- HTTP: restricted to 15+ API доменов (Tauri capability)
- Path validation через `os.path.realpath()`
- `subprocess.run()` всегда с массивами, без `shell=True`
- CSP: `default-src 'self'`

### ⚡ Умная озвучка (Sentence-Aware TTS)

- Группировка сегментов по границам предложений
- Одна TTS-генерация на группу → естественная интонация
- Максимум 8 сегментов в группе

### 🧠 Smart Translation Pipeline

- **Google Translate** — быстрый базовый перевод всех сегментов
- **Gemma4 AI Refinement** — улучшение перевода батчами по 4 сегмента
- **Circuit Breaker** — 3 последовательных сбоя → авто-фолбек на Google Translate
- **VRAM- aware** — авто-очистка GPU памяти между этапами
- **keep_alive** — модель остаётся в GPU 5 минут между запросами

### 🛡️ VRAM Management

- Авто-определение свободной VRAM перед загрузкой моделей
- Принудительное закрытие VRAM-голодных фоновых процессов (Chrome, Edge, Discord и др.)
- Авто-переключение на CPU при недостатке VRAM
- Изолированные подпроцессы Python для TTS (гарантированное освобождение VRAM)

### 👄 Lip-Sync

- FFmpeg audio swap: замена аудиодорожки в видео на дубляж
- Сохраняет оригинальное качество видео (copy codec)

### 🪟 Windows 11

- Mica эффект (нативный фон окна)
- Single instance (защита от повторного запуска)
- Window state persistence (позиция/размер)
- `transparent: true` для плавного resize

---

## 📦 Установка

### Из инсталлятора (Windows)

Скачай [`AutoDub Studio Setup.exe`](https://github.com/LiskinLabs/autodubstudio/releases/latest) (~8 MB).  
AI-модели скачиваются при первом запуске через Model Downloader.

### Требования (для разработки)

- Windows 10/11
- Python 3.12+
- Node.js 20+
- Rust (для сборки Tauri)
- Ollama
- FFmpeg (в PATH)
- NVIDIA GPU 6+ GB VRAM (рекомендуется)

### Быстрый старт (dev)

```bash
git clone https://github.com/LiskinLabs/autodubstudio.git
cd autodubstudio

# Python backend
uv sync
python backend/main.py

# Frontend (другой терминал)
cd gui
npm install
npm run tauri dev
```

---

## 🏗️ Архитектура

```
autodubstudio/
├── engine.py                # Основной пайплайн (AutoDubWorker)
├── live_engine.py           # Live-субтитры
├── backend/
│   ├── main.py              # FastAPI + WebSocket + /api/report-error + /api/models/*
│   ├── translator.py        # ИИ-перевод (Gemma, Gemini, DeepSeek, Google, DeepL)
│   ├── workers.py           # Фоновые задачи
│   └── vram_manager.py      # Управление VRAM
├── gui/                     # Tauri v2 + React 19
│   ├── src/
│   │   ├── components/      # 9 компонентов (CommandPalette, ErrorBoundary, ModelDownloader, ...)
│   │   ├── hooks/           # useOllama, usePipelineWebSocket, useLiveWebSocket
│   │   ├── lib/             # errorReporter, toast
│   │   ├── pages/           # DubbingStudio, LiveSubtitles, AIChat, Settings
│   │   └── store.ts         # 3 языка (240+ ключей), Tauri Secure Store
│   └── src-tauri/           # Rust: Mica, single-instance, updater, plugins
├── *_worker.py              # f5, qwen3, xtts, lip_sync, diarization
└── tools/                   # Utility scripts
```

---

## 🎮 Использование

### GUI

1. Запусти `Start_AutoDubStudio.bat`
2. Выбери видео (файл или YouTube URL)
3. Настрой: язык перевода, голос, движок перевода
4. Нажми «Start Pipeline»
5. MKV с дубляжом в папке `downloads/`

### CLI

```bash
python cli_run.py
```

---

## 🔧 Конфигурация

### API-ключи (Settings → API Keys)

- Google Gemini API Key
- DeepSeek API Key
- DeepL API Key
- OpenAI API Key
- HuggingFace Token (Pyannote)
- Azure Speech Key

### Переменные окружения

```bash
GITHUB_TOKEN=ghp_...     # Авто-репорты ошибок в GitHub Issues
TAURI_SIGNING_PRIVATE_KEY # Подпись кода (для авто-апдейтера)
```

---

## 🔗 Ссылки

- **🌐 GitHub:** https://github.com/LiskinLabs/autodubstudio
- **🪞 GitLab:** https://gitlab.com/LiskinLabs/autodubstudio
- **📥 Релизы:** https://github.com/LiskinLabs/autodubstudio/releases

---

## 🤝 Автор

**Silvestr Liskin** — Industrial Robot & Software Programmer (Full-stack Developer)  
Teknorob Robot ve Otomasyon — Bursa, TR  
[GitHub](https://github.com/LiskinLabs) · [LinkedIn](https://www.linkedin.com/in/silvestr-liskin-ab712920b)

---

## 📄 Лицензия

MIT License
