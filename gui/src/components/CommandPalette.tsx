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

export default function CommandPalette({ isOpen, onClose, onNavigate, onStartPipeline, isPipelineRunning: _isPipelineRunning }: CommandPaletteProps) {
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
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-[20vh] bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-[560px] max-h-[480px] bg-base-200 border border-base-content/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="p-4 border-b border-base-content/10">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder={t('cmd.placeholder')}
            className="w-full bg-transparent border-none outline-none text-base-content text-lg"
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto p-2">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-base-content/50 text-sm">
              {t('cmd.no_results')}
            </div>
          ) : (
            groups.map(group => (
              <div key={group}>
                <div className="px-3 pt-3 pb-1 text-xs font-semibold text-base-content/50 uppercase tracking-wider">
                  {group}
                </div>
                {filtered.filter(c => c.group === group).map((cmd, _i) => {
                  const globalIdx = filtered.indexOf(cmd);
                  const isSelected = globalIdx === selectedIndex;
                  return (
                    <div
                      key={cmd.id}
                      onClick={() => { cmd.action(); onClose(); }}
                      onMouseEnter={() => setSelectedIndex(globalIdx)}
                      className={`flex items-center gap-3 py-2 px-3 rounded-lg cursor-pointer text-sm transition-colors duration-75 ${
                        isSelected ? 'bg-base-content/10 text-base-content' : 'text-base-content/70 hover:bg-base-content/5'
                      }`}
                    >
                      <span className="text-base">{cmd.icon}</span>
                      <span className="flex-1">{cmd.label}</span>
                      {cmd.shortcut && (
                        <span className="text-xs text-base-content/40 font-mono">
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
        <div className="py-2 px-4 border-t border-base-content/10 text-xs text-base-content/50 flex gap-4">
          <span>{t('cmd.navigate')}</span>
          <span>{t('cmd.select')}</span>
          <span>{t('cmd.close')}</span>
        </div>
      </div>
    </div>
  );
}
