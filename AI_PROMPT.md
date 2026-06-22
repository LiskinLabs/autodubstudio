# AutoDub Studio — Полное ТЗ для AI-ассистента

## 🚨 КРИТИЧЕСКИЕ ПРАВИЛА (нарушение = катастрофа)

1. **НИКОГДА не отправляй код на GitHub/GitLab без тестирования.** Сначала запусти приложение, проверь что пайплайн работает, и только потом `git push`.
2. **Один фикс — один коммит.** Не меняй 30 файлов одновременно.
3. **Рабочий код — священен.** Прежде чем "исправлять", убедись что оно реально сломано.
4. **Python scoping:** никогда не делай `import os` внутри функции, которая уже использует `os` на уровне модуля.
5. **Бекенд-процесс живёт своей жизнью.** После изменения Python-файлов нужно УБИТЬ python.exe (через Диспетчер задач или `taskkill /F /IM python.exe`), иначе старый код продолжит работать.
6. **Читай документацию перед тем как трогать ML-библиотеки:** Context7 для Pyannote, faster-whisper, Demucs, XTTS, F5-TTS, edge-tts.

## 📁 Структура проекта

```
C:\Users\silvestr.liskin\Desktop\AutoDubStudio\
├── backend/
│   ├── main.py              # FastAPI сервер (порт 8000), WebSocket, 20+ endpoints
│   ├── translator.py        # DeepSeek, Gemini, DeepL, Google, Ollama переводчики
│   ├── shared.py            # pipeline_status (разделяемое состояние)
│   ├── vram_manager.py      # Мониторинг GPU
│   ├── workers.py           # Фоновые задачи
│   └── agent.py             # AI-агент
├── engine.py                # ГЛАВНЫЙ пайплайн: Demucs→Whisper→Pyannote→Translate→TTS→Mux
├── live_engine.py           # Live-субтитры
├── f5_worker.py             # F5-TTS PyTorch (PyTorch, .venv-f5)
├── f5_onnx_worker.py        # F5-TTS ONNX (.venv)
├── xtts_worker.py           # XTTS v2 (.venv-xtts)
├── qwen3_worker.py          # Qwen3-TTS (.venv-qwen3-tts)
├── diarization_worker.py    # Pyannote диаризация
├── gui/
│   ├── src/
│   │   ├── App.tsx          # Главный layout (Win11 Mica, сайдбар)
│   │   ├── store.ts         # i18n (300+ ключей, en/ru/tr), Zustand-like store
│   │   ├── pages/           # DubbingStudio, LiveSubtitles, AIChat, Settings
│   │   ├── components/      # StatusBar, ErrorBoundary, ModelDownloader, FirstRunWizard...
│   │   └── hooks/           # usePipelineWebSocket, useModelStatus, useOllama...
│   └── src-tauri/
│       ├── src/lib.rs       # Rust: запуск бекенда, kill порта, авто-установка зависимостей
│       └── tauri.conf.json  # Конфигурация Tauri, ресурсы, NSIS/MSI
├── github_token.txt         # GitHub PAT для авто-отправки ошибок (gitignored!)
└── config.json              # Пользовательские настройки (gitignored)
```

## 🔧 Компоненты и их статус

### ✅ Работает стабильно
| Компонент | Что делает | Где код |
|-----------|-----------|---------|
| **Demucs** | AI изоляция вокала (htdemucs_ft = 4 модели) | engine.py:666-700 |
| **Whisper** | Распознавание речи (large-v3, CUDA) | engine.py:731-770 |
| **Pyannote** | Диаризация (кто говорит) | engine.py:776-810 |
| **DeepSeek** | Умный перевод | backend/translator.py:155-163 |
| **XTTS v2** | Синтез речи с клонированием (.venv-xtts) | xtts_worker.py |
| **F5-TTS PyTorch** | Zero-shot клонирование (.venv-f5) | f5_worker.py |
| **FFmpeg Mux** | Сборка MKV с 2 дорожками дубляжа | engine.py:1104-1160 |

### ⚠️ Сломано/Нестабильно
| Компонент | Проблема |
|-----------|----------|
| **ONNX TTS** | int32/int64 конфликт с ONNX моделью. Используй XTTS вместо |
| **Qwen3 TTS** | `.venv-qwen3-tts`: pwd модуль (Unix-only) на Windows |
| **Edge-TTS** | Только что исправлен `voice is not defined` — проверь |

## 🚀 Как тестировать

```bash
# 1. Убить старый бекенд
taskkill /F /IM python.exe

# 2. Запустить Tauri в dev-режиме
cd C:\Users\silvestr.liskin\Desktop\AutoDubStudio\gui
npx tauri dev

# 3. В приложении: Dubbing Studio → test_20s.mp4 → XTTS v2 → Run

# 4. Смотреть логи
tail -f C:\Users\silvestr.liskin\Desktop\AutoDubStudio\autodub_backend.log

# 5. Собрать инсталлятор
cd gui && npx tauri build --bundles nsis
cp src-tauri/target/release/bundle/nsis/AutoDub\ Studio_0.0.1_x64-setup.exe ~/Desktop/
```

## 📝 Память и уроки

В `.claude/projects/C--Users-silvestr-liskin/memory/` лежат:
- `autodub-audit-lessons-2026-06-22.md` — 🚨 как Claude сломал рабочий код непроверенными изменениями
- `autodub-v0.0.1-final-state.md` — полное состояние проекта
- `autodub-pipeline-verified-2026-06-22.md` — проверенные конфигурации

## 🔗 Репозитории
- **GitHub (основной):** https://github.com/LiskinLabs/autodubstudio
- **GitLab (зеркало):** https://gitlab.com/LiskinLabs/autodubstudio
- **GitHub Release:** https://github.com/LiskinLabs/autodubstudio/releases/tag/v0.0.1 (турецкий)

## 💀 Как НЕ надо делать (реальный случай 2026-06-22)

Claude сделал "глубокий аудит" — изменил 30 файлов, запушил на GitHub без тестирования.
Результат: РАБОЧИЙ КОД ПЕРЕСТАЛ РАБОТАТЬ. 5 часов ушло на восстановление.

**Конкретные ошибки:**
- `import os` внутри функции `run()` → перекрыл модульный `os` → UnboundLocalError
- Изменён FFmpeg код (удалён `weights=`) → EINVAL на Windows
- Изменены f-строки в translator.py → SyntaxError
- Пуш в GitHub с токеном → push protection заблокировал
- Бекенд не перезагружался → пользователь тестировал старый код

**ВЫВОД: тестируй локально перед каждым пушем. GitHub/GitLab = только рабочий код.**

## 👤 Пользователь
- **Silvestr Liskin** — Senior Automation Engineer / Industrial Robot Programmer
- **Язык:** Русский (отвечай на русском)
- **Приоритет:** Качество и стабильность > скорость
