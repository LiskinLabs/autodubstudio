import { useRef, useEffect, useState, useCallback } from 'react';

interface LogEntry {
  text: string;
  time: string;
}

interface VirtualLogViewerProps {
  logs: string[];
  maxHeight?: number;
  itemHeight?: number;
}

const OVERSCAN = 5;

// Generate unique timestamps per log entry
function formatLogs(logs: string[]): LogEntry[] {
  const baseTime = new Date();
  return logs.map((log, i) => {
    // Offset each log by i seconds from base time for realistic timestamps
    const entryTime = new Date(baseTime.getTime() - (logs.length - 1 - i) * 1000);
    return {
      text: log,
      time: entryTime.toLocaleTimeString(),
    };
  });
}

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

  const entries = formatLogs(logs);
  const visibleCount = Math.ceil(maxHeight / itemHeight);
  const startIdx = Math.max(0, Math.floor(scrollTop / itemHeight) - OVERSCAN);
  const endIdx = Math.min(entries.length, startIdx + visibleCount + OVERSCAN * 2);
  const visibleItems = entries.slice(startIdx, endIdx);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="font-mono overflow-auto rounded-lg p-3 relative"
      style={{
        height: Math.min(maxHeight, entries.length * itemHeight),
        fontSize: 11,
        background: 'var(--colorNeutralBackground1)',
        border: '1px solid var(--colorNeutralStroke2)',
      }}
      role="log"
      aria-live="polite"
      aria-label="Pipeline log"
    >
      <div style={{ height: entries.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((entry, i) => {
          const actualIdx = startIdx + i;
          const log = entry.text;
          const isError = log.toLowerCase().includes('error');
          const isWarn = log.toLowerCase().includes('warn');
          const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('finished');
          const logColor = isError ? 'var(--colorPaletteRedForeground1)' : isWarn ? 'var(--colorPaletteYellowForeground1)' : isSuccess ? 'var(--colorPaletteGreenForeground1)' : 'var(--colorNeutralForeground3)';

          return (
            <div
              key={actualIdx}
              className="flex items-center gap-2 w-full truncate px-1 rounded"
              style={{
                position: 'absolute', top: actualIdx * itemHeight, height: itemHeight, left: 0, right: 0,
              }}
            >
              <span style={{ color: 'var(--colorNeutralForeground4)', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" }}>[{entry.time}]</span>
              <span className="truncate" style={{ color: logColor }}>{log}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
