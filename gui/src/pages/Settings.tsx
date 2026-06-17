import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useSettings, Language } from '../store';
import { open } from '@tauri-apps/plugin-dialog';
import { fetch } from '@tauri-apps/plugin-http';
import { notifyToast } from '../lib/toast';
import { useModelStatus, ALL_MODELS } from '../hooks/useModelStatus';

type SettingsTab = 'general' | 'models' | 'keys' | 'about';

interface ModelSettings {
  whisperModel: string;
  ollamaUrl: string;
  ttsCacheDir: string;
}

interface ApiKeys {
  deepseek: string;
  openai: string;
  azure: string;
  google: string;
  gemini: string;
  huggingface: string;
  deepl: string;
}

function Settings() {
  const { lang, theme, setLanguage, setTheme, t } = useSettings();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const [general, setGeneral] = useState({
    gpuMemory: 'auto',
    autoUpdate: true,
  });

  // Apply theme and language dynamically
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.lang = lang;
  }, [theme, lang]);

  const [models, setModels] = useState<ModelSettings>({
    whisperModel: 'large-v3',
    ollamaUrl: 'http://localhost:11434',
    ttsCacheDir: '',
  });

  const [keys, setKeys] = useState<ApiKeys>(() => {
    // Default empty — the Tauri Store will load & migrate data in store.ts
    return {
      deepseek: '',
      openai: '',
      azure: '',
      google: '',
      gemini: '',
      huggingface: '',
      deepl: '',
    };
  });

  const { setApiKeys, apiKeys: storedKeys } = useSettings();
  const { modelStatus, isLoading, startDownload, cancelDownload, deleteModel } = useModelStatus(keys.huggingface);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());

  type KeyStatus = 'idle' | 'testing' | 'success' | 'error';
  const [keyStatus, setKeyStatus] = useState<Record<string, KeyStatus>>({});
  const [_showKeys, _setShowKeys] = useState<Record<string, boolean>>({});

  // Sync keys from Tauri Store when it finishes loading
  useEffect(() => {
    const nonEmpty = Object.entries(storedKeys).filter(([_, v]) => v).length > 0;
    if (nonEmpty) {
      setKeys(prev => ({ ...prev, ...storedKeys }));
    }
  }, [storedKeys]); // Re-sync whenever the store updates

  // Debounced save: persist to store 500ms after last keystroke
  const debouncedSave = useCallback((newKeys: ApiKeys) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      setApiKeys(newKeys as unknown as Record<string, string>);
    }, 500);
  }, [setApiKeys]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, []);

  // Replace immediate save with debounced
  const updateKey = (id: keyof ApiKeys, value: string) => {
    setKeys(prev => {
      const next = { ...prev, [id]: value };
      debouncedSave(next);
      return next;
    });
  };

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'general', label: t('settings.general') },
    { id: 'models', label: t('settings.models') },
    { id: 'keys', label: t('settings.keys') },
    { id: 'about', label: t('settings.about') },
  ];

  const renderStatus = (id: string) => {
    const status = keyStatus[id];
    if (status === 'testing') return <span className="status-dot yellow" title={t("settings.keys.testing")} style={{ marginLeft: 8 }} />;
    if (status === 'success') return <span style={{ marginLeft: 8, color: 'var(--success)' }}>✅</span>;
    if (status === 'error') return <span style={{ marginLeft: 8, color: 'var(--error)' }}>❌</span>;
    return null;
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    setKeyStatus({});
    let successCount = 0;
    let failCount = 0;
    let errors: string[] = [];

    const testApi = async (id: keyof ApiKeys, name: string, url: string, options: RequestInit) => {
      setKeyStatus(prev => ({ ...prev, [id]: 'testing' }));
      try {
        const res = await fetch(url, options);
        if (res.ok) {
          successCount++;
          setKeyStatus(prev => ({ ...prev, [id]: 'success' }));
        } else {
          failCount++;
          let detail = `HTTP ${res.status}`;
          try {
            const body = await res.text();
            const snippet = body.slice(0, 120);
            if (snippet) detail += ` — ${snippet}`;
          } catch {}
          errors.push(`${name}: ${detail}`);
          setKeyStatus(prev => ({ ...prev, [id]: 'error' }));
        }
      } catch (err: any) {
        failCount++;
        errors.push(`${name}: ${err?.message || err?.toString?.() || 'Network Error'}`);
        setKeyStatus(prev => ({ ...prev, [id]: 'error' }));
      }
    };

    const promises = [];

    if (keys.deepl) {
      const isFree = keys.deepl.endsWith(':fx');
      const baseUrl = isFree ? 'https://api-free.deepl.com' : 'https://api.deepl.com';
      promises.push(testApi('deepl', 'DeepL', `${baseUrl}/v2/usage`, {
        headers: { 'Authorization': `DeepL-Auth-Key ${keys.deepl}` }
      }));
    }

    if (keys.deepseek) {
      promises.push(testApi('deepseek', 'DeepSeek', 'https://api.deepseek.com/models', {
        headers: { 'Authorization': `Bearer ${keys.deepseek}` }
      }));
    }
    if (keys.openai) {
      promises.push(testApi('openai', 'OpenAI', 'https://api.openai.com/v1/models', {
        headers: { 'Authorization': `Bearer ${keys.openai}` }
      }));
    }
    if (keys.huggingface) {
      promises.push(testApi('huggingface', 'HuggingFace', 'https://huggingface.co/api/whoami-v2', {
        headers: { 'Authorization': `Bearer ${keys.huggingface}` }
      }));
    }
    // Note: Gemini and Azure require specific payload structures or endpoints, skipping strict test if not easy, 
    // but Gemini models list is easy:
    if (keys.gemini || keys.google) {
      const gkey = keys.gemini || keys.google;
      const targetId = keys.gemini ? 'gemini' : 'google';
      promises.push(testApi(targetId, 'Google/Gemini', `https://generativelanguage.googleapis.com/v1beta/models?key=${gkey}`, {}));
    }

    if (promises.length === 0) {
      setIsTesting(false);
      setTestResult(t('settings.keys.no_keys'));
      return;
    }

    await Promise.all(promises);
    setIsTesting(false);

    if (failCount === 0) {
      setTestResult(t('settings.keys.all_ok'));
      notifyToast.success(t('settings.keys.all_ok'));
    } else {
      setTestResult(t('settings.keys.failed'));
      notifyToast.error(`${failCount} key(s) failed`, { description: errors.join(', ') });
    }
  };

  const renderGeneral = () => (
    <div className="flex-col gap-4" style={{ display: 'flex' }}>
      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.appearance')}</span>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.language')}</label>
          <select
            className="form-select"
            value={lang}
            onChange={(e) => setLanguage(e.target.value as Language)}
          >
            <option value="en">{t('settings.lang.en_label')}</option>
            <option value="ru">{t('settings.lang.ru_label')}</option>
            <option value="tr">{t('settings.lang.tr_label')}</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.theme')}</label>
          <select
            className="form-select"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
          >
            <option value="dark">{t('settings.theme.dark')}</option>
            <option value="light">{t('settings.theme.light')}</option>
            <option value="system">{t('settings.theme.system')}</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.performance')}</span>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.gpu_limit')}</label>
          <select
            className="form-select"
            value={general.gpuMemory}
            onChange={(e) => setGeneral({ ...general, gpuMemory: e.target.value })}
          >
            <option value="auto">{t('settings.gpu.auto')}</option>
            <option value="4">4 GB</option>
            <option value="6">6 GB</option>
            <option value="8">8 GB</option>
            <option value="12">12 GB</option>
          </select>
          <div className="text-sm text-muted mt-2">
            {t('settings.gpu_desc')}
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <div className="flex items-center justify-between">
            <div>
              <label className="form-label" style={{ marginBottom: 'var(--space-1)' }}>
                {t('settings.auto_update')}
              </label>
              <div className="text-sm text-muted">
                {t('settings.auto_update_desc')}
              </div>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={general.autoUpdate}
                onChange={(e) =>
                  setGeneral({ ...general, autoUpdate: e.target.checked })
                }
              />
              <span className="switch-slider" />
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const renderModels = () => (
    <div className="flex-col gap-4" style={{ display: 'flex' }}>
      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.speech_rec')}</span>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.whisper_model')}</label>
          <select
            className="form-select"
            value={models.whisperModel}
            onChange={(e) =>
              setModels({ ...models, whisperModel: e.target.value })
            }
          >
            <option value="tiny">tiny — {t('settings.whisper.tiny')}</option>
            <option value="base">base — {t('settings.whisper.base')}</option>
            <option value="small">small — {t('settings.whisper.small')}</option>
            <option value="medium">medium — {t('settings.whisper.medium')}</option>
            <option value="large-v3">large-v3 — {t('settings.whisper.large')}</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.ollama_config')}</span>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.ollama_url')}</label>
          <input
            className="form-input"
            type="text"
            value={models.ollamaUrl}
            onChange={(e) => setModels({ ...models, ollamaUrl: e.target.value })}
            placeholder="http://localhost:11434"
          />
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.tts_audio')}</span>
        </div>

        <div className="form-group">
          <label className="form-label">{t('settings.tts_cache')}</label>
          <div className="flex gap-2">
            <input
              className="form-input flex-1"
              type="text"
              value={models.ttsCacheDir}
              onChange={(e) =>
                setModels({ ...models, ttsCacheDir: e.target.value })
              }
              placeholder="C:\Users\...\tts_cache"
            />
            <button
              className="btn btn-secondary"
              style={{ flexShrink: 0 }}
              onClick={async () => {
                try {
                  const selected = await open({ directory: true, multiple: false });
                  if (selected) {
                    setModels({ ...models, ttsCacheDir: selected as string });
                  }
                } catch (e) {
                  console.error(e);
                }
              }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 13h12M6 8l2-2 2 2M8 6v7" />
                <path d="M13 3H3a1 1 0 0 0-1 1v8M14 4v8a1 1 0 0 1-1 1" />
              </svg>
              {t('settings.browse')}
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.model_status')}</span>
        </div>
        <div className="card-description mb-4">
          {t('settings.model_status_desc')}
        </div>

        {/* Bulk actions */}
        <div className="flex items-center gap-3 mb-4">
          <label className="flex items-center gap-2" style={{ cursor: 'pointer', fontSize: 'var(--text-xs)' }}>
            <input type="checkbox" checked={ALL_MODELS.length > 0 && ALL_MODELS.every(m => selectedModels.has(m.id))} onChange={(e) => { if (e.target.checked) { setSelectedModels(new Set(ALL_MODELS.map(m => m.id))); } else { setSelectedModels(new Set()); } }} />
            {t('dl.select_all')}
          </label>
          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>{selectedModels.size} / {ALL_MODELS.length}</span>
          <button className="btn btn-sm btn-primary" disabled={isLoading || selectedModels.size === 0} onClick={() => { selectedModels.forEach(id => { if (!modelStatus[id]?.done) startDownload(id); }); }}>
            ⬇ {t('dl.btn_download')} ({selectedModels.size})
          </button>
          <button className="btn btn-sm btn-danger" disabled={isLoading || selectedModels.size === 0} onClick={() => { selectedModels.forEach(id => { if (modelStatus[id]?.done) deleteModel(id); }); }}>
            🗑 {t('dl.btn_delete')}
          </button>
        </div>

        <div className="flex-col gap-2" style={{ display: 'flex' }}>
          {ALL_MODELS.map((model, index, arr) => {
            const st = modelStatus[model.id];
            const isDone = st?.done;
            const isDeleting = st?.progress === -2;
            const isDownloading = !isDone && !isDeleting && (st?.progress === -1 || (st?.progress !== undefined && st?.progress > 0 && st?.progress < 100));
            const hasProgress = (st?.progress ?? 0) >= 5;
            const isChecked = selectedModels.has(model.id);

            return (
              <React.Fragment key={model.id}>
                <div className="flex items-center gap-3" style={{ padding: 'var(--space-2) 0' }}>
                  <input type="checkbox" checked={isChecked} onChange={() => { setSelectedModels(prev => { const next = new Set(prev); if (next.has(model.id)) next.delete(model.id); else next.add(model.id); return next; }); }} style={{ flexShrink: 0, width: 18, height: 18, cursor: 'pointer' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span className="text-sm" style={{ fontWeight: 500 }}>
                      {model.name}
                      <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginLeft: 8 }}>{model.size}</span>
                    </span>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', marginTop: 2 }}>{t(model.descDetailKey as any)}</div>
                    {isDownloading && hasProgress && (
                      <div className="progress-bar" style={{ marginTop: 4, maxWidth: 200 }}>
                        <div className="progress-bar-fill" style={{ width: `${st.progress}%` }} />
                      </div>
                    )}
                    {st?.error && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--error)', marginTop: 2 }}>{st.error}</div>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexShrink: 0 }}>
                    {isDownloading && hasProgress && (
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--font-mono)', minWidth: 36, textAlign: 'right' }}>{st.progress}%</span>
                    )}
                    {isDownloading && !hasProgress && (
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', whiteSpace: 'nowrap' }}>⏳ {t('dl.downloading_short')}</span>
                    )}
                    {isDownloading && (
                      <button className="btn btn-sm" onClick={() => cancelDownload(model.id)} title={t('dubbing.btn.cancel')} style={{ color: 'var(--error)', border: '1px solid var(--error)', background: 'transparent', fontSize: 'var(--text-xs)', padding: '2px 8px', borderRadius: 'var(--radius-md)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                        ✕
                      </button>
                    )}
                    {isDeleting ? (
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--warning)', whiteSpace: 'nowrap' }}>🗑 {t('dl.deleting')}</span>
                    ) : isDone ? (
                      <button className="btn btn-sm" onClick={() => deleteModel(model.id)} title={t('dl.btn_delete')} style={{ color: 'var(--error)', border: '1px solid var(--error)', background: 'transparent', fontSize: 'var(--text-sm)', padding: '4px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
                        🗑 {t('dl.btn_delete')}
                      </button>
                    ) : isDownloading ? (
                      <span className="badge badge-info" style={{ fontSize: 'var(--text-xs)' }}>⏳</span>
                    ) : (
                      <button className="btn btn-sm btn-primary" onClick={() => startDownload(model.id)} disabled={isLoading}>
                        ⬇ {t('dl.btn_download')}
                      </button>
                    )}
                  </div>
                </div>
                {index < arr.length - 1 && (
                  <div style={{ height: 1, background: 'var(--border-subtle)' }} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );

  const renderKeys = () => (
    <div className="flex-col gap-4" style={{ display: 'flex' }}>
      <div className="callout callout-info">
        <span>ℹ️</span>
        <span>
          {t('settings.keys.notice')}
        </span>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.keys.translation_apis')}</span>
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.keys.gemini_label')}
              {renderStatus('gemini')}
            </label>
            <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.gemini_get')}
            </a>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.gemini}
            onChange={(e) => updateKey('gemini', e.target.value)}
            placeholder="AIzaSy..."
          />
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.deepl_key')}
              {renderStatus('deepl')}
            </label>
            <a href="https://www.deepl.com/pro-api" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.deepl_key')} ↗
            </a>
          </div>
          <div className="text-sm text-muted mb-2">
            {t('settings.deepl_desc')}
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.deepl}
            onChange={(e) => updateKey('deepl', e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx"
          />
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.keys.deepseek_label')}
              {renderStatus('deepseek')}
            </label>
            <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.deepseek_get')}
            </a>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.deepseek}
            onChange={(e) => updateKey('deepseek', e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.keys.openai_label')}
              {renderStatus('openai')}
            </label>
            <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.openai_get')}
            </a>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.openai}
            onChange={(e) => updateKey('openai', e.target.value)}
            placeholder="sk-proj-..."
          />
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.keys.speech_apis')}</span>
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.keys.azure_label')}
              {renderStatus('azure')}
            </label>
            <a href="https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/SpeechServices" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.azure_get')}
            </a>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.azure}
            onChange={(e) => updateKey('azure', e.target.value)}
            placeholder={t('settings.keys.azure_placeholder')}
          />
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.keys.google_label')}
              {renderStatus('google')}
            </label>
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.google_get')}
            </a>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.google}
            onChange={(e) => updateKey('google', e.target.value)}
            placeholder="AIzaSy..."
          />
        </div>

        <div className="form-group">
          <div className="flex justify-between items-center mb-2">
            <label className="form-label" style={{ marginBottom: 0 }}>
              {t('settings.hf_key')}
              {renderStatus('huggingface')}
            </label>
            <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer" className="text-sm text-muted" style={{ textDecoration: 'none' }}>
              {t('settings.keys.hf_get')}
            </a>
          </div>
          <div className="text-sm text-muted mb-2">
            {t('settings.hf_desc')}
            <div style={{ marginTop: '4px' }}>
              {t('settings.hf_terms')}:{' '}
              <a href="https://huggingface.co/pyannote/speaker-diarization-3.1" target="_blank" rel="noreferrer" style={{ textDecoration: 'underline' }}>Diarization 3.1</a>
              {' '}&amp;{' '}
              <a href="https://huggingface.co/pyannote/segmentation-3.0" target="_blank" rel="noreferrer" style={{ textDecoration: 'underline' }}>Segmentation 3.0</a>
            </div>
          </div>
          <input
            className="form-input"
            type="password"
            value={keys.huggingface}
            onChange={(e) => updateKey('huggingface', e.target.value)}
            placeholder="hf_..."
          />
        </div>
      </div>

      <div className="flex gap-3 items-center">
        <button
          className="btn btn-primary"
          onClick={handleTestConnection}
          disabled={isTesting}
        >
          {isTesting ? (
            <>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: 'spin 1s linear infinite' }}>
                <path d="M8 1a7 7 0 1 0 7 7" />
              </svg>
              {t('settings.keys.testing')}
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 3L6 10l-3-3" />
              </svg>
              {t('settings.keys.test_all')}
            </>
          )}
        </button>

        {testResult && (
          <span
            className="text-sm"
            style={{ color: testResult.includes('❌') ? 'var(--danger)' : testResult.includes('⚠️') ? 'var(--warning)' : 'var(--success)' }}
          >
            {testResult}
          </span>
        )}
      </div>
    </div>
  );

  const renderAbout = () => (
    <div className="flex-col gap-4" style={{ display: 'flex' }}>
      <div className="card">
        <div className="about-hero">
          <img src="/logo-icon.png" alt="AutoDub Studio" className="about-logo" />
          <div className="about-name">AutoDubStudio</div>
          <div className="about-role">
            {t('settings.about.tagline')}
          </div>

          <div className="flex gap-3 items-center" style={{ justifyContent: 'center' }}>
            <span className="badge badge-info">v0.0.1-beta</span>
            <span className="badge badge-neutral">Build 2026.06.15</span>
            <span className="badge badge-neutral">Tauri v2 + React 19</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.about.author')}</span>
        </div>

        <div className="flex items-center gap-4">
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              background: 'var(--accent-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 'var(--text-xl)',
              flexShrink: 0,
            }}
          >
            <svg width="24" height="24" viewBox="0 0 16 16" fill="var(--accent)" opacity="0.8">
              <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm5 6a5 5 0 0 0-10 0h10z" />
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 'var(--text-lg)' }}>
              Silvestr Liskin
            </div>
            <div className="text-sm text-muted" style={{ marginTop: 2 }}>
              {t('settings.about.role')}
            </div>
            <div className="text-sm text-muted">
              Teknorob Robot ve Otomasyon — Bursa, TR
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="about-partner">
          <div className="about-partner-label">{t('settings.about.partner')}</div>
          <img
            src="/teknorob.png"
            alt="Teknorob Robot ve Otomasyon"
            className="about-partner-logo"
          />
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">{t('settings.about.links')}</span>
        </div>

        <div className="flex-col gap-2" style={{ display: 'flex' }}>
          <a
            href="https://github.com/liskinlabs/autodubstudio"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3"
            style={{
              color: 'var(--text-secondary)',
              textDecoration: 'none',
              fontSize: 'var(--text-sm)',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-md)',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-hover)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            {t('settings.about.github')}
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ marginLeft: 'auto', opacity: 0.5 }}>
              <path d="M5 3h8v8M13 3L3 13" />
            </svg>
          </a>

          <a
            href="https://liskinlabs.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3"
            style={{
              color: 'var(--text-secondary)',
              textDecoration: 'none',
              fontSize: 'var(--text-sm)',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-md)',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-hover)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="8" cy="8" r="6" />
              <path d="M2 8h12M8 2a10 10 0 0 1 3 6 10 10 0 0 1-3 6 10 10 0 0 1-3-6 10 10 0 0 1 3-6z" />
            </svg>
            {t('settings.about.website')}
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ marginLeft: 'auto', opacity: 0.5 }}>
              <path d="M5 3h8v8M13 3L3 13" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('settings.title')}</h1>
        <p className="page-subtitle">
          {t('settings.subtitle')}
        </p>
      </div>

      {/* Tab bar */}
      <div className="settings-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => {
              setActiveTab(tab.id);
              setTestResult(null);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'general' && renderGeneral()}
      {activeTab === 'models' && renderModels()}
      {activeTab === 'keys' && renderKeys()}
      {activeTab === 'about' && renderAbout()}
    </div>
  );
}

export default Settings;
