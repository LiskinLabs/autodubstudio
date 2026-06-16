import { useState, useEffect, useCallback, useRef } from 'react';

interface LiveConfig {
  translationEngine: string;
  sourceLanguage: string;
  targetLanguage: string;
  subtitlePosition: string;
  fontSize: string;
}

export function useLiveWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [subtitleText, setSubtitleText] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket('ws://localhost:8000/ws/live');

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'subtitle' && data.text) {
            setSubtitleText(data.text);
          } else if (data.type === 'status') {
            setIsCapturing(data.active === true);
          }
        } catch {
          // skip malformed messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsCapturing(false);
        wsRef.current = null;
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      wsRef.current = ws;
    } catch {
      setIsConnected(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsCapturing(false);
  }, []);

  const startCapture = useCallback((config: LiveConfig) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'start', config }));
      setIsCapturing(true);
    } else {
      connect();
      // Retry after connection
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ action: 'start', config }));
          setIsCapturing(true);
        }
      }, 1000);
    }
  }, [connect]);

  const stopCapture = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
    }
    setIsCapturing(false);
    setSubtitleText('');
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    isCapturing,
    subtitleText,
    startCapture,
    stopCapture,
  };
}
