import { useState, useEffect } from 'react';
import { Store } from '@tauri-apps/plugin-store';
import { isThemeDark } from './theme';

export type Language = 'en' | 'ru' | 'tr';

const translations: Record<Language, Record<string, string>> = {
  en: {
    // Pipeline Steps
    'step.source': 'Source',
    'step.demucs': 'Demucs',
    'step.whisper': 'Whisper',
    'step.translate': 'Translate',
    'step.tts': 'TTS',
    'step.mux': 'Mux',

    // Live Subtitles
    'live.title': 'Live Subtitles',
    'live.subtitle': 'Real-time AI translation and speech-to-text with floating overlay.',
    'live.start': 'Start Capture',
    'live.stop': 'Stop',
    'live.settings': 'Overlay Settings',
    'live.position': 'Position',
    'live.size': 'Text Size',
    'live.status_audio': 'Audio Capture',
    'live.status_audio.idle': 'Idle - waiting to start',
    'live.status_audio.active': 'Capturing from default output device',
    'live.status_engine': 'Translation Engine',
    'live.status_engine.idle': 'Idle - waiting for audio stream',
    'live.status_engine.active': 'Active - connected to API',
    'live.status_overlay': 'Subtitle Overlay',
    'live.status_overlay.idle': 'Overlay hidden - will appear when started',
    'live.status_overlay.active': 'Showing subtitles',

    // Dropdowns / Labels
    'lang.en': 'English',
    'lang.ru': 'Russian',
    'lang.tr': 'Turkish',
    'lang.ar': 'Arabic',
    'lang.es': 'Spanish',
    'lang.fr': 'French',
    'lang.de': 'German',
    'lang.zh': 'Chinese',
    'lang.ja': 'Japanese',
    'lang.ko': 'Korean',
    'lang.it': 'Italian',
    'lang.pt': 'Portuguese',
    'lang.pl': 'Polish',
    'lang.hi': 'Hindi',
    'pos.bottom': 'Bottom',
    'pos.top': 'Top',
    'pos.center': 'Center',
    'size.small': 'Small',
    'size.medium': 'Medium',
    'size.large': 'Large',

    // Voice models
    'dubbing.voice.qwen': 'Qwen3-TTS [local]',
    'dubbing.voice.xtts': 'XTTSv2 [local]',
    'dubbing.voice.f5': 'F5-TTS [local]',
    'dubbing.voice.azure': 'Azure API [internet, $]',
    'dubbing.voice.edge': 'Edge-TTS [internet]',
    'dubbing.voice.qwen3_full': 'Qwen3-TTS (Local)',
    'dubbing.voice.xttsv2_full': 'XTTSv2 (Local)',
    'dubbing.voice.f5tts_full': 'F5-TTS PyTorch (Local)',
    'dubbing.voice.f5onnx_full': 'F5-TTS ONNX Turkish (Local, Fast)',
    'dubbing.voice.azure_cloud': 'Azure Speech (Cloud)',
    'dubbing.voice.edge_cloud': 'Edge TTS (Cloud)',

    // Dubbing general
    'dubbing.title': 'Dubbing Studio',
    'dubbing.subtitle': 'Translate and dub video or audio files using local or cloud AI models.',
    'dubbing.file.selected': 'Selected file:',
    'dubbing.dropzone': 'Drag & Drop video/audio here or click to browse',
    'dubbing.supported': 'Supports MP4, MKV, MP3, WAV (Max 500MB)',
    'dubbing.config': 'Configuration',
    'dubbing.target_lang': 'Target Language',
    'dubbing.voice_model': 'Voice Model',
    'dubbing.translation_engine': 'Translation Engine',
    'dubbing.translator_model': 'Translator Model',
    'dubbing.mode': 'Execution Mode',
    'dubbing.mode.auto_label': 'Automatic Mode',
    'dubbing.mode.auto_desc': 'Run the entire pipeline automatically from start to finish.',
    'dubbing.mode.manual_label': 'Manual Mode',
    'dubbing.mode.manual_desc': 'Pause after translation to review and edit subtitles before voice generation.',
    'dubbing.advanced': 'Advanced Settings',
    'dubbing.start': 'Start Pipeline',
    'nav.dubbing': 'Dubbing Studio',
    'nav.live': 'Live Subtitles',
    'nav.chat': 'AI Chat',
    'nav.settings': 'Settings',

    // Translation engines
    'dubbing.engine.deepseek': 'DeepSeek API [internet, $]',
    'dubbing.engine.gemini': 'Google Gemini API [internet, $]',
    'dubbing.engine.deepl': 'DeepL API [internet, $]',
    'dubbing.engine.ollama': 'Ollama [local]',
    'dubbing.engine.google': 'Google Translate [internet]',

    // Settings keys
    'settings.hf_key': 'HuggingFace Token (Pyannote)',
    'settings.hf_desc': 'Required for Speaker Diarization (identifying who is speaking)',
    'settings.hf_terms': 'You must accept the terms for these models',
    'settings.hf_agree': 'On each page, click "Agree and access repository" — otherwise the token will not work.',
    'settings.deepl_key': 'DeepL API Key',
    'settings.deepl_desc': 'Used for high-quality machine translation',
    'settings.gemini_key': 'Gemini API Key',
    'settings.gemini_desc': 'Used for context-aware translation',
    'settings.deepseek_key': 'DeepSeek API Key',
    'settings.deepseek_desc': 'Affordable and capable translation model',

    // Dubbing advanced
    'dubbing.adv.mux': 'Auto-Mux Video',
    'dubbing.adv.mux_desc': 'Automatically merge the generated audio track with the original video file using FFmpeg',
    'dubbing.adv.clone': 'Clone Voice from Original',
    'dubbing.adv.clone_desc': 'Analyze the original speaker\'s voice and clone it for the dubbed audio instead of using a generic TTS voice',
    'dubbing.adv.demucs': 'Isolate Vocals with Demucs',
    'dubbing.adv.demucs_desc': 'Use Demucs AI to separate vocals from background music/noise before transcribing, improving accuracy',
    'dubbing.adv.demucs_ft': 'Fine-tuned (best quality)',
    'dubbing.adv.demucs_bal': 'Balanced (faster)',
    'dubbing.adv.demucs_6s': '6-source (cleanest vocals)',
    'dubbing.adv.export_srt': 'Export SRT Separately',
    'dubbing.adv.export_srt_desc': 'Save subtitle files (.srt) as separate output alongside the video',
    'dubbing.adv.gender_ai': 'AI Gender Matching',
    'dubbing.adv.gender_ai_desc': 'Automatically detect original speaker gender and match TTS voice',
    'dubbing.adv.yt_subs': 'Use YouTube Subtitles',
    'dubbing.adv.yt_subs_desc': 'Prefer original YouTube subtitles instead of transcribing with Whisper (if available)',
    'dubbing.adv.lip_sync': 'AI Lip Sync',
    'dubbing.adv.lip_sync_desc': "Synchronize speaker's lip movements with the new dubbed audio (requires significant GPU power)",
    'dubbing.adv.keep_temp': 'Keep Intermediate Files',
    'dubbing.adv.keep_temp_desc': 'Keep WAV, raw text and other temporary files after pipeline finishes',
    'dubbing.adv.auto_open': 'Auto-Open Output Folder',
    'dubbing.adv.auto_open_desc': 'Open the output folder automatically when pipeline completes',
    'dubbing.status.done': 'Process completed',
    'dubbing.status.processing': 'Processing step',
    'dubbing.badge.running': 'Running',
    'dubbing.badge.done': 'Done',
    'dubbing.log.title': 'Pipeline Log',
    'dubbing.log.entries': 'entries',
    'dubbing.log.copy': 'Copy All',
    'dubbing.log.copied': 'Logs copied to clipboard',
    'dubbing.log.copy_failed': 'Failed to copy logs',
    'dubbing.btn.open': 'Open Output Folder',
    'dubbing.btn.new': 'New Project',
    'dubbing.review.title': 'Manual Review Mode',
    'dubbing.review.desc': 'Pipeline paused after translation. Review and edit the translated subtitles below, then continue to audio generation.',
    'dubbing.review.original': 'Original Subtitles',
    'dubbing.review.readonly': 'Read-only',
    'dubbing.review.translated': 'Translated Subtitles',
    'dubbing.review.editable': 'Editable',
    'dubbing.review.speaker': 'Speaker',
    'dubbing.review.time': 'Time',
    'dubbing.review.segments': 'segments',
    'dubbing.review.edit_hint': 'Click any translation to edit it inline',
    'dubbing.btn.continue': 'Continue to Voice Generation',
    'dubbing.btn.cancel': 'Cancel',

    // Settings TTS & models
    'settings.tts_audio': 'TTS & Audio',
    'settings.tts_cache': 'TTS Cache Directory',
    'settings.browse': 'Browse',
    'settings.model_status': 'Model Status',
    'settings.model_status_desc': 'Installed models and their current download status.',
    'settings.installed': 'Installed',
    
    // Model Downloader
    'dl.title': 'Welcome to AutoDub Studio!',
    'dl.desc': 'AI models are required for local speech-to-text and generation. Please download the selected models to continue.',
    'dl.btn_download': 'Download Selected',
    'dl.btn_skip': 'Skip for now',
    'dl.note': 'You can download models later in the settings menu',
    'dl.downloading': 'Downloading... (can take 10-30 mins depending on internet speed)',
    'dl.downloading_short': 'Downloading...',
    'dl.queued': 'Queued...',
    'dl.select_all': 'Select All',
    'dl.btn_delete': 'Delete',
    'dl.deleting': 'Deleting...',
    'dl.delete_confirm_title': 'Delete Model?',
    'dl.delete_confirm_desc': 'This will permanently delete the model from your disk. You will need to download it again (10-30 minutes) to use its features.',
    'dl.models.demucs': 'AI vocal isolation & audio separation',
    'dl.models.whisper': 'Local AI speech recognition',
    'dl.models.pyannote': 'Speaker separation',
    'dl.models.qwen': 'Qwen3-TTS (High Quality)',
    'dl.models.f5': 'F5-TTS (Zero-Shot Cloning)',
    'dl.models.xtts': 'XTTS v2 (Professional Cloning)',
    'dl.models.gemma': 'Gemma 4 e4b (AI Translation)',
    'dl.models.demucs_detail': 'AI vocal isolation — language independent',
    'dl.models.whisper_detail': 'Speech recognition — 99 languages',
    'dl.models.pyannote_detail': 'Speaker diarization — language independent',
    'dl.models.qwen_detail': 'Neural TTS — ru, en, es, fr, zh',
    'dl.models.f5_detail': 'Zero-shot voice cloning — ru, en, zh',
    'dl.models.xtts_detail': 'Voice cloning TTS — 10 languages: ru, en, tr, es, fr, de, ar, it, pt, pl',
    'dl.models.gemma_detail': 'Local AI translation via Ollama — all languages',

    // About
    'settings.about.tagline': 'AI-Powered Video Dubbing Pipeline',
    'settings.about.author': 'Author',
    'settings.about.role': 'Industrial Robot & Software Programmer (Full-stack Developer)',
    'settings.about.partner': 'In partnership with',
    'settings.about.links': 'Links & Resources',
    'settings.about.github': 'GitHub Repository',
    'settings.about.website': 'LiskinLabs Website',

    'settings.title': 'Settings',
    'settings.subtitle': 'Configure your local environment, AI models, and cloud API integrations.',
    'settings.general': 'General',
    'settings.models': 'AI Models',
    'settings.keys': 'API Keys',
    'settings.about': 'About',
    'settings.appearance': 'Appearance & Language',
    'dubbing.logs.waiting': 'Waiting for logs...',
    'dubbing.btn.paste': 'Paste',
    'dubbing.btn.paste_title': 'Paste from clipboard',
    'dubbing.no_models': 'No models found',
    'dubbing.translator.deepl_api': 'DeepL Pro/Free API',
    'dubbing.translator.default': 'Default API Model',
    'dubbing.status.waiting_backend': 'Waiting for Python engine...',
    'chat.placeholder': 'Type a message...',
    'chat.empty.title': 'Start a conversation',
    'chat.empty.subtitle': 'Chat with your local AI models. These are the same models used for translation in the dubbing pipeline.',
    'chat.ollama_error': 'Cannot connect to Ollama. Make sure it is running on localhost:11434',
    'chat.new_chat': 'New Chat',
    'chat.no_models': 'No models downloaded (use ollama pull)',
    'chat.send_title': 'Send message',
    'chat.ollama_off_title': 'AI Is Off',
    'chat.ollama_off_desc': 'The local AI engine (Ollama) is turned off to save memory.',
    'chat.start_ollama': 'Start Ollama',
    'chat.stop_ollama': 'Stop',
    'chat.refresh_models': 'Refresh model list',
    'chat.disclaimer': 'AI can make mistakes. Consider verifying important information.',
    'chat.model_selector': 'Select AI model',
    'chat.connection_status': 'Connection status',
    'settings.gpu_limit': 'GPU Memory Limit',
    'settings.gpu.auto': 'Auto (Recommended)',
    'settings.gpu_desc': 'Limits VRAM usage for local AI models. "Auto" detects available memory.',
    'settings.auto_update': 'Auto-update Check',
    'settings.auto_update_desc': 'Periodically check for new versions on startup',
    'settings.speech_rec': 'Speech Recognition',
  
    'dubbing.mode.auto': 'Automatic (End-to-End)',
    'dubbing.mode.manual': 'Manual Review (Pause for Editing)',
    'dubbing.step.demucs': 'Demucs',
    'dubbing.step.mux': 'Mux',
    'dubbing.step.source': 'Source',
    'dubbing.step.translate': 'Translate',
    'dubbing.step.tts': 'TTS',
    'dubbing.step.whisper': 'Whisper',
    'live.audio_status': 'Audio Status',
    'live.auto': 'Auto-detect',
    'live.callout': 'Real-time translation as transparent subtitles over any window for Zoom, Teams, and Google Meet. Captures system audio and translates on the fly.',
    'live.config': 'Subtitle Settings',
    'live.engine.deepseek': 'DeepSeek API',
    'live.engine.whisper_local': 'Local Whisper',
    'live.engine_label': 'Translation Engine',
    'live.fontsize': 'Font Size',
    'live.listening': 'Live Capture',
    'live.preview': 'Live Preview',
    'live.recording': 'Recording',
    'live.source_lang': 'Source Language',
    'live.standby': 'Standby',
    'live.target_lang': 'Target Language',
    'live.waiting_audio': 'Waiting for audio...',
    'nav.system': 'System',
    'nav.tools': 'Tools',
    'settings.keys.all_ok': 'All keys are valid!',
    'settings.keys.azure_get': 'Get Azure Key',
    'settings.keys.azure_label': 'Azure Speech Key',
    'settings.keys.deepseek_get': 'Get DeepSeek Key',
    'settings.keys.deepseek_label': 'DeepSeek API Key',
    'settings.keys.failed': 'Connection test failed',
    'settings.keys.gemini_get': 'Get Gemini Key',
    'settings.keys.gemini_label': 'Google Gemini API Key',
    'settings.keys.google_get': 'Get GCP Key',
    'settings.keys.google_label': 'Google Cloud Speech API Key',
    'settings.keys.no_keys': 'Enter at least one API key to test.',
    'settings.keys.notice': 'API keys are stored securely in your local system keychain. They are never sent anywhere except to the respective API provider.',
    'settings.keys.openai_get': 'Get OpenAI Key',
    'settings.keys.openai_label': 'OpenAI API Key',
    'settings.keys.speech_apis': 'Speech and Cloud APIs',
    'settings.keys.test_all': 'Test All Connections',
    'settings.keys.testing': 'Testing...',
    'settings.keys.untested': 'Not tested',
    'settings.keys.translation_apis': 'Translation APIs',
    'settings.lang.en_label': 'English',
    'settings.lang.ru_label': 'Russian',
    'settings.lang.tr_label': 'Turkish',
    'settings.language': 'Language',
    'settings.ollama_config': 'Ollama Settings',
    'settings.ollama_url': 'Ollama Server URL',
    'settings.performance': 'Performance',
    'settings.theme': 'Theme',
    'settings.theme.light': 'Light',
    'settings.theme.dim': 'Dim',
    'settings.theme.night': 'Night',
    'settings.whisper.base': 'Fast, low accuracy',
    'settings.whisper.large': 'Best accuracy (recommended)',
    'settings.whisper.medium': 'Good accuracy',
    'settings.whisper.small': 'Balanced',
    'settings.whisper.tiny': 'Fastest, lowest accuracy',
    'settings.whisper_model': 'Whisper Model',
    'status.cpu': 'CPU Mode',
    'status.gpu': 'GPU Ready',
    'status.ollama': 'Ollama Connected',
    'status.ollama_off': 'Ollama Offline',
    'status.vram': 'VRAM: Auto',

    // StatusBar VRAM Cleaner & Restart
    'statusbar.vram_cleaner.title': 'VRAM Cleaner — GPU Memory',
    'statusbar.vram_cleaner.vram': 'VRAM:',
    'statusbar.vram_cleaner.kill': 'Kill Selected',
    'statusbar.vram_high_tooltip': 'High VRAM usage — click to clean up background processes',
    'statusbar.restart_tooltip': 'Restart backend & clear Python cache',
    'statusbar.restarted': 'Backend restarted successfully',
    'statusbar.restart_error': 'Failed to restart backend',

    // Command Palette
    'cmd.placeholder': 'Type a command or search...',
    'cmd.no_results': 'No results found.',
    'cmd.navigate': '↑↓ Navigate',
    'cmd.select': '↵ Select',
    'cmd.close': 'Esc Close',

    // HuggingFace
    'settings.keys.hf_get': 'Get HF Token ↗',
    'settings.keys.azure_placeholder': 'Azure Subscription Key',

    // Toasts
    'toast.pipeline_started': 'Pipeline started',
    'toast.pipeline_init': 'Initializing dubbing pipeline...',
    'toast.pipeline_stopping': 'Pipeline stopping...',
    'toast.pipeline_cancel': 'Cancelling current operation',
    'toast.backend_error': 'Backend Error',
    'toast.backend_offline': 'Python backend is offline. Please restart the application.',
    'ws.disconnect': 'Connection to backend lost',

    // File filter
    'dubbing.file_filter': 'Video',

    // Branding
    'brand.powered_by': 'Powered by LiskinLabs',

    // App shell
    'app.skip_to_content': 'Skip to main content',
    'app.search_commands': 'Search commands (Ctrl+K)',
    'app.toggle_theme': 'Toggle theme',
    'app.toggle_menu': 'Toggle Menu',

    // Breadcrumbs
    'breadcrumb.dubbing': 'Dubbing Studio',
    'breadcrumb.live': 'Live Subtitles',
    'breadcrumb.chat': 'AI Chat',
    'breadcrumb.settings': 'Settings',
    'breadcrumb.settings_models': 'Settings · AI Models',
    'breadcrumb.settings_keys': 'Settings · API Keys',
    'breadcrumb.settings_about': 'Settings · About',

    // Error boundary
    'error.title': 'Something went wrong',
    'error.default_message': 'An unexpected error occurred.',
    'error.reported': 'Error report sent automatically. Our team will investigate.',
    'error.sending': 'Sending error report automatically...',
    'error.reload': 'Reload Component',

    // Update checker
    'update.available_title': 'Update v{version} available!',
    'update.available_desc': 'A new version is ready. Starting background download...',
    'update.downloading': 'Downloading update ({size}MB)...',
    'update.notify_ready': "We'll notify you when it's ready.",
    'update.downloaded': 'Update downloaded!',
    'update.restart_prompt': 'Restart now to apply the update?',
    'update.failed': 'Update download failed',
    'update.retry_later': 'Will retry on next launch.',
    'update.installing': 'Installing update...',
    'update.restart_auto': 'App will restart automatically.',
    'update.install_failed': 'Failed to install update',
    'update.restart_manual': 'Please restart manually.',
    'update.ready_label': 'v{version} ready',
    'update.click_to_install': 'Click to install and restart',
    'update.downloading_label': 'Downloading update...',
    'update.available_label': 'Update available',
    'update.checking': 'Checking...',

    // GPU options
    'settings.gpu_4gb': '4 GB',
    'settings.gpu_6gb': '6 GB',
    'settings.gpu_8gb': '8 GB',
    'settings.gpu_12gb': '12 GB',

    // Keys test
    'settings.keys_all_valid': 'All keys valid!',

    // About
    'settings.about.app_name': 'AutoDubStudio',
    'settings.about.version_badge': 'v0.0.1',
    'settings.about.tech_badge': 'Tauri v2 + React 19 + Fluent UI v9',
    'settings.about.author_name': 'Silvestr Liskin',
    'settings.about.company': 'Teknorob Robot ve Otomasyon — Bursa, TR',

    // Command palette
    'cmd.group_navigation': 'Navigation',
    'cmd.group_actions': 'Actions',
    'cmd.search_commands': 'Search commands',

    // Dubbing
    'dubbing.youtube_placeholder': 'https://youtube.com/watch?v=... or https://x.com/...',
    'dubbing.tab_local': 'Local File',
    'dubbing.tab_youtube': 'YouTube / Web URL',
    // Theme labels
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    'theme.dim': 'Dim',

    // Models display
    'models.count': '{count} model(s)',
    'models.whisper_tiny': 'tiny',
    'models.whisper_base': 'base',
    'models.whisper_small': 'small',
    'models.whisper_medium': 'medium',
    'models.whisper_large_v2': 'large-v2',
    'models.whisper_large_v3': 'large-v3',

    // First-Run Wizard
    'frun.title': '🚀 Welcome to AutoDub Studio',
    'frun.subtitle': 'This app needs a few free programs to work. Choose what to install — or click "Install All".',
    'frun.ready': 'Ready',
    'frun.installing': 'Installing...',
    'frun.install': 'Install',
    'frun.all_done': 'All set — continue',
    'frun.install_all': 'Install All ({count})',
    'frun.installing_all': 'Installing...',
    'frun.instructions': 'Instructions',
    'frun.skip': 'Skip — I\'ll install manually later',
    'frun.footer': 'All components are free and installed from official websites.',
    'frun.opened_url': 'Opened download page — check after install',
    'frun.deps_python': 'Python 3.12+',
    'frun.deps_python_desc': 'Language for AI backend (speech recognition, translation, synthesis)',
    'frun.deps_uv': 'uv (package manager)',
    'frun.deps_uv_desc': 'Install Python dependencies 10-100x faster than pip',
    'frun.deps_ollama': 'Ollama',
    'frun.deps_ollama_desc': 'Local AI models for translation & chat',
    'frun.deps_ffmpeg': 'FFmpeg',
    'frun.deps_ffmpeg_desc': 'Video/audio processing & final assembly',
    'frun.deps_packages': 'AI Libraries',
    'frun.deps_packages_desc': 'PyTorch, F5-TTS, Whisper (5-10 minutes)',
    'dubbing.yt.auth_btn': '🔑 YouTube Auth (For Subs)',
    'dubbing.yt.auth_btn_done': '✅ YouTube Authorized',
    'dubbing.yt.scan': 'Scan URL',
    'dubbing.yt.scanning': 'Scanning...',
    'dubbing.yt.download_only': 'Download Selected Only',
    'dubbing.yt.download_mux': 'Download & Integrate into Video',
    'dubbing.yt.downloading': 'Downloading...',
    'dubbing.yt.subs': 'Available Subtitles',
    'dubbing.yt.audio': 'Available Audio Dubs',
    'dubbing.yt.none': 'None found',
    'dubbing.yt.description': 'Select your preferred media or subtitle tracks to import into the dubbing studio.',
  },
  ru: {
    // Navigation
    'nav.dubbing': 'Студия Дубляжа',
    'nav.live': 'Лайв Субтитры',
    'nav.chat': 'ИИ Чат',
    'nav.settings': 'Настройки',
    'nav.tools': 'Инструменты',
    'nav.system': 'Система',

    // Settings
    'settings.title': 'Настройки',
    'settings.subtitle': 'Настройте локальное окружение, ИИ-модели и облачные API.',
    'settings.general': 'Основные',
    'settings.models': 'ИИ Модели',
    'settings.keys': 'Ключи API',
    'settings.about': 'О программе',
    'settings.appearance': 'Внешний вид и язык',
    'settings.language': 'Язык',
    'settings.theme': 'Тема',
    'settings.performance': 'Производительность',
    'settings.theme.light': 'Светлая',
    'settings.theme.dim': 'Тусклая',
    'settings.theme.night': 'Ночная',
    'settings.lang.en_label': 'Английский',
    'settings.lang.ru_label': 'Русский (Russian)',
    'settings.lang.tr_label': 'Турецкий (Türkçe)',

    // Dubbing
    'dubbing.title': 'Студия Дубляжа',
    'dubbing.subtitle': 'Профессиональный пайплайн для ИИ-дубляжа видео. Загрузка, транскрибация, перевод и синтез речи в одном месте.',
    'dubbing.dropzone': 'Перетащите видео или вставьте ссылку на YouTube',
    'dubbing.supported': 'Поддерживается MP4, MKV, AVI, WebM',
    'dubbing.config': 'Настройки пайплайна',
    'dubbing.target_lang': 'Язык перевода',
    'dubbing.voice_model': 'ИИ Модель голоса',
    'dubbing.translation_engine': 'Движок перевода',
    'dubbing.translator_model': 'Модель перевода',
    'dubbing.mode': 'Режим работы',
    'dubbing.mode.auto': 'Автоматический (от и до)',
    'dubbing.mode.manual': 'С проверкой (пауза для редактуры)',
    'dubbing.mode.auto_label': 'Автоматический',
    'dubbing.mode.auto_desc': 'ИИ делает всё — от исходника до готового дубляжа без пауз',
    'dubbing.mode.manual_label': 'Ручная проверка',
    'dubbing.mode.manual_desc': 'Пауза после перевода для проверки и редактирования перед озвучкой',
    'dubbing.advanced': 'Продвинутые опции',
    'dubbing.start': 'Запустить пайплайн',
    // Pipeline steps
    'dubbing.step.source': 'Источник',
    'dubbing.step.demucs': 'Demucs',
    'dubbing.step.whisper': 'Whisper',
    'dubbing.step.translate': 'Перевод',
    'dubbing.step.tts': 'Озвучка',
    'dubbing.step.mux': 'Сборка',
    // File & UI
    'dubbing.file.selected': 'Выбрано:',
    'dubbing.logs.waiting': 'Ожидание логов...',
    'dubbing.btn.paste': 'Вставить',
    'dubbing.btn.paste_title': 'Вставить из буфера обмена',
    'dubbing.no_models': 'Модели не найдены',
    'dubbing.translator.deepl_api': 'DeepL Pro/Free API',
    'dubbing.translator.default': 'Стандартная модель API',
    'dubbing.status.waiting_backend': 'Ожидание Python бэкенда...',

    // Live
    'live.title': 'Лайв Субтитры',
    'live.subtitle': 'Синхронный перевод и субтитры для встреч и стримов.',
    'live.callout': 'Синхронный перевод в виде прозрачных субтитров поверх любых окон для Zoom, Teams и Google Meet. Захватывает системный звук и переводит на лету.',
    'live.config': 'Настройки субтитров',
    'live.source_lang': 'Исходный язык',
    'live.target_lang': 'Язык перевода',
    'live.position': 'Позиция на экране',
    'live.fontsize': 'Размер шрифта',
    'live.start': 'Запустить субтитры',
    'live.stop': 'Остановить',
    'live.auto': 'Авто-определение',
    'live.engine_label': 'Движок перевода',
    'live.engine.deepseek': 'DeepSeek API',
    'live.engine.whisper_local': 'Локальный Whisper',
    'live.preview': 'Прямой эфир',
    'live.recording': 'Запись',
    'live.waiting_audio': 'Ожидание аудио...',

    // Chat
    'chat.placeholder': 'Напишите сообщение...',
    'chat.empty.title': 'Начните диалог',
    'chat.empty.subtitle': 'Общайтесь с вашими локальными ИИ-моделями. Это те же модели, что используются для перевода.',
    'chat.ollama_error': 'Не удалось подключиться к Ollama. Убедитесь, что она запущена на localhost:11434',
    'chat.new_chat': 'Новый чат',
    'chat.no_models': 'Нет загруженных моделей (используйте ollama pull)',
    'chat.send_title': 'Отправить',
    'chat.ollama_off_title': 'ИИ выключен',
    'chat.ollama_off_desc': 'Локальный ИИ движок (Ollama) отключен для экономии памяти.',
    'chat.start_ollama': 'Запустить Ollama',
    'chat.stop_ollama': 'Выключить',
    'chat.refresh_models': 'Обновить список моделей',
    'chat.disclaimer': 'ИИ может ошибаться. Рекомендуется проверять важную информацию.',
    'chat.model_selector': 'Выбрать ИИ модель',
    'chat.connection_status': 'Статус подключения',

    // Status bar
    'status.gpu': 'GPU Готов',
    'status.cpu': 'Режим CPU',
    'status.ollama': 'Ollama Подключен',
    'status.ollama_off': 'Ollama Отключен',
    'status.vram': 'VRAM: Авто',

    'statusbar.vram_cleaner.title': 'Очистка VRAM — Память GPU',
    'statusbar.vram_cleaner.vram': 'VRAM:',
    'statusbar.vram_cleaner.kill': 'Завершить выбранное',
    'statusbar.vram_high_tooltip': 'Высокое использование VRAM — нажмите чтобы очистить фоновые процессы',
    'statusbar.restart_tooltip': 'Перезапустить бекенд и очистить кэш Python',
    'statusbar.restarted': 'Бекенд успешно перезапущен',
    'statusbar.restart_error': 'Не удалось перезапустить бекенд',

    // Additional settings
    'settings.gpu_limit': 'Лимит памяти GPU',
    'settings.gpu.auto': 'Авто (Рекомендуется)',
    'settings.gpu_desc': 'Ограничивает использование VRAM для ИИ моделей. "Авто" определяет доступную память.',
    'settings.auto_update': 'Проверка обновлений',
    'settings.auto_update_desc': 'Периодически проверять новые версии при запуске',
    'settings.speech_rec': 'Распознавание речи',
    'settings.whisper_model': 'Модель Whisper',
    'settings.whisper.tiny': 'Самая быстрая, низкая точность',
    'settings.whisper.base': 'Быстрая, низкая точность',
    'settings.whisper.small': 'Сбалансированная',
    'settings.whisper.medium': 'Хорошая точность',
    'settings.whisper.large': 'Лучшая точность (рекомендуется)',
    'settings.ollama_config': 'Настройки Ollama',
    'settings.ollama_url': 'URL сервера Ollama',
    'settings.keys.notice': 'API ключи хранятся безопасно в локальном keychain. Они не отправляются никуда, кроме как к соответствующему API-провайдеру.',
    'settings.keys.translation_apis': 'API Перевода',
    'settings.keys.speech_apis': 'Речевые и облачные API',
    'settings.keys.gemini_label': 'Ключ Google Gemini API',
    'settings.keys.gemini_get': 'Получить ключ Gemini ↗',
    'settings.keys.deepseek_label': 'Ключ DeepSeek API',
    'settings.keys.deepseek_get': 'Получить ключ DeepSeek ↗',
    'settings.keys.openai_label': 'Ключ OpenAI API',
    'settings.keys.openai_get': 'Получить ключ OpenAI ↗',
    'settings.keys.azure_label': 'Ключ Azure Speech',
    'settings.keys.azure_get': 'Получить ключ Azure ↗',
    'settings.keys.google_label': 'Ключ Google Cloud Speech API',
    'settings.keys.google_get': 'Получить ключ GCP ↗',
    'settings.keys.testing': 'Проверка...',
    'settings.keys.test_all': 'Проверить все подключения',
    'settings.keys.untested': 'Не проверено',
    'settings.keys.no_keys': 'Enter at least one API key to test.',
    'settings.keys.all_ok': 'All keys are valid!',
    'settings.keys.failed': 'Connection test failed',

    // Live Status
    'live.audio_status': 'Аудио статус',
    'live.standby': 'Ожидание',
    'live.listening': 'Лайв-захват',
    'live.status_audio': 'Захват системного звука',
    'live.status_audio.idle': 'Готово — нажмите Запустить',
    'live.status_audio.active': 'Захват звука с устройства по умолчанию',
    'live.status_engine': 'Движок перевода',
    'live.status_engine.idle': 'Ожидание аудиопотока',
    'live.status_engine.active': 'Активно — подключено к API',
    'live.status_overlay': 'Оверлей субтитров',
    'live.status_overlay.idle': 'Оверлей скрыт — появится после запуска',
    'live.status_overlay.active': 'Субтитры отображаются',

    // Dropdowns / Labels
    'lang.en': 'Английский',
    'lang.ru': 'Русский',
    'lang.tr': 'Турецкий',
    'lang.ar': 'Арабский',
    'lang.es': 'Испанский',
    'lang.fr': 'Французский',
    'lang.de': 'Немецкий',
    'lang.zh': 'Китайский',
    'lang.ja': 'Японский',
    'lang.ko': 'Корейский',
    'lang.it': 'Итальянский',
    'lang.pt': 'Португальский',
    'lang.pl': 'Польский',
    'lang.hi': 'Хинди',
    'pos.bottom': 'Внизу',
    'pos.top': 'Наверху',
    'pos.center': 'По центру',
    'size.small': 'Мелкий',
    'size.medium': 'Средний',
    'size.large': 'Крупный',

    // Voice models
    'dubbing.voice.qwen': 'Qwen3-TTS [локально]',
    'dubbing.voice.xtts': 'XTTSv2 [локально]',
    'dubbing.voice.f5': 'F5-TTS [локально]',
    'dubbing.voice.azure': 'Azure API [интернет, $]',
    'dubbing.voice.edge': 'Edge-TTS [интернет]',
    'dubbing.voice.qwen3_full': 'Qwen3-TTS (Локально)',
    'dubbing.voice.xttsv2_full': 'XTTSv2 (Локально)',
    'dubbing.voice.f5tts_full': 'F5-TTS PyTorch (Локально)',
    'dubbing.voice.f5onnx_full': 'F5-TTS ONNX Turkish (Локально, Быстро)',
    'dubbing.voice.azure_cloud': 'Azure Speech (Облако)',
    'dubbing.voice.edge_cloud': 'Edge TTS (Облако)',

    // Translation engines
    'dubbing.engine.deepseek': 'DeepSeek API [интернет, $]',
    'dubbing.engine.gemini': 'Google Gemini API [интернет, $]',
    'dubbing.engine.deepl': 'DeepL API [интернет, $]',
    'dubbing.engine.ollama': 'Ollama [локально]',
    'dubbing.engine.google': 'Google Translate [интернет]',

    // Settings keys
    'settings.hf_key': 'HuggingFace Token (Pyannote)',
    'settings.hf_desc': 'Необходим для диаризации (определения кто говорит)',
    'settings.hf_terms': 'Также необходимо принять условия использования моделей',
    'settings.hf_agree': 'На каждой странице нажмите "Agree and access repository" — иначе токен не заработает.',
    'settings.deepl_key': 'API Ключ DeepL',
    'settings.deepl_desc': 'Используется для высококачественного машинного перевода',

    // Dubbing advanced
    'dubbing.adv.mux': 'Авто-сведение видео',
    'dubbing.adv.mux_desc': 'Автоматически объединить сгенерированную аудиодорожку с оригинальным видео через FFmpeg',
    'dubbing.adv.clone': 'Клонирование голоса из оригинала',
    'dubbing.adv.clone_desc': 'Анализировать голос оригинального диктора и клонировать его для дубляжа вместо стандартного TTS-голоса',
    'dubbing.adv.demucs': 'Изоляция голоса через Demucs',
    'dubbing.adv.demucs_desc': 'Использовать Demucs AI для отделения голоса от фоновой музыки/шума перед расшифровкой, улучшая точность',
    'dubbing.adv.demucs_ft': 'Точная (лучшее качество)',
    'dubbing.adv.demucs_bal': 'Сбалансированная (быстрее)',
    'dubbing.adv.demucs_6s': '6-источников (чистейший вокал)',
    'dubbing.adv.export_srt': 'Экспорт SRT отдельно',
    'dubbing.adv.export_srt_desc': 'Сохранять файлы субтитров (.srt) отдельным файлом вместе с видео',
    'dubbing.adv.gender_ai': 'ИИ-подбор пола',
    'dubbing.adv.gender_ai_desc': 'Автоматически определять пол говорящего и подбирать подходящий TTS голос',
    'dubbing.adv.yt_subs': 'Субтитры YouTube',
    'dubbing.adv.yt_subs_desc': 'Использовать оригинальные субтитры YouTube вместо транскрибации через Whisper (если есть)',
    'dubbing.adv.lip_sync': 'Синхронизация губ (Lip Sync)',
    'dubbing.adv.lip_sync_desc': 'Синхронизировать движения губ с новой озвучкой (требует мощной видеокарты)',
    'dubbing.adv.keep_temp': 'Сохранять промежуточные файлы',
    'dubbing.adv.keep_temp_desc': 'Не удалять WAV, сырой текст и другие временные файлы после пайплайна',
    'dubbing.adv.auto_open': 'Авто-открытие папки',
    'dubbing.adv.auto_open_desc': 'Открыть папку с результатом автоматически после завершения',
    'dubbing.status.done': 'Пайплайн завершен',
    'dubbing.status.processing': 'Выполнение шага',
    'dubbing.badge.running': 'В процессе',
    'dubbing.badge.done': 'Завершено',
    'dubbing.log.title': 'Журнал пайплайна',
    'dubbing.log.entries': 'записей',
    'dubbing.log.copy': 'Копировать всё',
    'dubbing.log.copied': 'Логи скопированы',
    'dubbing.log.copy_failed': 'Не удалось скопировать',
    'dubbing.btn.open': 'Открыть результат',
    'dubbing.btn.new': 'Новый проект',
    'dubbing.review.title': 'Режим ручной проверки',
    'dubbing.review.desc': 'Пайплайн приостановлен после перевода. Проверьте и отредактируйте субтитры ниже, затем продолжите синтез речи.',
    'dubbing.review.original': 'Оригинальные субтитры',
    'dubbing.review.readonly': 'Только чтение',
    'dubbing.review.translated': 'Переведенные субтитры',
    'dubbing.review.editable': 'Можно редактировать',
    'dubbing.review.speaker': 'Спикер',
    'dubbing.review.time': 'Время',
    'dubbing.review.segments': 'сегментов',
    'dubbing.review.edit_hint': 'Кликните по переводу для редактирования',
    'dubbing.btn.continue': 'Продолжить генерацию голоса',
    'dubbing.btn.cancel': 'Отмена',

    // Settings TTS & models
    'settings.tts_audio': 'Синтез речи (TTS) и Аудио',
    'settings.tts_cache': 'Директория кэша TTS',
    'settings.browse': 'Обзор',
    'settings.model_status': 'Статус моделей',
    'settings.model_status_desc': 'Установленные модели и их статус загрузки.',
    'settings.installed': 'Установлено',
    
    // Model Downloader
    'dl.title': 'Добро пожаловать в AutoDub Studio!',
    'dl.desc': 'ИИ-модели необходимы для локального распознавания и генерации речи. Пожалуйста, скачайте выбранные модели, чтобы продолжить.',
    'dl.btn_download': 'Скачать выбранные',
    'dl.btn_skip': 'Пропустить',
    'dl.note': 'Вы можете скачать модели позже в меню настроек',
    'dl.downloading': 'Загрузка... (может занять 10-30 минут в зависимости от скорости интернета)',
    'dl.downloading_short': 'Загрузка...',
    'dl.queued': 'В очереди...',
    'dl.select_all': 'Выбрать все',
    'dl.btn_delete': 'Удалить',
    'dl.deleting': 'Удаление...',
    'dl.delete_confirm_title': 'Удалить модель?',
    'dl.delete_confirm_desc': 'Модель будет безвозвратно удалена с диска. Для использования функций потребуется повторная загрузка (10-30 минут).',
    'dl.models.demucs': 'ИИ изоляция вокала и разделение аудио',
    'dl.models.whisper': 'Локальное распознавание речи',
    'dl.models.pyannote': 'Разделение спикеров',
    'dl.models.qwen': 'Qwen3-TTS (Высокое качество)',
    'dl.models.f5': 'F5-TTS (Клонирование голоса)',
    'dl.models.xtts': 'XTTS v2 (Проф. клонирование)',
    'dl.models.gemma': 'Gemma 4 e4b (ИИ Перевод)',
    'dl.models.demucs_detail': 'ИИ изоляция вокала — не зависит от языка',
    'dl.models.whisper_detail': 'Распознавание речи — 99 языков',
    'dl.models.pyannote_detail': 'Диаризация спикеров — не зависит от языка',
    'dl.models.qwen_detail': 'Нейро TTS — ru, en, es, fr, zh',
    'dl.models.f5_detail': 'Клонирование голоса — ru, en, zh',
    'dl.models.xtts_detail': 'Клонирование голоса — 10 языков: ru, en, tr, es, fr, de, ar, it, pt, pl',
    'dl.models.gemma_detail': 'Локальный ИИ перевод через Ollama — все языки',
    'settings.about.tagline': 'ИИ-пайплайн для дубляжа видео',
    'settings.about.author': 'Автор',
    'settings.about.role': 'Программист промышленных роботов и ПО (Full-stack разработчик)',
    'settings.about.partner': 'При поддержке',
    'settings.about.links': 'Ссылки и ресурсы',
    'settings.about.github': 'Репозиторий GitHub',
    'settings.about.website': 'Сайт LiskinLabs',
  
    'live.settings': 'Настройки оверлея',
    'live.size': 'Размер текста',
    'settings.deepseek_desc': 'Доступная и функциональная модель перевода',
    'settings.deepseek_key': 'Ключ DeepSeek API',
    'settings.gemini_desc': 'Используется для контекстного перевода',
    'settings.gemini_key': 'Ключ Gemini API',
    'step.demucs': 'Demucs',
    'step.mux': 'Mux',
    'step.source': 'Source',
    'step.translate': 'Translate',
    'step.tts': 'TTS',
    'step.whisper': 'Whisper',

    // Command Palette
    'cmd.placeholder': 'Введите команду или поиск...',
    'cmd.no_results': 'Ничего не найдено.',
    'cmd.navigate': '↑↓ Навигация',
    'cmd.select': '↵ Выбрать',
    'cmd.close': 'Esc Закрыть',

    // HuggingFace
    'settings.keys.hf_get': 'Получить HF токен ↗',
    'settings.keys.azure_placeholder': 'Ключ подписки Azure',

    // Toasts
    'toast.pipeline_started': 'Пайплайн запущен',
    'toast.pipeline_init': 'Инициализация пайплайна...',
    'toast.pipeline_stopping': 'Остановка пайплайна...',
    'toast.pipeline_cancel': 'Отмена текущей операции',
    'toast.backend_error': 'Ошибка бэкенда',
    'toast.backend_offline': 'Python бэкенд не отвечает. Перезапустите приложение.',
    'ws.disconnect': 'Соединение с бекендом разорвано',

    // File filter
    'dubbing.file_filter': 'Видео',

    // Branding
    'brand.powered_by': 'При поддержке LiskinLabs',

    // App shell
    'app.skip_to_content': 'Пропустить',
    'app.search_commands': 'Поиск команд (Ctrl+K)',
    'app.toggle_theme': 'Сменить тему',
    'app.toggle_menu': 'Меню',

    // Breadcrumbs
    'breadcrumb.dubbing': 'Студия Дубляжа',
    'breadcrumb.live': 'Лайв Субтитры',
    'breadcrumb.chat': 'ИИ Чат',
    'breadcrumb.settings': 'Настройки',
    'breadcrumb.settings_models': 'Настройки · ИИ Модели',
    'breadcrumb.settings_keys': 'Настройки · Ключи API',
    'breadcrumb.settings_about': 'Настройки · О программе',

    // Error boundary
    'error.title': 'Что-то пошло не так',
    'error.default_message': 'Произошла непредвиденная ошибка.',
    'error.reported': 'Отчёт об ошибке отправлен автоматически. Мы разберёмся.',
    'error.sending': 'Отправка отчёта об ошибке...',
    'error.reload': 'Перезагрузить',

    // Update checker
    'update.available_title': 'Доступна версия v{version}!',
    'update.available_desc': 'Начинаем фоновую загрузку...',
    'update.downloading': 'Загрузка обновления ({size}MB)...',
    'update.notify_ready': 'Сообщим, когда будет готово.',
    'update.downloaded': 'Обновление загружено!',
    'update.restart_prompt': 'Перезапустить сейчас?',
    'update.failed': 'Ошибка загрузки обновления',
    'update.retry_later': 'Повторим при следующем запуске.',
    'update.installing': 'Установка обновления...',
    'update.restart_auto': 'Приложение перезапустится автоматически.',
    'update.install_failed': 'Ошибка установки',
    'update.restart_manual': 'Пожалуйста, перезапустите вручную.',
    'update.ready_label': 'v{version} готово',
    'update.click_to_install': 'Нажмите для установки',
    'update.downloading_label': 'Загрузка обновления...',
    'update.available_label': 'Доступно обновление',
    'update.checking': 'Проверка...',

    // GPU options
    'settings.gpu_4gb': '4 ГБ',
    'settings.gpu_6gb': '6 ГБ',
    'settings.gpu_8gb': '8 ГБ',
    'settings.gpu_12gb': '12 ГБ',

    // Keys test
    'settings.keys_all_valid': 'Все ключи валидны!',

    // About
    'settings.about.app_name': 'AutoDubStudio',
    'settings.about.version_badge': 'v0.0.1',
    'settings.about.tech_badge': 'Tauri v2 + React 19 + Fluent UI v9',
    'settings.about.author_name': 'Сильвестр Лискин',
    'settings.about.company': 'Teknorob Robot ve Otomasyon — Бурса, Турция',

    // Command palette
    'cmd.group_navigation': 'Навигация',
    'cmd.group_actions': 'Действия',
    'cmd.search_commands': 'Поиск команд',

    // Dubbing
    'dubbing.youtube_placeholder': 'https://youtube.com/watch?v=... или https://x.com/...',
    'dubbing.tab_local': 'Локальный файл',
    'dubbing.tab_youtube': 'YouTube / Web URL',
    // Theme labels
    'theme.light': 'Светлая',
    'theme.dark': 'Тёмная',
    'theme.dim': 'Тусклая',

    // Models display
    'models.count': '{count} моделей',
    'models.whisper_tiny': 'tiny',
    'models.whisper_base': 'base',
    'models.whisper_small': 'small',
    'models.whisper_medium': 'medium',
    'models.whisper_large_v2': 'large-v2',
    'models.whisper_large_v3': 'large-v3',

    // First-Run Wizard
    'frun.title': '🚀 Добро пожаловать в AutoDub Studio',
    'frun.subtitle': 'Для работы нужны несколько бесплатных программ. Выберите что установить — или нажмите «Установить всё».',
    'frun.ready': 'Готово',
    'frun.installing': 'Установка...',
    'frun.install': 'Установить',
    'frun.all_done': 'Всё готово — продолжить',
    'frun.install_all': 'Установить всё ({count})',
    'frun.installing_all': 'Устанавливаю...',
    'frun.instructions': 'Инструкция',
    'frun.skip': 'Пропустить — установлю позже вручную',
    'frun.footer': 'Все компоненты бесплатны и устанавливаются с официальных сайтов.',
    'frun.opened_url': 'Открыта страница загрузки — проверьте после установки',
    'frun.deps_python': 'Python 3.12+',
    'frun.deps_python_desc': 'Язык для AI-бекенда (распознавание речи, перевод, синтез)',
    'frun.deps_uv': 'uv (менеджер пакетов)',
    'frun.deps_uv_desc': 'Установка Python-зависимостей в 10-100x быстрее pip',
    'frun.deps_ollama': 'Ollama',
    'frun.deps_ollama_desc': 'Локальные AI-модели для перевода и чата',
    'frun.deps_ffmpeg': 'FFmpeg',
    'frun.deps_ffmpeg_desc': 'Обработка видео/аудио и сборка финального файла',
    'frun.deps_packages': 'AI Библиотеки',
    'frun.deps_packages_desc': 'PyTorch, F5-TTS, Whisper (займёт 5-10 минут)',
    'dubbing.yt.auth_btn': '🔑 Авторизация YouTube (Для субтитров)',
    'dubbing.yt.auth_btn_done': '✅ YouTube Авторизован',
    'dubbing.yt.scan': 'Скан URL',
    'dubbing.yt.scanning': 'Сканирование...',
    'dubbing.yt.download_only': 'Скачать выбранное',
    'dubbing.yt.download_mux': 'Скачать и собрать вместе',
    'dubbing.yt.downloading': 'Скачивание...',
    'dubbing.yt.subs': 'Субтитры',
    'dubbing.yt.audio': 'Аудиодорожки',
    'dubbing.yt.none': 'Не найдено',
    'dubbing.yt.description': 'Вы можете скачать медиа или использовать этот URL для ИИ-Дубляжа.',
  },
  tr: {
    // Navigation
    'nav.dubbing': 'Dublaj Stüdyosu',
    'nav.live': 'Canlı Altyazı',
    'nav.chat': 'Yapay Zeka Sohbet',
    'nav.settings': 'Ayarlar',
    'nav.tools': 'Araçlar',
    'nav.system': 'Sistem',

    // Settings
    'settings.title': 'Ayarlar',
    'settings.subtitle': 'Yerel ortamınızı, YZ modellerinizi ve bulut API entegrasyonlarını yapılandırın.',
    'settings.general': 'Genel',
    'settings.models': 'Yapay Zeka Modelleri',
    'settings.keys': 'API Anahtarları',
    'settings.about': 'Hakkında',
    'settings.appearance': 'Görünüm ve Dil',
    'settings.language': 'Dil',
    'settings.theme': 'Tema',
    'settings.performance': 'Performans',
    'settings.theme.light': 'Açık',
    'settings.theme.dim': 'Loş',
    'settings.theme.night': 'Gece',
    'settings.lang.en_label': 'İngilizce',
    'settings.lang.ru_label': 'Rusça (Russian)',
    'settings.lang.tr_label': 'Türkçe (Turkish)',

    // Dubbing
    'dubbing.title': 'Dublaj Stüdyosu',
    'dubbing.subtitle': 'Profesyonel yapay zeka video dublaj hattı. Yükle, yazıya dök, çevir ve seslendir — hepsi tek bir yerde.',
    'dubbing.dropzone': 'Video dosyasını sürükleyin veya YouTube URL\'sini yapıştırın',
    'dubbing.supported': 'MP4, MKV, AVI, WebM destekler',
    'dubbing.config': 'İşlem Ayarları',
    'dubbing.target_lang': 'Hedef Dil',
    'dubbing.voice_model': 'Yapay Zeka Ses Modeli',
    'dubbing.translation_engine': 'Çeviri Motoru',
    'dubbing.translator_model': 'Çeviri Modeli',
    'dubbing.mode': 'Çalışma Modu',
    'dubbing.mode.auto': 'Otomatik (Uçtan Uca)',
    'dubbing.mode.manual': 'Manuel Kontrol (Düzenleme için duraklat)',
    'dubbing.mode.auto_label': 'Otomatik',
    'dubbing.mode.auto_desc': 'YZ her şeyi halleder — kaynaktan dublajlı çıktıya kadar duraklama olmadan',
    'dubbing.mode.manual_label': 'Manuel Kontrol',
    'dubbing.mode.manual_desc': 'Çeviriden sonra inceleme ve düzenleme için seslendirme öncesinde duraklat',
    'dubbing.advanced': 'Gelişmiş Seçenekler',
    'dubbing.start': 'İşlemi Başlat',
    // Pipeline steps
    'dubbing.step.source': 'Kaynak',
    'dubbing.step.demucs': 'Demucs',
    'dubbing.step.whisper': 'Whisper',
    'dubbing.step.translate': 'Çeviri',
    'dubbing.step.tts': 'Seslendirme',
    'dubbing.step.mux': 'Birleştirme',
    // File & UI
    'dubbing.file.selected': 'Seçildi:',
    'dubbing.logs.waiting': 'Günlükler bekleniyor...',
    'dubbing.btn.paste': 'Yapıştır',
    'dubbing.btn.paste_title': 'Panodan yapıştır',
    'dubbing.no_models': 'Model bulunamadı',
    'dubbing.translator.deepl_api': 'DeepL Pro/Free API',
    'dubbing.translator.default': 'Varsayılan API Modeli',
    'dubbing.status.waiting_backend': 'Python motoru bekleniyor...',

    // Live
    'live.title': 'Canlı Altyazı',
    'live.subtitle': 'Toplantılar ve canlı yayınlar için eşzamanlı çeviri ve altyazı.',
    'live.callout': 'Zoom, Teams ve Google Meet için şeffaf altyazı katmanı. Sistem sesini yakalar, anında çevirir ve tüm pencerelerin üzerinde gösterir.',
    'live.config': 'Altyazı Ayarları',
    'live.source_lang': 'Kaynak Dil',
    'live.target_lang': 'Hedef Dil',
    'live.position': 'Altyazı Konumu',
    'live.fontsize': 'Yazı Tipi Boyutu',
    'live.start': 'Altyazıyı Başlat',
    'live.stop': 'Durdur',
    'live.auto': 'Otomatik Algıla',
    'live.engine_label': 'Çeviri Motoru',
    'live.engine.deepseek': 'DeepSeek API',
    'live.engine.whisper_local': 'Yerel Whisper',
    'live.preview': 'Canlı Önizleme',
    'live.recording': 'Kaydediyor',
    'live.waiting_audio': 'Ses girişi bekleniyor...',

    // Chat
    'chat.placeholder': 'Bir mesaj yazın...',
    'chat.empty.title': 'Sohbeti başlat',
    'chat.empty.subtitle': 'Yerel yapay zeka modellerinizle sohbet edin. Bunlar çeviri için kullanılan aynı modellerdir.',
    'chat.ollama_error': 'Ollama\'ya bağlanılamıyor. localhost:11434 üzerinde çalıştığından emin olun.',
    'chat.new_chat': 'Yeni Sohbet',
    'chat.no_models': 'İndirilmiş model yok (ollama pull kullanın)',
    'chat.send_title': 'Mesaj gönder',
    'chat.ollama_off_title': 'Yapay Zeka Kapalı',
    'chat.ollama_off_desc': 'Yerel yapay zeka motoru (Ollama) bellek tasarrufu için kapatıldı.',
    'chat.start_ollama': 'Ollama\'yı Başlat',
    'chat.stop_ollama': 'Kapat',
    'chat.refresh_models': 'Model listesini yenile',
    'chat.disclaimer': 'Yapay zeka hata yapabilir. Önemli bilgileri doğrulamanız önerilir.',
    'chat.model_selector': 'YZ modeli seç',
    'chat.connection_status': 'Bağlantı durumu',

    // Status bar
    'status.gpu': 'GPU Hazır',
    'status.cpu': 'CPU Modu',
    'status.ollama': 'Ollama Bağlı',
    'status.ollama_off': 'Ollama Çevrimdışı',
    'status.vram': 'VRAM: Otomatik',

    'statusbar.vram_cleaner.title': 'VRAM Temizleyici — GPU Belleği',
    'statusbar.vram_cleaner.vram': 'VRAM:',
    'statusbar.vram_cleaner.kill': 'Seçileni Sonlandır',
    'statusbar.vram_high_tooltip': 'Yüksek VRAM kullanımı — arka plan işlemlerini temizlemek için tıklayın',
    'statusbar.restart_tooltip': 'Arka ucu yeniden başlat ve Python önbelleğini temizle',
    'statusbar.restarted': 'Arka uç başarıyla yeniden başlatıldı',
    'statusbar.restart_error': 'Arka uç yeniden başlatılamadı',

    // Additional settings
    'settings.gpu_limit': 'GPU Bellek Sınırı',
    'settings.gpu.auto': 'Otomatik (Önerilen)',
    'settings.gpu_desc': 'Yerel YZ modelleri için VRAM kullanımını sınırlar. "Otomatik" kullanılabilir belleği algılar.',
    'settings.auto_update': 'Otomatik Güncelleme',
    'settings.auto_update_desc': 'Başlangıçta yeni sürümleri periyodik olarak kontrol et',
    'settings.speech_rec': 'Ses Tanıma',
    'settings.whisper_model': 'Whisper Modeli',
    'settings.whisper.tiny': 'En hızlı, en düşük doğruluk',
    'settings.whisper.base': 'Hızlı, düşük doğruluk',
    'settings.whisper.small': 'Dengeli',
    'settings.whisper.medium': 'İyi doğruluk',
    'settings.whisper.large': 'En iyi doğruluk (önerilen)',
    'settings.ollama_config': 'Ollama Ayarları',
    'settings.ollama_url': 'Ollama Sunucu URL\'si',
    'settings.keys.notice': 'API anahtarları yerel sistem anahtarlığınızda güvenli bir şekilde saklanır. İlgili API sağlayıcısı dışında hiçbir yere gönderilmezler.',
    'settings.keys.translation_apis': 'Çeviri API\'ları',
    'settings.keys.speech_apis': 'Ses ve Bulut API\'ları',
    'settings.keys.gemini_label': 'Google Gemini API Anahtarı',
    'settings.keys.gemini_get': 'Gemini Anahtarı Al ↗',
    'settings.keys.deepseek_label': 'DeepSeek API Anahtarı',
    'settings.keys.deepseek_get': 'DeepSeek Anahtarı Al ↗',
    'settings.keys.openai_label': 'OpenAI API Anahtarı',
    'settings.keys.openai_get': 'OpenAI Anahtarı Al ↗',
    'settings.keys.azure_label': 'Azure Speech Anahtarı',
    'settings.keys.azure_get': 'Azure Anahtarı Al ↗',
    'settings.keys.google_label': 'Google Cloud Speech API Anahtarı',
    'settings.keys.google_get': 'GCP Anahtarı Al ↗',
    'settings.keys.testing': 'Test ediliyor...',
    'settings.keys.test_all': 'Tüm Bağlantıları Test Et',
    'settings.keys.untested': 'Test edilmedi',
    'settings.keys.no_keys': 'Test etmek için en az bir API anahtarı girin.',
    'settings.keys.all_ok': 'Tüm anahtarlar geçerli!',
    'settings.keys.failed': 'Bağlantı testi başarısız',

    // Live Status
    'live.audio_status': 'Ses Durumu',
    'live.standby': 'Beklemede',
    'live.listening': 'Canlı Yakalama',
    'live.status_audio': 'Sistem Sesi Yakalama',
    'live.status_audio.idle': 'Hazır — başlatmak için Başlat\'a basın',
    'live.status_audio.active': 'Varsayılan çıkış cihazından ses yakalanıyor',
    'live.status_engine': 'Çeviri Motoru',
    'live.status_engine.idle': 'Boşta — ses akışı bekleniyor',
    'live.status_engine.active': 'Aktif — API bağlı',
    'live.status_overlay': 'Altyazı Katmanı',
    'live.status_overlay.idle': 'Katman gizli — başlatıldığında görünecek',
    'live.status_overlay.active': 'Altyazılar gösteriliyor',

    // Dropdowns / Labels
    'lang.en': 'İngilizce',
    'lang.ru': 'Rusça',
    'lang.tr': 'Türkçe',
    'lang.ar': 'Arapça',
    'lang.es': 'İspanyolca',
    'lang.fr': 'Fransızca',
    'lang.de': 'Almanca',
    'lang.zh': 'Çince',
    'lang.ja': 'Japonca',
    'lang.ko': 'Korece',
    'lang.it': 'İtalyanca',
    'lang.pt': 'Portekizce',
    'lang.pl': 'Lehçe',
    'lang.hi': 'Hintçe',
    'pos.bottom': 'Alt',
    'pos.top': 'Üst',
    'pos.center': 'Orta',
    'size.small': 'Küçük',
    'size.medium': 'Orta',
    'size.large': 'Büyük',

    // Voice models
    'dubbing.voice.qwen': 'Qwen3-TTS [yerel]',
    'dubbing.voice.xtts': 'XTTSv2 [yerel]',
    'dubbing.voice.f5': 'F5-TTS [yerel]',
    'dubbing.voice.azure': 'Azure API [internet, $]',
    'dubbing.voice.edge': 'Edge-TTS [internet]',
    'dubbing.voice.qwen3_full': 'Qwen3-TTS (Yerel)',
    'dubbing.voice.xttsv2_full': 'XTTSv2 (Yerel)',
    'dubbing.voice.f5tts_full': 'F5-TTS PyTorch (Yerel)',
    'dubbing.voice.f5onnx_full': 'F5-TTS ONNX Turkish (Yerel, Hızlı)',
    'dubbing.voice.azure_cloud': 'Azure Speech (Bulut)',
    'dubbing.voice.edge_cloud': 'Edge TTS (Bulut)',

    // Translation engines
    'dubbing.engine.deepseek': 'DeepSeek API [internet, $]',
    'dubbing.engine.gemini': 'Google Gemini API [internet, $]',
    'dubbing.engine.deepl': 'DeepL API [internet, $]',
    'dubbing.engine.ollama': 'Ollama [yerel]',
    'dubbing.engine.google': 'Google Translate [internet]',

    // Settings keys
    'settings.hf_key': 'HuggingFace Token (Pyannote)',
    'settings.hf_desc': 'Konuşmacı ayrımı için gereklidir (kimin konuştuğunu belirler)',
    'settings.hf_terms': 'Ayrıca bu modellerin kullanım koşullarını kabul etmelisiniz',
    'settings.hf_agree': 'Her sayfada "Agree and access repository" butonuna tıklayın — aksi takdirde token çalışmaz.',
    'settings.deepl_key': 'DeepL API Anahtarı',
    'settings.deepl_desc': 'Yüksek kaliteli makine çevirisi için kullanılır',

    // Dubbing advanced
    'dubbing.adv.mux': 'Videoyu Otomatik Birleştir',
    'dubbing.adv.mux_desc': 'Oluşturulan ses parçasını FFmpeg kullanarak orijinal video dosyasıyla otomatik olarak birleştir',
    'dubbing.adv.clone': 'Orijinalden Sesi Klonla',
    'dubbing.adv.clone_desc': 'Orijinal konuşmacının sesini analiz et ve dublajlı ses için genel bir TTS sesi yerine klonla',
    'dubbing.adv.demucs': 'Demucs ile Sesi Ayrıştır',
    'dubbing.adv.demucs_desc': 'Yazıya dökmeden önce sesi arka plan müzik/gürültüden ayırmak için Demucs AI kullan, doğruluğu artır',
    'dubbing.adv.demucs_ft': 'İnce ayarlı (en iyi kalite)',
    'dubbing.adv.demucs_bal': 'Dengeli (daha hızlı)',
    'dubbing.adv.demucs_6s': '6-kaynaklı (en temiz vokal)',
    'dubbing.adv.export_srt': 'SRT\'yi Ayrı Kaydet',
    'dubbing.adv.export_srt_desc': 'Altyazı dosyalarını (.srt) video ile birlikte ayrı çıktı olarak kaydet',
    'dubbing.adv.gender_ai': 'Yapay Zeka Cinsiyet Eşleştirme',
    'dubbing.adv.gender_ai_desc': 'Orijinal konuşmacının cinsiyetini otomatik algıla ve TTS sesini eşleştir',
    'dubbing.adv.yt_subs': 'YouTube Altyazılarını Kullan',
    'dubbing.adv.yt_subs_desc': 'Whisper ile deşifre etmek yerine (varsa) orijinal YouTube altyazılarını tercih et',
    'dubbing.adv.lip_sync': 'Yapay Zeka Dudak Senkronizasyonu',
    'dubbing.adv.lip_sync_desc': 'Konuşmacının dudak hareketlerini yeni dublajlı ses ile senkronize et (yüksek GPU gücü gerektirir)',
    'dubbing.adv.keep_temp': 'Ara Dosyaları Sakla',
    'dubbing.adv.keep_temp_desc': 'WAV, ham metin ve diğer geçici dosyaları işlem tamamlandıktan sonra silme',
    'dubbing.adv.auto_open': 'Klasörü Otomatik Aç',
    'dubbing.adv.auto_open_desc': 'İşlem tamamlandığında çıktı klasörünü otomatik olarak aç',
    'dubbing.status.done': 'İşlem tamamlandı',
    'dubbing.status.processing': 'Adım işleniyor',
    'dubbing.badge.running': 'Çalışıyor',
    'dubbing.badge.done': 'Tamamlandı',
    'dubbing.log.title': 'İşlem Günlüğü',
    'dubbing.log.entries': 'kayıt',
    'dubbing.log.copy': 'Tümünü Kopyala',
    'dubbing.log.copied': 'Günlükler panoya kopyalandı',
    'dubbing.log.copy_failed': 'Kopyalanamadı',
    'dubbing.btn.open': 'Çıktı Dosyasını Aç',
    'dubbing.btn.new': 'Yeni Proje',
    'dubbing.review.title': 'Manuel Kontrol Modu',
    'dubbing.review.desc': 'İşlem çeviriden sonra duraklatıldı. Çevrilen altyazıları aşağıda inceleyip düzenleyin, ardından ses oluşturmaya devam edin.',
    'dubbing.review.original': 'Orijinal Altyazılar',
    'dubbing.review.readonly': 'Salt Okunur',
    'dubbing.review.translated': 'Çevrilmiş Altyazılar',
    'dubbing.review.editable': 'Düzenlenebilir',
    'dubbing.review.speaker': 'Konuşmacı',
    'dubbing.review.time': 'Zaman',
    'dubbing.review.segments': 'segment',
    'dubbing.review.edit_hint': 'Düzenlemek için çeviriye tıklayın',
    'dubbing.btn.continue': 'Ses Üretimine Devam Et',
    'dubbing.btn.cancel': 'İptal',

    // Settings TTS & models
    'settings.tts_audio': 'Ses Sentezi (TTS) ve Ses',
    'settings.tts_cache': 'TTS Önbellek Dizini',
    'settings.browse': 'Göz At',
    'settings.model_status': 'Model Durumu',
    'settings.model_status_desc': 'Yüklü modeller ve indirme durumları.',
    'settings.installed': 'Yüklendi',
    
    // Model Downloader
    'dl.title': 'AutoDub Studio\'ya Hoş Geldiniz!',
    'dl.desc': 'Yerel ses tanıma ve üretim için yapay zeka modelleri gereklidir. Devam etmek için lütfen seçili modelleri indirin.',
    'dl.btn_download': 'Seçilenleri İndir',
    'dl.btn_skip': 'Şimdilik Atla',
    'dl.note': 'Modelleri daha sonra ayarlar menüsünden indirebilirsiniz',
    'dl.downloading': 'İndiriliyor... (internet hızına bağlı olarak 10-30 dakika sürebilir)',
    'dl.downloading_short': 'İndiriliyor...',
    'dl.queued': 'Sırada...',
    'dl.select_all': 'Tümünü Seç',
    'dl.btn_delete': 'Sil',
    'dl.deleting': 'Siliniyor...',
    'dl.delete_confirm_title': 'Model silinsin mi?',
    'dl.delete_confirm_desc': 'Model diskten kalıcı olarak silinecek. Özellikleri kullanmak için tekrar indirmeniz gerekecek (10-30 dakika).',
    'dl.models.demucs': 'YZ vokal izolasyonu ve ses ayrıştırma',
    'dl.models.whisper': 'Yerel yapay zeka ses tanıma',
    'dl.models.pyannote': 'Konuşmacı ayrıştırma',
    'dl.models.qwen': 'Qwen3-TTS (Yüksek Kalite)',
    'dl.models.f5': 'F5-TTS (Ses Klonlama)',
    'dl.models.xtts': 'XTTS v2 (Prof. Klonlama)',
    'dl.models.gemma': 'Gemma 4 e4b (YZ Çeviri)',
    'dl.models.demucs_detail': 'YZ vokal izolasyonu — dilden bağımsız',
    'dl.models.whisper_detail': 'Ses tanıma — 99 dil',
    'dl.models.pyannote_detail': 'Konuşmacı ayrıştırma — dilden bağımsız',
    'dl.models.qwen_detail': 'Nöral TTS — ru, en, es, fr, zh',
    'dl.models.f5_detail': 'Sıfır atış ses klonlama — ru, en, zh',
    'dl.models.xtts_detail': 'Ses klonlama TTS — 10 dil: ru, en, tr, es, fr, de, ar, it, pt, pl',
    'dl.models.gemma_detail': 'Yerel YZ çeviri (Ollama) — tüm diller',

    // About
    'settings.about.tagline': 'YZ Destekli Video Dublaj Hattı',
    'settings.about.author': 'Yazar',
    'settings.about.role': 'Endüstriyel Robot ve Yazılım Programcısı (Full-stack Geliştirici)',
    'settings.about.partner': 'İş birliğiyle',
    'settings.about.links': 'Bağlantılar ve Kaynaklar',
    'settings.about.github': 'GitHub Deposu',
    'settings.about.website': 'LiskinLabs Web Sitesi',
  
    'live.settings': 'Altyazı Katmanı Ayarları',
    'live.size': 'Yazı Boyutu',
    'settings.deepseek_desc': 'Uygun fiyatlı ve yetenekli çeviri modeli',
    'settings.deepseek_key': 'DeepSeek API Anahtarı',
    'settings.gemini_desc': 'Bağlam duyarlı çeviri için kullanılır',
    'settings.gemini_key': 'Gemini API Anahtarı',
    'step.demucs': 'Demucs',
    'step.mux': 'Mux',
    'step.source': 'Source',
    'step.translate': 'Translate',
    'step.tts': 'TTS',
    'step.whisper': 'Whisper',

    // Command Palette
    'cmd.placeholder': 'Komut yazın veya arama yapın...',
    'cmd.no_results': 'Sonuç bulunamadı.',
    'cmd.navigate': '↑↓ Gezin',
    'cmd.select': '↵ Seç',
    'cmd.close': 'Esc Kapat',

    // HuggingFace
    'settings.keys.hf_get': 'HF Tokeni Al ↗',
    'settings.keys.azure_placeholder': 'Azure Abonelik Anahtarı',

    // Toasts
    'toast.pipeline_started': 'İşlem başlatıldı',
    'toast.pipeline_init': 'İşlem başlatılıyor...',
    'toast.pipeline_stopping': 'İşlem durduruluyor...',
    'toast.pipeline_cancel': 'Mevcut işlem iptal ediliyor',
    'toast.backend_error': 'Arka Uç Hatası',
    'toast.backend_offline': 'Python arka ucu çevrimdışı. Lütfen uygulamayı yeniden başlatın.',
    'ws.disconnect': 'Arka uç bağlantısı kesildi',

    // File filter
    'dubbing.file_filter': 'Video',

    // Branding
    'brand.powered_by': 'LiskinLabs Tarafından Desteklenmektedir',

    // App shell
    'app.skip_to_content': 'Ana içeriğe geç',
    'app.search_commands': 'Komut ara (Ctrl+K)',
    'app.toggle_theme': 'Tema değiştir',
    'app.toggle_menu': 'Menü',

    // Breadcrumbs
    'breadcrumb.dubbing': 'Dublaj Stüdyosu',
    'breadcrumb.live': 'Canlı Altyazı',
    'breadcrumb.chat': 'YZ Sohbet',
    'breadcrumb.settings': 'Ayarlar',
    'breadcrumb.settings_models': 'Ayarlar · YZ Modelleri',
    'breadcrumb.settings_keys': 'Ayarlar · API Anahtarları',
    'breadcrumb.settings_about': 'Ayarlar · Hakkında',

    // Error boundary
    'error.title': 'Bir şeyler yanlış gitti',
    'error.default_message': 'Beklenmeyen bir hata oluştu.',
    'error.reported': 'Hata raporu otomatik gönderildi. Ekibimiz inceleyecek.',
    'error.sending': 'Hata raporu gönderiliyor...',
    'error.reload': 'Yeniden Yükle',

    // Update checker
    'update.available_title': 'v{version} güncellemesi mevcut!',
    'update.available_desc': 'Arka planda indiriliyor...',
    'update.downloading': 'Güncelleme indiriliyor ({size}MB)...',
    'update.notify_ready': 'Hazır olduğunda bildireceğiz.',
    'update.downloaded': 'Güncelleme indirildi!',
    'update.restart_prompt': 'Şimdi yeniden başlatılsın mı?',
    'update.failed': 'Güncelleme indirilemedi',
    'update.retry_later': 'Sonraki başlatmada tekrar denenecek.',
    'update.installing': 'Güncelleme kuruluyor...',
    'update.restart_auto': 'Uygulama otomatik yeniden başlayacak.',
    'update.install_failed': 'Güncelleme kurulamadı',
    'update.restart_manual': 'Lütfen manuel olarak yeniden başlatın.',
    'update.ready_label': 'v{version} hazır',
    'update.click_to_install': 'Kurmak için tıklayın',
    'update.downloading_label': 'Güncelleme indiriliyor...',
    'update.available_label': 'Güncelleme mevcut',
    'update.checking': 'Kontrol ediliyor...',

    // GPU options
    'settings.gpu_4gb': '4 GB',
    'settings.gpu_6gb': '6 GB',
    'settings.gpu_8gb': '8 GB',
    'settings.gpu_12gb': '12 GB',

    // Keys test
    'settings.keys_all_valid': 'Tüm anahtarlar geçerli!',

    // About
    'settings.about.app_name': 'AutoDubStudio',
    'settings.about.version_badge': 'v0.0.1',
    'settings.about.tech_badge': 'Tauri v2 + React 19 + Fluent UI v9',
    'settings.about.author_name': 'Silvestr Liskin',
    'settings.about.company': 'Teknorob Robot ve Otomasyon — Bursa, TR',

    // Command palette
    'cmd.group_navigation': 'Navigasyon',
    'cmd.group_actions': 'Eylemler',
    'cmd.search_commands': 'Komut ara',

    // Dubbing
    'dubbing.youtube_placeholder': 'https://youtube.com/watch?v=... veya https://x.com/...',
    'dubbing.tab_local': 'Yerel Dosya',
    'dubbing.tab_youtube': 'YouTube / Web URL',
    // Theme labels
    'theme.light': 'Açık',
    'theme.dark': 'Koyu',
    'theme.dim': 'Loş',

    // Models display
    'models.count': '{count} model',
    'models.whisper_tiny': 'tiny',
    'models.whisper_base': 'base',
    'models.whisper_small': 'small',
    'models.whisper_medium': 'medium',
    'models.whisper_large_v2': 'large-v2',
    'models.whisper_large_v3': 'large-v3',

    // First-Run Wizard
    'frun.title': '🚀 AutoDub Studio\'ya Hoş Geldiniz',
    'frun.subtitle': 'Bu uygulama için birkaç ücretsiz program gerekiyor. Kurmak istediklerinizi seçin — veya "Tümünü Kur"a tıklayın.',
    'frun.ready': 'Hazır',
    'frun.installing': 'Kuruluyor...',
    'frun.install': 'Kur',
    'frun.all_done': 'Her şey hazır — devam et',
    'frun.install_all': 'Tümünü Kur ({count})',
    'frun.installing_all': 'Kuruluyor...',
    'frun.instructions': 'Talimatlar',
    'frun.skip': 'Atla — daha sonra manuel kuracağım',
    'frun.footer': 'Tüm bileşenler ücretsizdir ve resmi sitelerden kurulur.',
    'frun.opened_url': 'İndirme sayfası açıldı — kurulumdan sonra kontrol edin',
    'frun.deps_python': 'Python 3.12+',
    'frun.deps_python_desc': 'YZ arka ucu için dil (ses tanıma, çeviri, sentez)',
    'frun.deps_uv': 'uv (paket yöneticisi)',
    'frun.deps_uv_desc': 'Python bağımlılıklarını pip\'ten 10-100x daha hızlı kurun',
    'frun.deps_ollama': 'Ollama',
    'frun.deps_ollama_desc': 'Çeviri ve sohbet için yerel YZ modelleri',
    'frun.deps_ffmpeg': 'FFmpeg',
    'frun.deps_ffmpeg_desc': 'Video/ses işleme ve son birleştirme',
    'frun.deps_packages': 'Yapay Zeka Kütüphaneleri',
    'frun.deps_packages_desc': 'PyTorch, F5-TTS, Whisper (5-10 dakika sürer)',
    'dubbing.yt.auth_btn': '🔑 YouTube Girişi (Altyazılar İçin)',
    'dubbing.yt.auth_btn_done': '✅ YouTube Yetkilendirildi',
    'dubbing.yt.scan': 'URL Tara',
    'dubbing.yt.scanning': 'Taranıyor...',
    'dubbing.yt.download_only': 'Sadece Seçilenleri İndir',
    'dubbing.yt.download_mux': 'İndir ve Videoya Ekle',
    'dubbing.yt.downloading': 'İndiriliyor...',
    'dubbing.yt.subs': 'Mevcut Altyazılar',
    'dubbing.yt.audio': 'Mevcut Ses Dosyaları',
    'dubbing.yt.none': 'Bulunamadı',
    'dubbing.yt.description': 'Medyayı indirebilir veya bu URL yi doğrudan Yapay Zeka Dublaj motoruna gönderebilirsiniz.',
  }
};

