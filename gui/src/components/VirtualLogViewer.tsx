import { useRef, useEffect, useState, useCallback } from 'react';

interface VirtualLogViewerProps {
  logs: string[];
  maxHeight?: number;
  itemHeight?: number;
}

const OVERSCAN = 5;

export default function VirtualLogViewer({ logs, maxHeight = 200, itemHeight = 22 }: VirtualLogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const handleScroll = useCallback(() => {
    if (containerRef.current) {
      setScrollTop(containerRef.current.scrollTop);
    }
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs.length]);

  const time = new Date().toLocaleTimeString();
  const visibleCount = Math.ceil(maxHeight / itemHeight);
  const startIdx = Math.max(0, Math.floor(scrollTop / itemHeight) - OVERSCAN);
  const endIdx = Math.min(logs.length, startIdx + visibleCount + OVERSCAN * 2);

  const visibleItems = logs.slice(startIdx, endIdx);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        height: Math.min(maxHeight, logs.length * itemHeight),
        overflow: 'auto',
        position: 'relative',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--text-xs)',
      }}
    >
      {/* Spacer for total scroll height */}
      <div style={{ height: logs.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((log, i) => {
          const actualIdx = startIdx + i;
          const isError = log.toLowerCase().includes('error');
          const isWarn = log.toLowerCase().includes('warn');
          const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('finished');
          const colorClass = isError ? 'log-error' : isWarn ? 'log-warning' : isSuccess ? 'log-success' : 'log-info';

          return (
            <div
              key={actualIdx}
              className="log-line"
              style={{
                position: 'absolute',
                top: actualIdx * itemHeight,
                height: itemHeight,
                left: 0,
                right: 0,
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
              }}
            >
              <span className="log-time">[{time}]</span>
              <span className={`log-text ${colorClass}`}>{log}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
