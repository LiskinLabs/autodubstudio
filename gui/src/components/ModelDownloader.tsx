import { useState, useEffect, useCallback, useRef } from 'react';

interface ModelInfo {
  id: string;
  name: string;
  size: string;
  url: string;
  description: string;
}

const MODELS: ModelInfo[] = [
  {
    id: 'whisper-large-v3',
    name: 'Whisper large-v3',
    size: '3.1 GB',
    url: 'https://huggingface.co/openai/whisper-large-v3/resolve/main/model.bin',
    description: 'Распознавание речи — лучшая точность (рекомендуется)',
  },
  {
    id: 'whisper-base',
    name: 'Whisper base',
    size: '290 MB',
    url: 'https://huggingface.co/openai/whisper-base/resolve/main/model.bin',
    description: 'Распознавание речи — быстро, ниже точность',
  },
  {
    id: 'pyannote-segmentation',
    name: 'Pyannote Segmentation 3.0',
    size: '180 MB',
    url: 'https://huggingface.co/pyannote/segmentation-3.0/resolve/main/pytorch_model.bin',
    description: 'Диаризация — определяет кто говорит',
  },
  {
    id: 'xttsv2',
    name: 'XTTSv2',
    size: '1.9 GB',
    url: 'https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth',
    description: 'Синтез речи — турецкий, русский, английский',
  },
];

type DlState = 'idle' | 'downloading' | 'done' | 'error';

export default function ModelDownloader() {
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [downloads, setDownloads] = useState<Record<string, { state: DlState; progress: number; error?: string }>>({});
  const abortRef = useRef<Record<string, AbortController>>({});

  // Check if first launch
  useEffect(() => {
    const hasRun = localStorage.getItem('autodub_first_launch');
    if (!hasRun) {
      // First launch — auto-open model downloader
      setIsOpen(true);
      // Pre-select recommended models
      setSelected(new Set(['whisper-large-v3', 'pyannote-segmentation']));
    }

    // Initialize download states
    const state: Record<string, { state: DlState; progress: number }> = {};
    for (const m of MODELS) {
      const done = localStorage.getItem(`model_${m.id}`) === 'done';
      state[m.id] = { state: done ? 'done' : 'idle', progress: done ? 100 : 0 };
    }
    setDownloads(state);
  }, []);

  const toggleModel = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const downloadSelected = useCallback(async () => {
    localStorage.setItem('autodub_first_launch', 'done');
    const toDownload = MODELS.filter(m => selected.has(m.id) && downloads[m.id]?.state !== 'done');

    for (const model of toDownload) {
      setDownloads(prev => ({ ...prev, [model.id]: { state: 'downloading', progress: 0 } }));
      const controller = new AbortController();
      abortRef.current[model.id] = controller;

      try {
        const resp = await fetch(model.url, { signal: controller.signal });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        if (!resp.body) throw new Error('No body');

        const total = Number(resp.headers.get('content-length')) || 0;
        const reader = resp.body.getReader();
        let received = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          received += value.length;
          if (total > 0) {
            setDownloads(prev => ({
              ...prev,
              [model.id]: { state: 'downloading', progress: Math.round((received / total) * 100) },
            }));
          }
        }

        localStorage.setItem(`model_${model.id}`, 'done');
        setDownloads(prev => ({ ...prev, [model.id]: { state: 'done', progress: 100 } }));
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        setDownloads(prev => ({ ...prev, [model.id]: { state: 'error', progress: 0, error: err.message } }));
      }
    }
  }, [selected, downloads]);

  const skipAll = useCallback(() => {
    localStorage.setItem('autodub_first_launch', 'done');
    setIsOpen(false);
  }, []);

  // Compact status bar indicator when not open
  if (!isOpen) {
    const downloading = Object.values(downloads).filter(d => d.state === 'downloading').length;
    if (downloading > 0) {
      return (
        <div className="status-item" style={{ color: 'var(--accent)', cursor: 'pointer' }} onClick={() => setIsOpen(true)}>
          <span>⬇️ {downloading} model(s)</span>
        </div>
      );
    }
    return null;
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.7)',
      }}
    >
      <div
        style={{
          width: 600, maxHeight: '85vh', overflow: 'auto',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          padding: 'var(--space-8)',
        }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <div style={{ fontSize: '48px', marginBottom: 'var(--space-3)' }}>🤖</div>
          <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Добро пожаловать в AutoDub Studio!
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginTop: 'var(--space-2)', lineHeight: 1.6 }}>
            Чтобы начать работу, установите AI модели. Они скачиваются один раз и кэшируются локально.
            Вы можете пропустить этот шаг и установить модели позже в Настройках.
          </p>
        </div>

        {/* Model list */}
        <div className="flex-col gap-3" style={{ display: 'flex', marginBottom: 'var(--space-6)' }}>
          {MODELS.map(model => {
            const dl = downloads[model.id];
            const isDone = dl?.state === 'done';
            const isDownloading = dl?.state === 'downloading';
            const isChecked = selected.has(model.id) || isDone;

            return (
              <label
                key={model.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
                  padding: 'var(--space-4)',
                  background: isDone ? 'var(--success-muted)' : 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-md)',
                  border: `1px solid ${isChecked ? 'var(--accent)' : 'var(--border-subtle)'}`,
                  cursor: isDone ? 'default' : 'pointer',
                  opacity: isDownloading ? 0.7 : 1,
                  transition: 'all 120ms ease',
                }}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  disabled={isDone || isDownloading}
                  onChange={() => !isDone && toggleModel(model.id)}
                  style={{ accentColor: 'var(--accent)', width: 18, height: 18, cursor: 'pointer', flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {model.name}
                    <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginLeft: 8 }}>
                      {model.size}
                    </span>
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 2 }}>
                    {model.description}
                  </div>

                  {isDownloading && (
                    <div className="progress-bar" style={{ marginTop: 'var(--space-2)' }}>
                      <div className="progress-bar-fill" style={{ width: `${dl.progress}%` }} />
                    </div>
                  )}
                  {dl?.state === 'error' && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--error)', marginTop: 4 }}>{dl.error}</div>
                  )}
                </div>

                {isDone && <span className="badge badge-success">✓</span>}
                {isDownloading && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 600 }}>{dl.progress}%</span>}
              </label>
            );
          })}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            className="btn btn-primary btn-lg"
            style={{ flex: 1 }}
            onClick={downloadSelected}
            disabled={selected.size === 0 || Object.values(downloads).some(d => d.state === 'downloading')}
          >
            ⬇️ Установить выбранные ({selected.size})
          </button>
          <button className="btn btn-secondary btn-lg" onClick={skipAll}>
            Пропустить
          </button>
        </div>

        <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textAlign: 'center' }}>
          Модели можно установить позже: Настройки → Model Status → Download
        </div>
      </div>
    </div>
  );
}
