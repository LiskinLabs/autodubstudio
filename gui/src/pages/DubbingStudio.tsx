import { useState, useCallback, useEffect, type DragEvent, type ChangeEvent } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { useSettings } from '../store';
import { useOllama } from '../hooks/useOllama';
import { usePipelineWebSocket } from '../hooks/usePipelineWebSocket';
import { notifyToast } from '../lib/toast';
import VirtualLogViewer from '../components/VirtualLogViewer';

/* ─── Types ─── */
type PipelineState = 'idle' | 'running' | 'review' | 'done';

type PipelineMode = 'automatic' | 'manual';

interface Config {
  targetLanguage: string;
  voiceModel: string;
  translationEngine: string;
  translatorModel: string;
  pipelineMode: PipelineMode;
  autoMux: boolean;
  voiceCloning: boolean;
  audioSeparation: boolean;
}

/* ─── Constants ─── */
const PIPELINE_STEP_KEYS = ['source', 'demucs', 'whisper', 'translate', 'tts', 'mux'] as const;
type StepKey = (typeof PIPELINE_STEP_KEYS)[number];
const STEP_T_KEY: Record<StepKey, string> = {
  source: 'dubbing.step.source',
  demucs: 'dubbing.step.demucs',
  whisper: 'dubbing.step.whisper',
  translate: 'dubbing.step.translate',
  tts: 'dubbing.step.tts',
  mux: 'dubbing.step.mux',
};

/* ─── SVG Icons ─── */
function FilmIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
      <line x1="7" y1="2" x2="7" y2="22" />
      <line x1="17" y1="2" x2="17" y2="22" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="2" y1="7" x2="7" y2="7" />
      <line x1="2" y1="17" x2="7" y2="17" />
      <line x1="17" y1="7" x2="22" y2="7" />
      <line x1="17" y1="17" x2="22" y2="17" />
    </svg>
  );
}

function ClipboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="4" rx="1" />
      <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5.14v14l11-7-11-7z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transition: 'transform 200ms ease', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

// Imports moved to top

const LANG_T_KEY: Record<string, string> = {
  ru: 'lang.ru', tr: 'lang.tr', en: 'lang.en', es: 'lang.es', fr: 'lang.fr',
  de: 'lang.de', ar: 'lang.ar', zh: 'lang.zh', ja: 'lang.ja', ko: 'lang.ko',
  it: 'lang.it', pt: 'lang.pt', pl: 'lang.pl', hi: 'lang.hi',
};

const LANGUAGE_OPTIONS = ['ru', 'tr', 'en', 'es', 'fr', 'de', 'ar', 'zh', 'ja', 'ko', 'it', 'pt', 'pl', 'hi'];

const TTS_MODELS_BY_LANG: Record<string, string[]> = {
  'ru': ['qwen3-tts', 'xttsv2', 'f5-tts', 'azure', 'edge-tts'],
  'en': ['qwen3-tts', 'xttsv2', 'f5-tts', 'azure', 'edge-tts'],
  'tr': ['xttsv2', 'azure', 'edge-tts'],
  'es': ['qwen3-tts', 'xttsv2', 'azure', 'edge-tts'],
  'fr': ['qwen3-tts', 'xttsv2', 'azure', 'edge-tts'],
  'de': ['xttsv2', 'azure', 'edge-tts'],
  'ar': ['xttsv2', 'azure', 'edge-tts'],
  'zh': ['qwen3-tts', 'f5-tts', 'azure', 'edge-tts'],
  'ja': ['azure', 'edge-tts'],
  'ko': ['azure', 'edge-tts'],
  'it': ['xttsv2', 'azure', 'edge-tts'],
  'pt': ['xttsv2', 'azure', 'edge-tts'],
  'pl': ['xttsv2', 'azure', 'edge-tts'],
  'hi': ['azure', 'edge-tts']
};

const TTS_T_KEY: Record<string, string> = {
  'qwen3-tts': 'dubbing.voice.qwen3_full',
  'xttsv2': 'dubbing.voice.xttsv2_full',
  'f5-tts': 'dubbing.voice.f5tts_full',
  'azure': 'dubbing.voice.azure_cloud',
  'edge-tts': 'dubbing.voice.edge_cloud',
};

