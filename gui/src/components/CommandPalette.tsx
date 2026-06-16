import { useState, useEffect, useCallback, useRef } from 'react';
import { useSettings } from '../store';

interface Command {
  id: string;
  label: string;
  icon?: string;
  shortcut?: string;
  group: string;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: string) => void;
  onStartPipeline?: () => void;
  isPipelineRunning?: boolean;
}

export default function CommandPalette({ isOpen, onClose, onNavigate, onStartPipeline, isPipelineRunning }: CommandPaletteProps) {
  const { t } = useSettings();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Command[] = [
    { id: 'nav-dubbing', label: t('nav.dubbing'), icon: '🎬', shortcut: '⌘1', group: 'Navigation', action: () => onNavigate('dubbing') },
    { id: 'nav-live', label: t('nav.live'), icon: '🎤', shortcut: '⌘2', group: 'Navigation', action: () => onNavigate('live') },
    { id: 'nav-chat', label: t('nav.chat'), icon: '💬', shortcut: '⌘3', group: 'Navigation', action: () => onNavigate('chat') },
    { id: 'nav-settings', label: t('nav.settings'), icon: '⚙️', shortcut: '⌘,', group: 'Navigation', action: () => onNavigate('settings') },
    { id: 'start-pipeline', label: t('dubbing.start'), icon: '▶️', shortcut: '⌘Enter', group: 'Actions', action: () => { onStartPipeline?.(); onClose(); } },
    { id: 'new-project', label: t('dubbing.btn.new'), icon: '🆕', shortcut: '⌘N', group: 'Actions', action: () => { onNavigate('dubbing'); onClose(); } },
    { id: 'live-start', label: t('live.start'), icon: '🎙️', shortcut: '⌘⇧L', group: 'Actions', action: () => { onNavigate('live'); onClose(); } },
  ];

  const filtered = query
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()) || c.group.toLowerCase().includes(query.toLowerCase()))
    : commands;

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action();
          onClose();
        }
        break;
      case 'Escape':
        e.preventDefault();
        onClose();
        break;
    }
  }, [filtered, selectedIndex, onClose]);

  // Global Esc handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) { e.preventDefault(); onClose(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const groups = [...new Set(filtered.map(c => c.group))];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '20vh',
        background: 'rgba(0,0,0,0.5)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 560,
          maxHeight: 480,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg), 0 0 0 1px var(--border-subtle)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div style={{ padding: 'var(--space-4)', borderBottom: '1px solid var(--border-subtle)' }}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-lg)',
              fontFamily: 'var(--font-sans)',
            }}
          />
        </div>

        {/* Results */}
        <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-2)' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
              No results found.
            </div>
          ) : (
            groups.map(group => (
              <div key={group}>
                <div style={{ padding: 'var(--space-3) var(--space-3) var(--space-1)', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {group}
                </div>
                {filtered.filter(c => c.group === group).map((cmd, i) => {
                  const globalIdx = filtered.indexOf(cmd);
                  const isSelected = globalIdx === selectedIndex;
                  return (
                    <div
                      key={cmd.id}
                      onClick={() => { cmd.action(); onClose(); }}
                      onMouseEnter={() => setSelectedIndex(globalIdx)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-2) var(--space-3)',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        background: isSelected ? 'var(--bg-hover)' : 'transparent',
                        color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                        fontSize: 'var(--text-sm)',
                        transition: 'background 80ms ease',
                      }}
                    >
                      <span style={{ fontSize: 'var(--text-base)' }}>{cmd.icon}</span>
                      <span style={{ flex: 1 }}>{cmd.label}</span>
                      {cmd.shortcut && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-disabled)', fontFamily: 'var(--font-mono)' }}>
                          {cmd.shortcut}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: 'var(--space-2) var(--space-4)', borderTop: '1px solid var(--border-subtle)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', display: 'flex', gap: 'var(--space-4)' }}>
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
