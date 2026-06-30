import { useCallback, useRef, useState } from 'react';
import { fetch } from '@tauri-apps/plugin-http';
import { notifyToast } from '../lib/toast';

export interface OllamaMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface SendMessageOptions {
  model: string;
  messages: OllamaMessage[];
  onChunk: (chunk: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

const OLLAMA_BASE = 'http://127.0.0.1:11434';

const FALLBACK_MAP: Record<string, string> = {
  // Add fallbacks here if needed: 'big-model': 'smaller-model'
};

export function useOllama() {
  const [models, setModels] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const isConnectedRef = useRef<boolean>(false);
  const abortRef = useRef<AbortController | null>(null);

  const updateConnected = useCallback((val: boolean) => {
    setIsConnected(val);
    isConnectedRef.current = val;
  }, []);

  const checkConnection = useCallback(async (): Promise<string[]> => {
    try {
      const res = await fetch(`${OLLAMA_BASE}/api/tags`, {
        method: 'GET'
      });
      if (res.ok) {
        const data = await res.json();
        const modelList = data.models?.map((m: any) => m.name) || [];
        setIsConnected(true);
        isConnectedRef.current = true;
        setModels(modelList);
        return modelList;
      } else {
        updateConnected(false);
        setModels([]);
        return [];
      }
    } catch {
      updateConnected(false);
      setModels([]);
      return [];
    }
  }, []);

  const startOllama = useCallback(async () => {
    try {
      await fetch(`http://127.0.0.1:8000/api/ollama/start`, { method: 'POST' });
      // give it a sec to start
      setTimeout(() => checkConnection(), 2000);
    } catch {
      notifyToast.error("Failed to start Ollama", { description: "Make sure Ollama is installed and try again." });
    }
  }, [checkConnection]);

  const stopOllama = useCallback(async () => {
    try {
      await fetch(`http://127.0.0.1:8000/api/ollama/stop`, { method: 'POST' });
      updateConnected(false);
      setModels([]);
    } catch {
      notifyToast.error("Failed to stop Ollama", { description: "Try stopping it manually via Task Manager." });
    }
  }, []);

  const abort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const sendMessage = useCallback(
    async (opts: SendMessageOptions) => {
      const { model, messages, onChunk, onDone, onError } = opts;
      abort();

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${OLLAMA_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, messages, stream: true }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const text = await res.text().catch(() => 'Unknown error');
          
          // Fallback logic
          const fallbackModel = FALLBACK_MAP[model];
          if (fallbackModel) {
             console.warn(`Model ${model} failed (${res.status}). Falling back to ${fallbackModel}...`);
             // Retry with fallback
             return sendMessage({ ...opts, model: fallbackModel });
          }

          onError?.(`Ollama returned ${res.status}: ${text}`);
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) {
          onError?.('No response stream available');
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            try {
              const parsed = JSON.parse(trimmed);
              if (parsed.message?.content) {
                onChunk(parsed.message.content);
              }
              if (parsed.done) {
                onDone?.();
                return;
              }
            } catch {
              // skip malformed lines
            }
          }
        }

        // process remaining buffer
        if (buffer.trim()) {
          try {
            const parsed = JSON.parse(buffer.trim());
            if (parsed.message?.content) {
              onChunk(parsed.message.content);
            }
          } catch {
            // skip
          }
        }

        onDone?.();
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        
        // Fallback logic for network/connection errors
        const fallbackModel = FALLBACK_MAP[model];
        // if connection fails entirely, maybe Ollama isn't running, but if it's just a timeout, we could fallback
        if (fallbackModel && !isConnectedRef.current) {
           console.warn(`Connection failed for ${model}. Falling back to ${fallbackModel}...`);
           return sendMessage({ ...opts, model: fallbackModel });
        }

        updateConnected(false);
        // Let the UI translate the network error message
        onError?.(err instanceof TypeError ? '' : err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [abort, updateConnected],
  );

  return { sendMessage, abort, isConnected, models, checkConnection, startOllama, stopOllama };
}

export default useOllama;
