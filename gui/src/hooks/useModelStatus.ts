import { useState, useEffect, useCallback, useRef } from 'react';

export interface ModelInfo {
  id: string;
  name: string;
  size: string;
  descKey: string;
  descDetailKey: string;
}

export interface ModelStatus {
  done: boolean;
  progress: number;
  error?: string;
}

export const ALL_MODELS: ModelInfo[] = [
  { id: 'htdemucs', name: 'Demucs (htdemucs)', size: '~80 MB', descKey: 'dl.models.demucs', descDetailKey: 'dl.models.demucs_detail' },
  { id: 'whisper-large-v3', name: 'Whisper Large v3', size: '~3.1 GB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'whisper-large-v2', name: 'Whisper Large v2', size: '~3.1 GB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'whisper-medium', name: 'Whisper Medium', size: '~1.5 GB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'whisper-small', name: 'Whisper Small', size: '~465 MB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'whisper-base', name: 'Whisper Base', size: '~145 MB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'whisper-tiny', name: 'Whisper Tiny', size: '~75 MB', descKey: 'dl.models.whisper', descDetailKey: 'dl.models.whisper_detail' },
  { id: 'pyannote-segmentation', name: 'Pyannote Audio', size: '~220 MB', descKey: 'dl.models.pyannote', descDetailKey: 'dl.models.pyannote_detail' },
  { id: 'qwen3-tts', name: 'Qwen3-TTS', size: '~2.4 GB', descKey: 'dl.models.qwen', descDetailKey: 'dl.models.qwen_detail' },
  { id: 'f5-tts', name: 'F5-TTS', size: '~1.3 GB', descKey: 'dl.models.f5', descDetailKey: 'dl.models.f5_detail' },
  { id: 'xttsv2', name: 'XTTS v2', size: '~1.8 GB', descKey: 'dl.models.xtts', descDetailKey: 'dl.models.xtts_detail' },
  { id: 'gemma4', name: 'Gemma 4 (e4b)', size: '~9.6 GB', descKey: 'dl.models.gemma', descDetailKey: 'dl.models.gemma_detail' },
];

const BACKEND = 'http://127.0.0.1:8000';

export function useModelStatus(hfToken?: string) {
  const [modelStatus, setModelStatus] = useState<Record<string, ModelStatus>>({});
  const [isLoading, setIsLoading] = useState(false);
  const pollRef = useRef<number | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/models/status`);
      if (resp.ok) {
        const data = await resp.json();
        const status: Record<string, ModelStatus> = {};
        for (const m of ALL_MODELS) {
          const ds = data.downloading?.[m.id];
          status[m.id] = {
            done: data.models?.[m.id] || ds?.done || false,
            progress: ds?.progress || (data.models?.[m.id] ? 100 : 0),
            error: ds?.error,
          };
        }
        setModelStatus(status);
        return status;
      }
    } catch { /* backend offline */ }
    return {};
  }, []);

  // Start polling when any model is downloading
  useEffect(() => {
    const hasActiveDownload = Object.values(modelStatus).some(
      s => !s.done && (s.progress === -1 || (s.progress >= 0 && s.progress < 100))
    );
    if (hasActiveDownload && !pollRef.current) {
      pollRef.current = window.setInterval(() => {
        fetchStatus().then(status => {
          if (status && Object.keys(status).length > 0) {
            const stillDownloading = Object.values(status).some(
              s => !s.done && (s.progress === -1 || (s.progress >= 0 && s.progress < 100))
            );
            if (!stillDownloading && pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
              setIsLoading(false);
            }
          }
        });
      }, 2000);
    }
    if (!hasActiveDownload && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
      setIsLoading(false);
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [modelStatus, fetchStatus]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const startDownload = useCallback(async (modelId: string) => {
    // Immediate visual feedback — show "starting" state before API call
    setModelStatus(prev => ({ ...prev, [modelId]: { done: false, progress: -1 } }));
    try {
      const params = new URLSearchParams();
      if (hfToken) params.set('hf_token', hfToken);
      const url = `${BACKEND}/api/models/preload/${modelId}${params.toString() ? '?' + params.toString() : ''}`;
      await fetch(url, { method: 'POST' });
    } catch { /* backend handles it */ }
    setTimeout(() => fetchStatus(), 500);
  }, [fetchStatus, hfToken]);

  const cancelDownload = useCallback(async (modelId: string) => {
    // Immediate feedback
    setModelStatus(prev => ({ ...prev, [modelId]: { done: false, progress: 0, error: 'Cancelled' } }));
    try {
      await fetch(`${BACKEND}/api/models/cancel/${modelId}`, { method: 'POST' });
    } catch { /* ignore */ }
    await fetchStatus();
  }, [fetchStatus]);

  const deleteModel = useCallback(async (modelId: string) => {
    // Show "deleting" state immediately
    setModelStatus(prev => ({ ...prev, [modelId]: { done: false, progress: -2 } }));
    try {
      await fetch(`${BACKEND}/api/models/delete/${modelId}`, { method: 'DELETE' });
    } catch { /* ignore */ }
    setModelStatus(prev => ({ ...prev, [modelId]: { done: false, progress: 0 } }));
    await fetchStatus();
  }, [fetchStatus]);

  return { modelStatus, isLoading, fetchStatus, startDownload, cancelDownload, deleteModel };
}
