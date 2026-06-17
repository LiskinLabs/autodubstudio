import { useState, useEffect, useCallback, useRef } from 'react';
import { notifyToast } from '../lib/toast';
import { settingsStore } from '../store';

export interface PipelineEvent {
  type: 'progress' | 'log' | 'review_ready' | 'finished' | 'error' | 'info';
  data?: any;
  success?: boolean;
  message?: string;
  original?: string[];
  translated?: string[];
  segments?: any[];
}

export function usePipelineWebSocket(
  onProgress: (val: number) => void,
  onLog: (text: string) => void,
  onReviewReady: (orig: string[], trans: string[], segments: any[]) => void,
  onFinished: (success: boolean, msg: string) => void
) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      // Fetch WebSocket auth token from backend
      const tokenResp = await fetch('http://127.0.0.1:8000/api/token');
      const { token } = await tokenResp.json();

      const ws = new WebSocket('ws://127.0.0.1:8000/ws/pipeline');

      ws.onopen = () => {
        // Authenticate immediately
        ws.send(JSON.stringify({ auth: token }));
      };

      ws.onmessage = (event) => {
        try {
          const data: PipelineEvent = JSON.parse(event.data);

          // Handle auth confirmation (first message after auth is either info or error)
          if (data.type === 'error' && data.message?.includes('Authentication')) {
            console.error('WebSocket auth failed:', data.message);
            ws.close();
            return;
          }

          if (data.type === 'info' && data.message === 'Pipeline started') {
            setIsConnected(true);
          }

          switch (data.type) {
            case 'progress':
              if (data.data !== undefined) onProgress(data.data);
              break;
            case 'log':
              if (data.data) onLog(data.data);
              break;
            case 'review_ready':
              if (data.original && data.translated && data.segments) {
                onReviewReady(data.original, data.translated, data.segments);
              }
              break;
            case 'finished':
              onFinished(!!data.success, data.message || '');
              break;
            case 'error':
              onLog(`[ERROR] ${data.message}`);
              break;
            case 'info':
              onLog(`[INFO] ${data.message}`);
              break;
          }
        } catch (err) {
          console.error('Failed to parse WS message', err);
        }
      };

      ws.onclose = () => {
        console.log('Disconnected from Pipeline WebSocket');
        setIsConnected(false);
        wsRef.current = null;
        if ((window as any).__pipelineToast) {
          notifyToast.dismiss((window as any).__pipelineToast);
          notifyToast.error(settingsStore.t('ws.disconnect') as string);
          (window as any).__pipelineToast = undefined;
        }
        // Auto-reconnect after 3s
        setTimeout(() => connect(), 3000);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      // Retry after 3s
      setTimeout(() => connect(), 3000);
    }
  }, [onProgress, onLog, onReviewReady, onFinished]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const startPipeline = useCallback((config: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'start', config }));
    } else {
      console.error("Cannot start: WebSocket not connected");
      onLog("[SYSTEM] Connection error. Is the backend running?");
    }
  }, [onLog]);

  const resumePipeline = useCallback((segments: any[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'resume', segments }));
    }
  }, []);

  const stopPipeline = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
    }
  }, []);

  return {
    isConnected,
    startPipeline,
    resumePipeline,
    stopPipeline
  };
}