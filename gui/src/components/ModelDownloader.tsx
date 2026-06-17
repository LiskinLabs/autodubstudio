import { useState, useEffect, useCallback, useRef } from 'react';
import { useSettings } from '../store';
import { ALL_MODELS } from '../hooks/useModelStatus';

const MODELS = ALL_MODELS;

const BACKEND = 'http://127.0.0.1:8000';

export default function ModelDownloader() {
  const { t } = useSettings();
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [modelStatus, setModelStatus] = useState<Record<string, { done: boolean; progress: number; error?: string }>>({});
  const intervalRef = useRef<number | null>(null);

  // Check first launch
  useEffect(() => {
    const hasRun = localStorage.getItem('autodub_first_launch_v2');
    if (!hasRun) {
      setIsOpen(true);
      setSelected(new Set(['whisper-large-v3', 'pyannote-segmentation', 'xttsv2', 'gemma4']));
    }
    fetchModelStatus();
  }, []);

  const fetchModelStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/models/status`);
      if (resp.ok) {
        const data = await resp.json();
        const status: Record<string, { done: boolean; progress: number; error?: string }> = {};
        for (const m of MODELS) {
          const ds = data.downloading?.[m.id];
          status[m.id] = {
            done: data.models?.[m.id] || ds?.done || false,
            progress: ds?.progress || (data.models?.[m.id] ? 100 : 0),
            error: ds?.error,
          };
        }
        setModelStatus(status);
        // Remove already-installed models from the download selection
        setSelected(prev => {
          const cleaned = new Set(prev);
          for (const m of MODELS) {
            if (status[m.id]?.done) cleaned.delete(m.id);
          }
          return cleaned;
        });
        return status;
      }
    } catch { /* backend offline */ }
    return {};
  }, []);

  // Poll status while downloading
  useEffect(() => {
    const hasDownloading = Object.values(modelStatus).some(s => !s.done && s.progress > 0 && !s.error);
    if (hasDownloading) {
      intervalRef.current = window.setInterval(fetchModelStatus, 2000);
    } else {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [modelStatus, fetchModelStatus]);

  const toggleModel = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const downloadSelected = useCallback(async () => {
    localStorage.setItem('autodub_first_launch_v2', 'done');
    const toDownload = MODELS.filter(m => selected.has(m.id) && !modelStatus[m.id]?.done);

    for (const model of toDownload) {
      // Show "downloading" state - backend will update real status via polling
      setModelStatus(prev => ({ ...prev, [model.id]: { done: false, progress: -1 } }));
      try {
        await fetch(`${BACKEND}/api/models/preload/${model.id}`, { method: 'POST' });
      } catch { /* backend will handle */ }
    }
    // Start polling
    fetchModelStatus();
    setIsOpen(false);
  }, [selected, modelStatus, fetchModelStatus]);

  const skipAll = useCallback(() => {
    localStorage.setItem('autodub_first_launch_v2', 'done');
    setIsOpen(false);
  }, []);

  // Compact indicator
  if (!isOpen) {
    const downloading = Object.values(modelStatus).filter(s => !s.done && s.progress > 0).length;
    if (downloading > 0) {
      return (
        <div className="status-item" style={{ color: 'var(--accent)', cursor: 'pointer' }} onClick={() => setIsOpen(true)}>
          <span>⬇️ {downloading} model(s)</span>
        </div>
      );
    }
    return null;
  }

  // Count only models that are selected AND not already installed
  const pendingDownloadCount = MODELS.filter(m => selected.has(m.id) && !modelStatus[m.id]?.done).length;

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)' }}>
      <div style={{ width: 600, maxHeight: '85vh', overflow: 'auto', background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-lg)', padding: 'var(--space-8)' }}>
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <img src="/logo-icon.png" alt="AutoDub Studio" style={{ width: 80, height: 80, marginBottom: 'var(--space-4)', objectFit: 'contain' }} />
          <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: 0 }}>{t('dl.title')}</h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginTop: 'var(--space-2)', lineHeight: 1.6 }}>
            {t('dl.desc')}
          </p>
        </div>

        <div className="flex-col gap-3" style={{ display: 'flex', marginBottom: 'var(--space-6)' }}>
          {MODELS.map(model => {
            const st = modelStatus[model.id];
            const isDone = st?.done;
            const isDownloading = !isDone && (st?.progress === -1 || (st?.progress !== undefined && st?.progress > 0));
            const hasRealProgress = st?.progress >= 5;
            const isChecked = selected.has(model.id) || isDone;

            return (
              <label key={model.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', padding: 'var(--space-4)', background: isDone ? 'var(--success-muted)' : 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: `1px solid ${isChecked ? 'var(--accent)' : 'var(--border-subtle)'}`, cursor: isDone ? 'default' : 'pointer', opacity: isDownloading ? 0.7 : 1, transition: 'all 120ms ease' }}>
                <input type="checkbox" checked={isChecked} disabled={isDone || isDownloading} onChange={() => !isDone && toggleModel(model.id)} style={{ accentColor: 'var(--accent)', width: 18, height: 18, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                    {model.name}
                    <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginLeft: 8 }}>{model.size}</span>
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 2 }}>{t(model.descKey as any)}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', marginTop: 1 }}>{t(model.descDetailKey as any)}</div>
                  {isDownloading && hasRealProgress && (
                    <div className="progress-bar" style={{ marginTop: 'var(--space-2)' }}>
                      <div className="progress-bar-fill" style={{ width: `${st.progress}%` }} />
                    </div>
                  )}
                  {isDownloading && !hasRealProgress && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', marginTop: 4 }}>
                      {t('dl.downloading')}
                    </div>
                  )}
                  {st?.error && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--error)', marginTop: 4 }}>{st.error}</div>}
                </div>
                {isDone && <span className="badge badge-success">✓</span>}
                {isDownloading && hasRealProgress && (
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 600 }}>{st.progress}%</span>
                )}
              </label>
            );
          })}
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button className="btn btn-primary btn-lg" style={{ flex: 1 }} onClick={downloadSelected} disabled={pendingDownloadCount === 0}>
            {t('dl.btn_download')} ({pendingDownloadCount})
          </button>
          <button className="btn btn-secondary btn-lg" onClick={skipAll}>{t('dl.btn_skip')}</button>
        </div>
        <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textAlign: 'center' }}>
          {t('dl.note')}
        </div>
      </div>
    </div>
  );
}
