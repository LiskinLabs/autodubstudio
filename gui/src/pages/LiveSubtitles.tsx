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
    <div className="page">
      {/* ─── Header ─── */}
      <div className="page-header">
        <h1 className="page-title">{t('live.title')}</h1>
        <p className="page-subtitle">
          {t('live.subtitle')}
        </p>
      </div>

      {/* ─── Info Callout ─── */}
      <div className="callout callout-info">
        <InfoIcon />
        <div>
          {t('live.callout')}
        </div>
      </div>

      {/* ─── Configuration ─── */}
      <div className="card mb-6">
        <div className="card-header">
          <h3 className="card-title">{t('live.config')}</h3>
          <SubtitleIcon />
        </div>

        {/* Row 1: Translation Engine */}
        <div className="form-group">
          <label className="form-label">{t('live.engine_label')}</label>
          <select
            className="form-select"
            value={config.translationEngine}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('translationEngine', e.target.value)}
          >
            <option value="deepseek">{t('live.engine.deepseek')}</option>
            <option value="whisper-local">{t('live.engine.whisper_local')}</option>
          </select>
        </div>

        {/* Row 2: Languages */}
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">{t('live.source_lang')}</label>
            <select
              className="form-select"
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
          <div className="form-group">
            <label className="form-label">{t('live.target_lang')}</label>
            <select
              className="form-select"
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
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">{t('live.position')}</label>
            <select
              className="form-select"
              value={config.subtitlePosition}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig('subtitlePosition', e.target.value)}
            >
              <option value="bottom">{t('pos.bottom')}</option>
              <option value="top">{t('pos.top')}</option>
              <option value="center">{t('pos.center')}</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">{t('live.fontsize')}</label>
            <select
              className="form-select"
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

      {/* ─── Audio Status ─── */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: 'var(--space-4)' }}>
          <h3 className="card-title">{t('live.audio_status')}</h3>
          <div className={`badge ${isCapturing ? 'badge-success' : isConnected ? 'badge-info' : 'badge-neutral'}`}>
            {isCapturing ? t('live.listening') : isConnected ? t('live.standby') : t('status.ollama_off')}
          </div>
        </div>

        <div className="flex-col gap-3">
          {/* Microphone */}
          <div className="flex items-center gap-3">
            <div className={`status-dot ${isCapturing ? 'green' : 'yellow'}`} />
            <MicIcon />
            <div className="flex-col" style={{ gap: 2 }}>
              <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {t('live.status_audio')}
              </span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                {isCapturing
                  ? t('live.status_audio.active')
                  : t('live.status_audio.idle')
                }
              </span>
            </div>
          </div>

          {/* Translation Engine Status */}
          <div className="flex items-center gap-3">
            <div className={`status-dot ${isCapturing ? 'green' : 'blue'}`} />
            <SubtitleIcon />
            <div className="flex-col" style={{ gap: 2 }}>
              <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {t('live.status_engine')}
              </span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                {isCapturing
                  ? t('live.status_engine.active')
                  : t('live.status_engine.idle')
                }
              </span>
            </div>
          </div>

          {/* Subtitle Overlay */}
          <div className="flex items-center gap-3">
            <div className={`status-dot ${isCapturing ? 'green' : 'yellow'}`} />
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18" />
              <path d="M9 21V9" />
            </svg>
            <div className="flex-col" style={{ gap: 2 }}>
              <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {t('live.status_overlay')}
              </span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                {isCapturing
                  ? t('live.status_overlay.active')
                  : t('live.status_overlay.idle')
                }
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Live Subtitle Preview (when listening) ─── */}
      {isCapturing && (
        <div className="card mb-6" style={{ borderColor: 'rgba(34, 197, 94, 0.2)' }}>
          <div className="card-header">
            <h3 className="card-title">{t('live.preview')}</h3>
            <div className="flex items-center gap-2">
              <div className="status-dot green" />
              <span className="text-sm" style={{ color: 'var(--success)' }}>{t('live.recording')}</span>
            </div>
          </div>
          <div
            className="font-mono"
            style={{
              padding: 'var(--space-4)',
              background: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              fontSize: 'var(--text-sm)',
              lineHeight: 1.8,
              color: 'var(--text-secondary)',
            }}
          >
            <div style={{ color: subtitleText ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              {subtitleText || t('live.waiting_audio')}
            </div>
          </div>
        </div>
      )}

      {/* ─── Start / Stop Button ─── */}
      <button
        className={`btn btn-lg btn-full ${isCapturing ? 'btn-danger' : 'btn-primary'}`}
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
  );
}
