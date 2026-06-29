# AutoDubStudio - Project Journal & Memory

## [2026-06-23] "Netflix" Translation Pipeline & Spacy Integration
### 🎯 Current State & Hand-off
- **Competitor Analysis:** Investigated `VideoLingo` to integrate their high-end 3-stage translation pipeline (Spacy NLP Splitter -> LLM Context -> LLM Netflix-style adaptation) and User Glossary features.
- **Phase 1 (NLP Splitter) DONE:**
  - Installed `spacy` (`en_core_web_sm`, `ru_core_news_sm`) via `uv`.
  - Created `backend/nlp_splitter.py` to logically split raw Whisper segments based on sentence boundaries (`doc.sents`).
  - Integrated into `engine.py` pipeline (runs after Whisper transcription).
  - Added "Умное NLP-разделение фраз (Spacy)" toggle to the Config UI in `DubbingStudio.tsx`.
- **Knowledge Captured:**
  - **Whisper Models:** Explained the trade-offs of tiny/base vs medium vs large-v3 models. (large-v3 is critical for Netflix-level dubbing).
  - **Whisper Engines:** Clarified that both `faster-whisper` and `WhisperX` use the same models. `faster-whisper` optimizes speed/VRAM via CTranslate2, while `WhisperX` uses `faster-whisper` + Wav2Vec2 for precise word-level phonetic alignment (perfect for lip-sync).
- **Next Step:** Proceed to Phase 2 (User Glossaries CRUD & UI mapping) and Phase 3 (3-stage translation).

---

## [2026-06-19] Release 0.0.1 — UI/UX Audit, API Keys Fix & Stabilization

### 🎯 Current State & Hand-off
- **Release 0.0.1 is STABLE.** The pipeline connects, VRAM manages properly, and UI is responsive.
- **API Keys FIXED:** DeepL, HuggingFace, Azure, OpenAI, Google tokens are now correctly exposed from `store.ts` to `settingsStore` and passed via WebSocket to `engine.py`. Keys are no longer lost between the front-end and the `AutoDubWorker`.
- **UI/UX Polished (Win11 Settings Style):**
  - **Sidebar:** The mobile sidebar backdrop now fades in/out smoothly and is strictly hidden on desktop `>768px` using CSS.
  - **Grids:** All configuration grids (`LiveSubtitles`, `DubbingStudio` manual mode cards) collapse to single columns on small screens using global overrides.
  - **Padding:** Hardcoded `48px` paddings in `AIChat` replaced with `max(20px, min(48px, 4vw))` for fluid responsiveness.
  - **Review Editor:** Header columns and row cells in the translation review table wrap dynamically (`flex-wrap`) on mobile to prevent overflow.
  - **Text Wraps:** `.win11-page` enforces `overflow-wrap: break-word`.

### 🚀 Next Steps (Towards v0.0.2)
1. **TTS Quality Audit:** Check F5-TTS, XTTSv2, Qwen3-TTS audio output accuracy and performance.
2. **Lip-Sync Precision:** Implement dynamic time warping using per-word Whisper timestamps.
3. **Advanced Error Recovery:** Improve pipeline behavior if a specific TTS or Translation engine hangs mid-processing.
4. **Stable Release Prep:** Prepare pipeline to handle more edge cases in SubRip parsing.

---

## [2026-06-18] Security + Cleanup + Bugs + Build + Pipeline Testing
*(Archived summary of 0.0.1 foundation)*

- **Security (21 findings fixed):** Safe subprocess env, log redaction (secrets masking), origin validation, CSP headers.
- **Whisper Architecture:** Runs in a separate subprocess via `-c` to guarantee 100% VRAM cleanup before Ollama starts.
- **Ollama/Gemma4:** `num_gpu` auto-scales based on available VRAM. (Note: 4GB GPU might hit CUDA OOM with `gemma4:e4b` — Google Translate fallback works correctly).
- **Backend Infrastructure:** TCP watchdog (`is_backend_alive()`), exponential backoff for port 8000 handling.
- **Compiled App:** Built as `AutoDub Studio_0.0.1_x64-setup.exe` (NSIS).

## 🔒 Security & Industrial Constraints
- **GitHub PAT:** Token in `config.json` is **untouchable**. It is required for the Error Reporter. Do not delete or rotate it.
- **Frontend Translations:** NEVER call `t()` at the top-level scope outside React components. It causes a fatal "Cannot read properties of undefined" due to `settingsStore` lazy init. Always call `t()` during render!

## 🛠 Instructions for AI: How to build `.exe` (CRITICAL)
1. `cd C:\Users\silvestr.liskin\Desktop\AutoDubStudio\gui`
2. `npm run tauri build` (temporarily remove `tsc` from build script if it fails due to strict TS).
3. Wait for NSIS bundle.
4. Copy: `Copy-Item -Path "src-tauri\target\release\bundle\nsis\AutoDub Studio_0.0.1_x64-setup.exe" -Destination "C:\Users\silvestr.liskin\Desktop\AutoDub Studio_0.0.1_x64-setup.exe" -Force`
5. Inform the user it's ready.

## [2026-06-22] Automated Engine Testing & Audit
- **Status:** Остановлены на 23/26. В будущем перезапустим с новым патчем, чтобы каждое MKV сохранялось с именем связки для удобной отладки качества (например, выявление французского акцента в RU).
- **Keys Applied:** Gemini (OK), DeepL (OK), HuggingFace (OK), DeepSeek (OK).
- **Fixes Applied:** 
  - Patched `run_tests.bat` to remove `pause`.
  - Restarted with `$env:PYTHONIOENCODING="utf-8"` to prevent Windows `charmap` crashes on emoji output (`✅`).
  - Patched `test_all_engines.py` to properly load `hf_key` from config.
