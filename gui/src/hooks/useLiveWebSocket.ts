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
  const timeoutRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, []);

  const connect = useCallback(() => {
    if (!isMountedRef.current || wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    try {
      const ws = new WebSocket('ws://127.0.0.1:8000/ws/live');

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
        if (!isMountedRef.current) return;
        setIsConnected(false);
        setIsCapturing(false);
        wsRef.current = null;
        if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
        timeoutRef.current = window.setTimeout(() => connect(), 3000);
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      wsRef.current = ws;
    } catch {
      if (!isMountedRef.current) return;
      setIsConnected(false);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
      timeoutRef.current = window.setTimeout(() => connect(), 3000);
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

  const startCapture = useCallback(async (config: LiveConfig) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'start', config }));
      setIsCapturing(true);
      return;
    }

    connect();
    
    // Wait up to 3 seconds for connection
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 100));
      if (!isMountedRef.current) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: 'start', config }));
        setIsCapturing(true);
        return;
      }
    }
    console.error("Failed to start capture: WebSocket didn't connect in time");
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