class SettingsStore {
  language: Language = 'en';
  theme: string = 'dim';        // dim (teamsDarkTheme) — best Win11 default
  themeLight: string = 'light'; // webLightTheme
  themeDark: string = 'dim';    // teamsDarkTheme
  apiKeys: Record<string, string> = {};
  listeners: Set<() => void> = new Set();
  private _store: Store | null = null;
  private _storeReady!: Promise<void>;

  constructor() {
    try {
      const sysLang = navigator.language.toLowerCase();
      if (sysLang.startsWith('ru')) {
        this.language = 'ru';
      } else if (sysLang.startsWith('tr')) {
        this.language = 'tr';
      } else {
        this.language = 'en';
      }
    } catch (e) {
      this.language = 'en';
    }
    this._storeReady = this._initStore();
  }

  private async _initStore() {
    try {
      this._store = await Store.load('autodub-settings.json');
      const storedTheme = await this._store.get<string>('theme');
      const storedLight = await this._store.get<string>('themeLight');
      const storedDark = await this._store.get<string>('themeDark');
      const storedLang = await this._store.get<Language>('language');
      if (storedLang) this.language = storedLang;
      if (storedTheme) this.theme = storedTheme;
      else this.theme = 'dim';
      if (storedLight) this.themeLight = storedLight;
      if (storedDark) this.themeDark = storedDark;
      // Theme is handled by FluentProvider in main.tsx — no data-theme attribute needed
      const stored = await this._store.get<Record<string, string>>('apiKeys');

      if (stored && typeof stored === 'object') {
        this.apiKeys = stored;
      } else {
        // Migration: read from old localStorage and move to Tauri Store
        const legacy = localStorage.getItem('autodub_api_keys');
        if (legacy) {
          try {
            this.apiKeys = JSON.parse(legacy);
            await this._store.set('apiKeys', this.apiKeys);
            await this._store.save();
            localStorage.removeItem('autodub_api_keys'); // Clean up legacy
            console.log('[SECURITY] Migrated API keys from localStorage to Tauri Store');
          } catch (e) {
            console.error('Migration failed:', e);
          }
        }
      }
      // Notify subscribers that keys have been loaded
      this.notify();
    } catch (_err) {
      // Fallback: Tauri Store not available (e.g., running in browser dev mode)
      const saved = localStorage.getItem('autodub_api_keys');
      if (saved) {
        try { this.apiKeys = JSON.parse(saved); } catch (e) { console.error(e); }
        this.notify();
      }
    }
  }