/* ─── Component ─── */
export default function DubbingStudio() {
  const { t, settings } = useSettings();
  /* State */
  const [pipelineState, setPipelineState] = useState<PipelineState>('idle');
  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [fileName, setFileName] = useState('');
  const [translatedSrt, setTranslatedSrt] = useState<string>('');
  
  const [logs, setLogs] = useState<string[]>([]);
  const [originalSegments, setOriginalSegments] = useState<string[]>([]);
  const [_translatedSegments, setTranslatedSegments] = useState<string[]>([]);
  const [editedSegments, setEditedSegments] = useState<any[]>([]);

  const onProgress = useCallback((val: number) => setProgress(val), []);
  const onLog = useCallback((text: string) => {
    setLogs(prev => [...prev, text]);
    // Try to guess active step based on logs
    const lower = text.toLowerCase();
    if (lower.includes('demucs')) setActiveStep(2);
    else if (lower.includes('whisper') || lower.includes('распознавание')) setActiveStep(3);
    else if (lower.includes('перевод') || lower.includes('translate')) setActiveStep(4);
    else if (lower.includes('озвучка') || lower.includes('tts')) setActiveStep(5);
    else if (lower.includes('сборка') || lower.includes('ffmpeg')) setActiveStep(6);
  }, []);
  
  const onReviewReady = useCallback((orig: string[], trans: string[], segments: any[]) => {
    setOriginalSegments(orig);
    setTranslatedSegments(trans);
    setEditedSegments(segments);
    setPipelineState('review');
    setTranslatedSrt(trans.join('\n\n'));
  }, []);
  
  const onFinished = useCallback((success: boolean, msg: string) => {
    setPipelineState('done');
    onLog(`[FINISHED] Success: ${success}, Message: ${msg}`);
  }, [onLog]);

  const { isConnected: _isConnected, startPipeline, resumePipeline, stopPipeline } = usePipelineWebSocket(
    onProgress, onLog, onReviewReady, onFinished
  );

  const { models: ollamaModels, checkConnection } = useOllama();

  const [config, setConfig] = useState<Config>({
    targetLanguage: 'ru',
    voiceModel: 'xttsv2',
    translationEngine: 'deepseek',
    translatorModel: 'gemma2',
    pipelineMode: 'automatic',
    autoMux: true,
    voiceCloning: true,
    audioSeparation: true,
  });

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  // When language changes, auto-select a valid TTS model if current is incompatible
  useEffect(() => {
    const validModels = TTS_MODELS_BY_LANG[config.targetLanguage] || [];
    if (!validModels.includes(config.voiceModel)) {
      if (validModels.length > 0) {
        updateConfig('voiceModel', validModels[0]);
      }
    }
  }, [config.targetLanguage, config.voiceModel]);

  // When engine changes, auto-select a valid translator model
  useEffect(() => {
    if (config.translationEngine === 'ollama' && ollamaModels.length > 0) {
      if (!ollamaModels.includes(config.translatorModel)) {
        updateConfig('translatorModel', ollamaModels[0]);
      }
    } else if (config.translationEngine === 'deepseek') {
      updateConfig('translatorModel', 'deepseek-chat');
    } else if (config.translationEngine === 'google' || config.translationEngine === 'gemini') {
      updateConfig('translatorModel', 'default');
    }
  }, [config.translationEngine, ollamaModels, config.translatorModel]);

  /* Handlers */
  const updateConfig = useCallback(<K extends keyof Config>(key: K, value: Config[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setFileName(files[0].name);
    }
  }, []);

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setYoutubeUrl(text);
    } catch {
      // clipboard access denied
    }
  }, []);

  const handleStartPipeline = useCallback(() => {
    if (!fileName && !youtubeUrl) return;
    const toastId = notifyToast.loading(t('toast.pipeline_started'), { description: t('toast.pipeline_init') });
    setPipelineState('running');
    setActiveStep(1);
    setProgress(0);
    setLogs([]);
    startPipeline({
      video_path: fileName || youtubeUrl,
      out_dir: '',
      langs: [config.targetLanguage.toLowerCase()],
      model_size: 'base',
      device: 'cuda',
      translation_engine: config.translationEngine,
      gemini_key: settings.geminiKey,
      deepseek_key: settings.deepseekKey,
      deepl_key: settings.deeplKey,
      manual_mode: config.pipelineMode === 'manual'
    });
    // Store toastId for later dismissal
    (window as any).__pipelineToast = toastId;
  }, [fileName, youtubeUrl, config, startPipeline, settings]);

  const handleContinueFromReview = useCallback(() => {
    setPipelineState('running');
    setActiveStep(5);
    setProgress(67);
    resumePipeline(editedSegments);
  }, [resumePipeline, editedSegments]);

  const handleReset = useCallback(() => {
    setPipelineState('idle');
    setActiveStep(0);
    setProgress(0);
    setFileName('');
    setYoutubeUrl('');
  }, []);

  const handleSelectFile = async () => {
    try {
      const selected = await open({
        multiple: false,
        filters: [{
          name: t('dubbing.file_filter'),
          extensions: ['mp4', 'mkv', 'avi', 'webm', 'mov']
        }]
      });
      if (selected) {
        setFileName(selected as string);
      }
    } catch (e) {
      console.error(e);
    }
  };

  /* Helpers */
  const getStepState = (stepNumber: number): string => {
    if (stepNumber < activeStep) return 'done';
    if (stepNumber === activeStep) return 'active';
    return '';
  };

  const getConnectorState = (stepNumber: number): string => {
    return stepNumber < activeStep ? 'done' : '';
  };

  // const logTypeClass = (type: 'info' | 'success' | 'warning' | 'error'): string => {
  //   return `log-${type}`;
  // };

  /* Render helpers */
  const renderSwitch = (label: string, checked: boolean, onChange: (v: boolean) => void, tooltip?: string) => (
    <div className="flex items-center justify-between" style={{ padding: 'var(--space-2) 0' }} title={tooltip}>
      <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="switch-slider" />
      </label>
    </div>
  );

  return (
    <div className="page">
      {/* ─── Header ─── */}
      <div className="page-header">
        <h1 className="page-title">{t('dubbing.title')}</h1>
        <p className="page-subtitle">
          {t('dubbing.subtitle')}
        </p>
      </div>

      {/* ─── Idle: Input & Config ─── */}
      {(pipelineState === 'idle') && (
        <>
          {/* Drop Zone */}
          <div
            className={`drop-zone${isDragging ? ' drag-over' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleSelectFile}
            style={{ marginBottom: 'var(--space-6)', cursor: 'pointer' }}
          >
            <div className="drop-zone-icon">
              <FilmIcon />
            </div>
            <div className="drop-zone-text">
              {fileName
                ? <>{t('dubbing.file.selected')} <strong>{fileName}</strong></>
                : <div style={{ fontWeight: 500 }}>{t('dubbing.dropzone')}</div>
              }
            </div>
            <div className="text-sm text-muted">{t('dubbing.supported')}</div>
          </div>
            {/* Log Viewer */}
          <div className="log-viewer" style={{ marginTop: 'var(--space-4)', flex: 1 }}>
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text-tertiary)' }}>{t('dubbing.logs.waiting')}</div>
            ) : (
              <VirtualLogViewer logs={logs} />
            )}
          </div>

          {/* YouTube URL Input */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              className="form-input flex-1"
              placeholder="https://youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setYoutubeUrl(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={handlePaste} title={t('dubbing.btn.paste_title')}>
              <ClipboardIcon />
              <span>{t('dubbing.btn.paste')}</span>
            </button>
          </div>

          {/* Configuration */}
          <div className="card mb-6">
            <div className="card-header">
              <h3 className="card-title">{t('dubbing.config')}</h3>
            </div>

            {/* Row 1 */}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">{t('dubbing.target_lang')}</label>
                <select
                  className="form-select"
                  value={config.targetLanguage}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('targetLanguage', e.target.value)}
                >
                  {LANGUAGE_OPTIONS.map(code => (
                    <option key={code} value={code}>{t(LANG_T_KEY[code] as any)}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">{t('dubbing.voice_model')}</label>
                <select
                  className="form-select"
                  value={config.voiceModel}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('voiceModel', e.target.value)}
                >
                  {(TTS_MODELS_BY_LANG[config.targetLanguage] || []).map(modelKey => (
                    <option key={modelKey} value={modelKey}>
                      {t(TTS_T_KEY[modelKey] as any) || modelKey}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row 2 */}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">{t('dubbing.translation_engine')}</label>
                <select
                  className="form-select"
                  value={config.translationEngine}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('translationEngine', e.target.value)}
                >
                  <option value="deepseek">{t('dubbing.engine.deepseek')}</option>
                  <option value="gemini">{t('dubbing.engine.gemini')}</option>
                  <option value="deepl">{t('dubbing.engine.deepl')}</option>
                  <option value="ollama">{t('dubbing.engine.ollama')}</option>
                  <option value="google">{t('dubbing.engine.google')}</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">{t('dubbing.translator_model')}</label>
                <select
                  className="form-select"
                  value={config.translatorModel}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('translatorModel', e.target.value)}
                  disabled={config.translationEngine === 'google' || config.translationEngine === 'gemini'}
                >
                  {config.translationEngine === 'ollama' ? (
                    ollamaModels.length > 0 ? (
                      ollamaModels.map(m => <option key={m} value={m}>{m}</option>)
                    ) : (
                      <option value="">{t('dubbing.no_models')}</option>
                    )
                  ) : config.translationEngine === 'deepseek' ? (
                    <>
                      <option value="deepseek-chat">deepseek-chat</option>
                      <option value="deepseek-reasoner">deepseek-reasoner</option>
                    </>
                  ) : config.translationEngine === 'deepl' ? (
                    <option value="deepl-api">{t('dubbing.translator.deepl_api')}</option>
                  ) : (
                    <option value="default">{t('dubbing.translator.default')}</option>
                  )}
                </select>
              </div>
            </div>
          </div>

          {/* Pipeline Mode */}
          <div className="card mb-6">
            <div className="card-header">
              <label className="form-label">{t('dubbing.mode')}</label>
            </div>
            <div className="flex-col gap-3">
              <label className="form-radio">
                <input
                  type="radio"
                  name="pipelineMode"
                  checked={config.pipelineMode === 'automatic'}
                  onChange={() => updateConfig('pipelineMode', 'automatic')}
                />
                <div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{t('dubbing.mode.auto_label')}</div>
                  <div className="text-sm text-muted">{t('dubbing.mode.auto_desc')}</div>
                </div>
              </label>
              <label className="form-radio">
                <input
                  type="radio"
                  name="pipelineMode"
                  checked={config.pipelineMode === 'manual'}
                  onChange={() => updateConfig('pipelineMode', 'manual')}
                />
                <div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{t('dubbing.mode.manual_label')}</div>
                  <div className="text-sm text-muted">{t('dubbing.mode.manual_desc')}</div>
                </div>
              </label>
            </div>
          </div>

          {/* Advanced Options */}
          <div className="card mb-6">
            <div
              className="flex items-center justify-between"
              style={{ cursor: 'pointer' }}
              onClick={() => setShowAdvanced(v => !v)}
            >
              <h3 className="card-title">{t('dubbing.advanced')}</h3>
              <ChevronIcon open={showAdvanced} />
            </div>
            {showAdvanced && (
              <div className="mt-4">
                {renderSwitch(t('dubbing.adv.mux'), config.autoMux, v => updateConfig('autoMux', v), t('dubbing.adv.mux_desc'))}
                {renderSwitch(t('dubbing.adv.clone'), config.voiceCloning, v => updateConfig('voiceCloning', v), t('dubbing.adv.clone_desc'))}
                {renderSwitch(t('dubbing.adv.demucs'), config.audioSeparation, v => updateConfig('audioSeparation', v), t('dubbing.adv.demucs_desc'))}
              </div>
            )}
          </div>

          {/* Start Button */}
          <button
            className="btn btn-primary btn-lg btn-full"
            onClick={handleStartPipeline}
            disabled={!fileName && !youtubeUrl}
            style={{ opacity: (!fileName && !youtubeUrl) ? 0.5 : 1 }}
          >
            <PlayIcon />
            {t('dubbing.start')}
          </button>
        </>
      )}

      {/* ─── Running / Done: Pipeline Progress ─── */}
      {(pipelineState === 'running' || pipelineState === 'done') && (
        <>
          {/* Pipeline Steps */}
          <div className="pipeline-steps" style={{ flexWrap: 'wrap' }}>
            {PIPELINE_STEP_KEYS.map((key, idx) => {
              const num = idx + 1;
              return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                <div className={`pipeline-step ${getStepState(num)}`}>
                  {getStepState(num) === 'done' ? (
                    <CheckIcon />
                  ) : (
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, opacity: 0.7 }}>{num}</span>
                  )}
                  {t(STEP_T_KEY[key] as any)}
                </div>
                {idx < PIPELINE_STEP_KEYS.length - 1 && (
                  <div className={`pipeline-connector ${getConnectorState(num)}`} />
                )}
              </div>
            )})}
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {pipelineState === 'done' ? t('dubbing.status.done') : t('dubbing.status.processing')} {activeStep} / {PIPELINE_STEP_KEYS.length}…
              </span>
              <span className="text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {progress}%
              </span>
            </div>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Status Badge */}
          <div className="mb-6 flex items-center gap-3">
            {pipelineState === 'running' && (
              <>
                <span className="badge badge-info">
                  <SpinnerIcon />
                  {t('dubbing.badge.running')}
                </span>
                <button
                  className="btn btn-danger btn-lg"
                  onClick={() => {
                    stopPipeline();
                    notifyToast.info(t('toast.pipeline_stopping'), { description: t('toast.pipeline_cancel') });
                  }}
                  style={{ marginLeft: 'auto' }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: 6 }}>
                    <rect x="6" y="6" width="12" height="12" rx="1" />
                  </svg>
                  {t('dubbing.btn.cancel')}
                </button>
              </>
            )}
            {pipelineState === 'done' && (
              <span className="badge badge-success">
                <CheckIcon />
                {t('dubbing.badge.done')}
              </span>
            )}
          </div>

          {/* Log Viewer */}
          <div className="card mb-6">
            <div className="card-header">
              <h3 className="card-title">{t('dubbing.log.title')}</h3>
              <span className="badge badge-neutral">{logs.length} {t('dubbing.log.entries')}</span>
            </div>
            <div className="log-viewer" role="log" aria-live="polite">
              {logs.length > 0 ? (
                <VirtualLogViewer logs={logs} maxHeight={200} />
              ) : (
              <div className="log-entry">
                <span className="log-time">[{new Date().toLocaleTimeString()}]</span>
                <span className="log-text log-info">{t('dubbing.status.waiting_backend')}</span>
              </div>
            )}
            </div>
          </div>

          {/* Done actions */}
          {pipelineState === 'done' && (
            <div className="flex gap-3">
              <button className="btn btn-primary btn-lg" style={{ flex: 1 }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                {t('dubbing.btn.open')}
              </button>
              <button className="btn btn-secondary btn-lg" onClick={handleReset}>
                {t('dubbing.btn.new')}
              </button>
            </div>
          )}
        </>
      )}

      {/* ─── Review Mode: SRT Editor ─── */}
      {pipelineState === 'review' && (
        <>
          {/* Pipeline steps (frozen at step 4) */}
          <div className="pipeline-steps" style={{ flexWrap: 'wrap' }}>
            {PIPELINE_STEP_KEYS.map((key, idx) => {
              const num = idx + 1;
              return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                <div className={`pipeline-step ${getStepState(num)}`}>
                  {getStepState(num) === 'done' ? (
                    <CheckIcon />
                  ) : (
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, opacity: 0.7 }}>{num}</span>
                  )}
                  {t(STEP_T_KEY[key] as any)}
                </div>
                {idx < PIPELINE_STEP_KEYS.length - 1 && (
                  <div className={`pipeline-connector ${getConnectorState(num)}`} />
                )}
              </div>
            )})}
          </div>

          <div className="callout callout-warning mb-6">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <div>
              <strong>{t('dubbing.review.title')}</strong> — {t('dubbing.review.desc')}
            </div>
          </div>

          {/* Split Editor */}
          <div className="editor-split mb-6">
            {/* Left: Original */}
            <div className="editor-panel">
              <div className="editor-panel-header">
                <span>{t('dubbing.review.original')}</span>
                <span className="badge badge-neutral">{t('dubbing.review.readonly')}</span>
              </div>
              <div className="editor-content">
                {originalSegments.length > 0
                  ? originalSegments.map((seg, i) => <div key={i}>{seg}</div>)
                  : <span style={{ color: 'var(--text-muted)' }}>{t('dubbing.status.waiting_backend')}</span>}
              </div>
            </div>

            {/* Right: Translated (editable) */}
            <div className="editor-panel">
              <div className="editor-panel-header">
                <span>{t('dubbing.review.translated')}</span>
                <span className="badge badge-info">{t('dubbing.review.editable')}</span>
              </div>
              <textarea
                className="editor-content"
                value={translatedSrt}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setTranslatedSrt(e.target.value)}
              />
            </div>
          </div>

          {/* Continue Button */}
          <div className="flex gap-3">
            <button className="btn btn-primary btn-lg btn-full" onClick={handleContinueFromReview}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              {t('dubbing.btn.continue')}
            </button>
            <button className="btn btn-secondary btn-lg" onClick={handleReset}>
              {t('dubbing.btn.cancel')}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
