import { useState, type ChangeEvent } from 'react';

/* ─── Types ─── */
type SubtitleState = 'idle' | 'listening';

interface SubtitleConfig {
  translationEngine: string;
  sourceLanguage: string;
  targetLanguage: string;
  subtitlePosition: string;
  fontSize: string;
}

/* ─── SVG Icons ─── */
function InfoIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

export function AudioWaveIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12h2" />
      <path d="M6 8v8" />
      <path d="M10 4v16" />
      <path d="M14 6v12" />
      <path d="M18 9v6" />
      <path d="M22 12h-2" />
    </svg>
  );
}

function SubtitleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <line x1="6" y1="14" x2="14" y2="14" />
      <line x1="6" y1="18" x2="18" y2="18" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

import { useSettings } from '../store';
import { useLiveWebSocket } from '../hooks/useLiveWebSocket';

/* ─── Component ─── */
export default function LiveSubtitles() {
  const { t } = useSettings();
  const [state, setState] = useState<SubtitleState>('idle');
  const { isConnected, isCapturing, subtitleText, startCapture, stopCapture } = useLiveWebSocket();
  const [config, setConfig] = useState<SubtitleConfig>({
    translationEngine: 'deepseek',
    sourceLanguage: 'auto',
    targetLanguage: 'ru',
    subtitlePosition: 'bottom',
    fontSize: 'medium',
  });

  const updateConfig = <K extends keyof SubtitleConfig>(key: K, value: SubtitleConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleToggle = () => {
    if (state === 'idle') {
      setState('listening');
      startCapture(config);
    } else {
      setState('idle');
      stopCapture();
    }
  };

  return (
    <div className="flex flex-col flex-1 h-full overflow-y-auto">
      <div className="flex flex-col h-full max-w-5xl mx-auto w-full px-4 py-8 md:px-8 pb-24">
        {/* ─── Header ─── */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-base-content mb-2">{t('live.title')}</h1>
        <p className="text-base-content/60">
          {t('live.subtitle')}
        </p>
      </div>

      {/* ─── Info Callout ─── */}
      <div className="alert alert-info shadow-sm border border-info/20 mb-8">
        <InfoIcon />
        <span>{t('live.callout')}</span>
      </div>

      {/* ─── Configuration ─── */}
      <div className="card bg-base-200 shadow-sm border border-base-content/5 mb-8">
        <div className="card-body p-6">
          <div className="flex items-center gap-2 mb-6">
            <SubtitleIcon />
            <h3 className="card-title text-lg m-0">{t('live.config')}</h3>
          </div>

          {/* Row 1: Translation Engine */}
          <div className="form-control w-full mb-4">
            <label className="label">
              <span className="label-text font-medium">{t('live.engine_label')}</span>
            </label>
            <select
              className="select select-bordered w-full"
            value={config.translationEngine}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('translationEngine', e.target.value)}
          >
            <option value="deepseek">{t('live.engine.deepseek')}</option>
            <option value="whisper-local">{t('live.engine.whisper_local')}</option>
          </select>
        </div>

        {/* Row 2: Languages */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="form-control w-full">
            <label className="label">
              <span className="label-text font-medium">{t('live.source_lang')}</span>
            </label>
            <select
              className="select select-bordered w-full"
              value={config.sourceLanguage}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('sourceLanguage', e.target.value)}
            >
              <option value="auto">{t('live.auto')}</option>
              <option value="en">{t('lang.en')}</option>
              <option value="tr">{t('lang.tr')}</option>
              <option value="ar">{t('lang.ar')}</option>
              <option value="ru">{t('lang.ru')}</option>
            </select>
          </div>
          <div className="form-control w-full">
            <label className="label">
              <span className="label-text font-medium">{t('live.target_lang')}</span>
            </label>
            <select
              className="select select-bordered w-full"
              value={config.targetLanguage}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('targetLanguage', e.target.value)}
            >
              <option value="ru">{t('lang.ru')}</option>
              <option value="tr">{t('lang.tr')}</option>
              <option value="en">{t('lang.en')}</option>
            </select>
          </div>
        </div>

        {/* Row 3: Display */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="form-control w-full">
            <label className="label">
              <span className="label-text font-medium">{t('live.position')}</span>
            </label>
            <select
              className="select select-bordered w-full"
              value={config.subtitlePosition}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('subtitlePosition', e.target.value)}
            >
              <option value="bottom">{t('pos.bottom')}</option>
              <option value="top">{t('pos.top')}</option>
              <option value="center">{t('pos.center')}</option>
            </select>
          </div>
          <div className="form-control w-full">
            <label className="label">
              <span className="label-text font-medium">{t('live.fontsize')}</span>
            </label>
            <select
              className="select select-bordered w-full"
              value={config.fontSize}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('fontSize', e.target.value)}
            >
              <option value="small">{t('size.small')}</option>
              <option value="medium">{t('size.medium')}</option>
              <option value="large">{t('size.large')}</option>
            </select>
          </div>
        </div>
        </div>
      </div>

      {/* ─── Audio Status ─── */}
      <div className="card bg-base-200 shadow-sm border border-base-content/5 mb-8">
        <div className="card-body p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="card-title text-lg m-0">{t('live.audio_status')}</h3>
            <div className={`badge font-medium ${isCapturing ? 'badge-success' : isConnected ? 'badge-info' : 'badge-neutral'}`}>
              {isCapturing ? t('live.listening') : isConnected ? t('live.standby') : t('status.ollama_off')}
            </div>
          </div>

          <div className="flex flex-col gap-6">
          {/* Microphone */}
          <div className="flex items-center gap-4">
            <div className={`w-2.5 h-2.5 rounded-full ${isCapturing ? 'bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-warning'}`} />
            <div className="opacity-70"><MicIcon /></div>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-base-content">
                {t('live.status_audio')}
              </span>
              <span className="text-xs text-base-content/60">
                {isCapturing
                  ? t('live.status_audio.active')
                  : t('live.status_audio.idle')
                }
              </span>
            </div>
          </div>

          {/* Translation Engine Status */}
          <div className="flex items-center gap-4">
            <div className={`w-2.5 h-2.5 rounded-full ${isCapturing ? 'bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-info'}`} />
            <div className="opacity-70"><SubtitleIcon /></div>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-base-content">
                {t('live.status_engine')}
              </span>
              <span className="text-xs text-base-content/60">
                {isCapturing
                  ? t('live.status_engine.active')
                  : t('live.status_engine.idle')
                }
              </span>
            </div>
          </div>

          {/* Subtitle Overlay */}
          <div className="flex items-center gap-4">
            <div className={`w-2.5 h-2.5 rounded-full ${isCapturing ? 'bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-warning'}`} />
            <div className="opacity-70">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18" />
                <path d="M9 21V9" />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-base-content">
                {t('live.status_overlay')}
              </span>
              <span className="text-xs text-base-content/60">
                {isCapturing
                  ? t('live.status_overlay.active')
                  : t('live.status_overlay.idle')
                }
              </span>
            </div>
          </div>
        </div>
        </div>
      </div>

      {/* ─── Live Subtitle Preview (when listening) ─── */}
      {isCapturing && (
        <div className="card bg-base-200 shadow-sm border border-success/30 mb-8">
          <div className="card-body p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="card-title text-lg m-0">{t('live.preview')}</h3>
              <div className="flex items-center gap-2 text-success">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-sm font-medium">{t('live.recording')}</span>
              </div>
            </div>
            <div className="bg-base-300 rounded-lg p-6 font-mono text-sm leading-relaxed border border-base-content/10 text-base-content">
              <div className={subtitleText ? '' : 'opacity-50 italic'}>
                {subtitleText || t('live.waiting_audio')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Start / Stop Button ─── */}
      <button
        className={`btn btn-lg w-full ${isCapturing ? 'btn-error' : 'btn-primary'}`}
        onClick={handleToggle}
      >
        {isCapturing ? (
          <>
            <StopIcon />
            {t('live.stop')}
          </>
        ) : (
          <>
            <PlayIcon />
            {t('live.start')}
          </>
        )}
      </button>
      </div>
    </div>
  );
}
