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
      className="font-mono text-xs overflow-auto bg-base-100 rounded-lg border border-base-content/10 p-3 relative"
      style={{ 
        height: Math.min(maxHeight, logs.length * itemHeight),
      }}
    >
      {/* Spacer for total scroll height */}
      <div style={{ height: logs.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((log, i) => {
          const actualIdx = startIdx + i;
          const isError = log.toLowerCase().includes('error');
          const isWarn = log.toLowerCase().includes('warn');
          const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('finished');
          const colorClass = isError ? 'text-error' : isWarn ? 'text-warning' : isSuccess ? 'text-success' : 'text-info';

          return (
            <div
              key={actualIdx}
              className="flex items-center gap-2 w-full truncate px-1"
              style={{
                position: 'absolute',
                top: actualIdx * itemHeight,
                height: itemHeight,
                left: 0,
                right: 0,
              }}
            >
              <span className="text-base-content/40 shrink-0">[{time}]</span>
              <span className={`truncate ${colorClass}`}>{log}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
