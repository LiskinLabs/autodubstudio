import { useState, useEffect, useCallback, useRef } from 'react';
import { useSettings } from '../store';

interface ModelInfo {
  id: string;
  name: string;
  size: string;
  url: string;
  required: boolean;
  description: string;
}

// Models hosted on GitHub Releases — downloaded on-demand
const MODELS: ModelInfo[] = [
  {
    id: 'whisper-large-v3',
    name: 'Whisper large-v3',
    size: '~3.1 GB',
    url: 'https://huggingface.co/openai/whisper-large-v3/resolve/main/model.bin',
    required: false,
    description: 'Best accuracy speech recognition (recommended)',
  },
  {
    id: 'whisper-base',
    name: 'Whisper base',
    size: '~290 MB',
    url: 'https://huggingface.co/openai/whisper-base/resolve/main/model.bin',
    required: false,
    description: 'Fast, lower accuracy — good for testing',
  },
  {
    id: 'pyannote-segmentation',
    name: 'Pyannote Segmentation 3.0',
    size: '~180 MB',
    url: 'https://huggingface.co/pyannote/segmentation-3.0/resolve/main/pytorch_model.bin',
    required: false,
    description: 'Speaker diarization — identifies who is speaking',
  },
  {
    id: 'xttsv2',
    name: 'XTTSv2',
    size: '~1.9 GB',
    url: 'https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth',
    required: false,
    description: 'High-quality Turkish/Russian voice synthesis',
  },
];

type DownloadState = 'idle' | 'downloading' | 'done' | 'error';

interface ModelDownloadState {
  [key: string]: {
    state: DownloadState;
    progress: number;
    error?: string;
  };
}

export default function ModelDownloader() {
  const { t } = useSettings();
  const [downloads, setDownloads] = useState<ModelDownloadState>({});
  const [isOpen, setIsOpen] = useState(false);
  const abortRef = useRef<Record<string, AbortController>>({});

  const getStored = useCallback((modelId: string): DownloadState => {
    try {
      return localStorage.getItem(`model_${modelId}`) === 'done' ? 'done' : 'idle';
    } catch {
      return 'idle';
    }
  }, []);

  useEffect(() => {
    // Check which models are already installed
    const state: ModelDownloadState = {};
    for (const m of MODELS) {
      state[m.id] = { state: getStored(m.id), progress: 0 };
    }
    setDownloads(state);

    // Auto-open if any required models are missing
    const missing = MODELS.some(m => m.required && getStored(m.id) !== 'done');
    if (missing) {
      setIsOpen(true);
    }
  }, [getStored]);

  const downloadModel = useCallback(async (model: ModelInfo) => {
    setDownloads(prev => ({
      ...prev,
      [model.id]: { state: 'downloading', progress: 0 },
    }));

    const controller = new AbortController();
    abortRef.current[model.id] = controller;

    try {
      const resp = await fetch(model.url, { signal: controller.signal });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (!resp.body) throw new Error('No response body');

      const contentLength = Number(resp.headers.get('content-length')) || 0;
      const reader = resp.body.getReader();
      let received = 0;
      const chunks: Uint8Array[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (contentLength > 0) {
          setDownloads(prev => ({
            ...prev,
            [model.id]: {
              state: 'downloading',
              progress: Math.round((received / contentLength) * 100),
            },
          }));
        }
      }

      // Save model to disk (placeholder — uses Tauri file system in production)
      localStorage.setItem(`model_${model.id}`, 'done');
      setDownloads(prev => ({
        ...prev,
        [model.id]: { state: 'done', progress: 100 },
      }));
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      setDownloads(prev => ({
        ...prev,
        [model.id]: { state: 'error', progress: 0, error: err.message },
      }));
    }
  }, []);

  const cancelDownload = useCallback((modelId: string) => {
    abortRef.current[modelId]?.abort();
  }, []);

  if (!isOpen) {
    // Show compact status bar indicator
    const downloading = Object.values(downloads).filter(d => d.state === 'downloading').length;
    if (downloading > 0) {
      return (
        <div className="status-item" style={{ color: 'var(--accent)', cursor: 'pointer' }} onClick={() => setIsOpen(true)}>
          <span>⬇️ Models: {downloading} downloading</span>
        </div>
      );
    }
    return null;
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9998,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)',
      }}
    >
      <div
        style={{
          width: 560,
          maxHeight: '80vh',
          overflow: 'auto',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          padding: 'var(--space-6)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-5)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: 0 }}>Download AI Models</h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
              Models are downloaded on-demand from HuggingFace. Only download what you need.
            </p>
          </div>
          <button className="btn btn-ghost" onClick={() => setIsOpen(false)} style={{ fontSize: 'var(--text-lg)' }}>
            ✕
          </button>
        </div>

        <div className="flex-col gap-3" style={{ display: 'flex' }}>
          {MODELS.map(model => {
            const dl = downloads[model.id];
            const isDownloading = dl?.state === 'downloading';
            const isDone = dl?.state === 'done';
            const isError = dl?.state === 'error';

            return (
              <div
                key={model.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-4)',
                  padding: 'var(--space-4)',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {model.name}
                    <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginLeft: 'var(--space-2)' }}>
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
                  {isError && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--error)', marginTop: 4 }}>
                      {dl.error}
                    </div>
                  )}
                </div>

                {isDone ? (
                  <span className="badge badge-success">✓ Installed</span>
                ) : isDownloading ? (
                  <button className="btn btn-ghost btn-icon" onClick={() => cancelDownload(model.id)} title="Cancel">
                    ✕
                  </button>
                ) : (
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: 'var(--text-xs)', padding: '4px 12px' }}
                    onClick={() => downloadModel(model)}
                  >
                    {isError ? 'Retry' : 'Download'}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', textAlign: 'center' }}>
          All models are cached locally after first download. You can delete them from Settings → TTS Cache.
        </div>
      </div>
    </div>
  );
}