  async _persistKeys() {
    await this._storeReady;
    if (this._store) {
      await this._store.set('apiKeys', this.apiKeys);
      await this._store.save();
    }
    // SECURITY: Never fall back to localStorage for API keys.
    // If Tauri Store is unavailable, keys are kept in memory only for this session.
  }

  async setLanguage(lang: Language) {
    this.language = lang;
    await this._storeReady;
    if (this._store) {
      await this._store.set('language', lang);
      await this._store.save();
    }
    this.notify();
  }

  async setTheme(theme: string) {
    this.theme = theme;
    // Remember light/dark preference
    if (isThemeDark(theme)) {
      this.themeDark = theme;
    } else {
      this.themeLight = theme;
    }
    await this._storeReady;
    if (this._store) {
      await this._store.set('theme', theme);
      await this._store.set('themeLight', this.themeLight);
      await this._store.set('themeDark', this.themeDark);
      await this._store.save();
    }
    this.notify();
  }

  async toggleTheme() {
    const next = isThemeDark(this.theme) ? this.themeLight : this.themeDark;
    await this.setTheme(next);
  }

  async setApiKeys(keys: Record<string, string>) {
    this.apiKeys = keys;
    await this._persistKeys();
    this.notify();
  }

  notify() {
    this.listeners.forEach(l => l());
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  t(key: string) {
    return translations[this.language]?.[key] || translations.en[key] || key;
  }
}

export const settingsStore = new SettingsStore();

import { useMemo } from 'react';

export function useSettings() {
  const [, setTick] = useState(0);

  useEffect(() => {
    const unsub = settingsStore.subscribe(() => setTick(t => t + 1));
    return () => { unsub(); };
  }, []);

  return useMemo(() => ({
    lang: settingsStore.language,
    theme: settingsStore.theme,
    setLanguage: (l: Language) => settingsStore.setLanguage(l),
    themeLight: settingsStore.themeLight,
    themeDark: settingsStore.themeDark,
    setTheme: (t: string) => settingsStore.setTheme(t),
    toggleTheme: () => settingsStore.toggleTheme(),
    setApiKeys: (keys: Record<string, string>) => settingsStore.setApiKeys(keys),
    settings: {
      geminiKey: settingsStore.apiKeys.gemini || '',
      deepseekKey: settingsStore.apiKeys.deepseek || '',
      deeplKey: settingsStore.apiKeys.deepl || '',
      hfKey: settingsStore.apiKeys.huggingface || '',
      azureKey: settingsStore.apiKeys.azure || '',
      openaiKey: settingsStore.apiKeys.openai || '',
      googleKey: settingsStore.apiKeys.google || '',
    },
    apiKeys: settingsStore.apiKeys,
    t: (key: string): string => settingsStore.t(key) as string
  }), [settingsStore.language, settingsStore.theme, settingsStore.apiKeys]);
}
