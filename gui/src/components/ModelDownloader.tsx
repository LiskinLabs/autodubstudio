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
        <div className="flex items-center gap-1.5 h-full px-2 hover:bg-base-content/5 transition-colors cursor-pointer text-primary" onClick={() => setIsOpen(true)}>
          <span>⬇️ {downloading} model(s)</span>
        </div>
      );
    }
    return null;
  }

  // Count only models that are selected AND not already installed
  const pendingDownloadCount = MODELS.filter(m => selected.has(m.id) && !modelStatus[m.id]?.done).length;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 p-4">
      <div className="w-[600px] max-h-[85vh] overflow-y-auto bg-base-100 border border-base-content/10 rounded-2xl shadow-2xl p-8">
        <div className="text-center mb-6">
          <img src="/logo-icon.png" alt="AutoDub Studio" className="w-20 h-20 mb-4 object-contain mx-auto" />
          <h2 className="text-2xl font-bold m-0 text-base-content">{t('dl.title')}</h2>
          <p className="text-sm text-base-content/70 mt-2 leading-relaxed max-w-sm mx-auto">
            {t('dl.desc')}
          </p>
        </div>

        <div className="flex flex-col gap-3 mb-6">
          {MODELS.map(model => {
            const st = modelStatus[model.id];
            const isDone = st?.done;
            const isDownloading = !isDone && (st?.progress === -1 || (st?.progress !== undefined && st?.progress > 0));
            const hasRealProgress = st?.progress >= 5;
            const isChecked = selected.has(model.id) || isDone;

            return (
              <label key={model.id} className={`flex items-center gap-4 p-4 rounded-lg border transition-all duration-120 ${isDone ? 'bg-success/10 border-success/20 cursor-default' : 'bg-base-200 cursor-pointer'} ${isChecked && !isDone ? 'border-primary' : ''} ${!isDone && !isChecked ? 'border-base-content/10 hover:border-base-content/20' : ''} ${isDownloading ? 'opacity-70' : 'opacity-100'}`}>
                <input type="checkbox" checked={isChecked} disabled={isDone || isDownloading} onChange={() => !isDone && toggleModel(model.id)} className="checkbox checkbox-primary w-5 h-5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-base-content">
                    {model.name}
                    <span className="font-normal text-base-content/50 text-xs ml-2">{model.size}</span>
                  </div>
                  <div className="text-xs text-base-content/70 mt-0.5">{t(model.descKey as any)}</div>
                  <div className="text-xs text-primary mt-0.5">{t(model.descDetailKey as any)}</div>
                  {isDownloading && hasRealProgress && (
                    <progress className="progress progress-primary w-full h-1.5 mt-2" value={st.progress} max="100"></progress>
                  )}
                  {isDownloading && !hasRealProgress && (
                    <div className="text-xs text-primary mt-1 font-medium">
                      {t('dl.downloading')}
                    </div>
                  )}
                  {st?.error && <div className="text-xs text-error mt-1">{st.error}</div>}
                </div>
                {isDone && <span className="badge badge-success badge-sm">✓</span>}
                {isDownloading && hasRealProgress && (
                  <span className="text-xs text-primary font-semibold">{st.progress}%</span>
                )}
              </label>
            );
          })}
        </div>

        <div className="flex gap-3 mt-4">
          <button className="btn btn-primary flex-1" onClick={downloadSelected} disabled={pendingDownloadCount === 0}>
            {t('dl.btn_download')} ({pendingDownloadCount})
          </button>
          <button className="btn btn-neutral" onClick={skipAll}>{t('dl.btn_skip')}</button>
        </div>
        <div className="mt-4 text-xs text-base-content/50 text-center">
          {t('dl.note')}
        </div>
      </div>
    </div>
  );
}
