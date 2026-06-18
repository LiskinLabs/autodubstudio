import { useState, useEffect, useCallback, useRef } from "react";
import { Dialog, DialogSurface } from "@fluentui/react-components";
import {
  MoviesAndTvRegular as Film,
  MicRegular as Mic,
  ChatRegular as MessageCircle,
  SettingsRegular as Settings,
  PlayRegular as Play,
  AddRegular as Plus,
  MusicNote2Regular as Radio,
  SearchRegular as Search,
} from "@fluentui/react-icons";
import { useSettings } from "../store";

interface Command {
  id: string;
  label: string;
  icon: React.ReactNode;
  shortcut?: string;
  group: string;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: string) => void;
  onStartPipeline?: () => void;
}

export default function CommandPalette({ isOpen, onClose, onNavigate, onStartPipeline }: CommandPaletteProps) {
  const { t } = useSettings();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Command[] = [
    { id: "nav-dubbing", label: t("nav.dubbing"), icon: <Film style={{ fontSize: 16 }} />, shortcut: "Ctrl+1", group: t("cmd.group_navigation"), action: () => onNavigate("dubbing") },
    { id: "nav-live", label: t("nav.live"), icon: <Mic style={{ fontSize: 16 }} />, shortcut: "Ctrl+2", group: t("cmd.group_navigation"), action: () => onNavigate("live") },
    { id: "nav-chat", label: t("nav.chat"), icon: <MessageCircle style={{ fontSize: 16 }} />, shortcut: "Ctrl+3", group: t("cmd.group_navigation"), action: () => onNavigate("chat") },
    { id: "nav-settings", label: t("nav.settings"), icon: <Settings style={{ fontSize: 16 }} />, shortcut: "Ctrl+,", group: t("cmd.group_navigation"), action: () => onNavigate("settings-general") },
    { id: "start-pipeline", label: t("dubbing.start"), icon: <Play style={{ fontSize: 16 }} />, shortcut: "Ctrl+Enter", group: t("cmd.group_actions"), action: () => { onStartPipeline?.(); onClose(); } },
    { id: "new-project", label: t("dubbing.btn.new"), icon: <Plus style={{ fontSize: 16 }} />, shortcut: "Ctrl+N", group: t("cmd.group_actions"), action: () => { onNavigate("dubbing"); onClose(); } },
    { id: "live-start", label: t("live.start"), icon: <Radio style={{ fontSize: 16 }} />, shortcut: "Ctrl+Shift+L", group: t("cmd.group_actions"), action: () => { onNavigate("live"); onClose(); } },
  ];

  const filtered = query
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()) || c.group.toLowerCase().includes(query.toLowerCase()))
    : commands;

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); setSelectedIndex(i => Math.min(i + 1, filtered.length - 1)); break;
      case "ArrowUp": e.preventDefault(); setSelectedIndex(i => Math.max(i - 1, 0)); break;
      case "Enter": e.preventDefault(); if (filtered[selectedIndex]) filtered[selectedIndex].action(); break;
      case "Escape": e.preventDefault(); onClose(); break;
    }
  }, [filtered, selectedIndex, onClose]);

  const groups = [...new Set(filtered.map(c => c.group))];

  return (
    <Dialog open={isOpen} onOpenChange={(_, data) => { if (!data.open) onClose(); }}>
      <DialogSurface style={{
        width: 520, maxHeight: 420, padding: 0,
        borderRadius: 16, overflow: "hidden",
        boxShadow: "0 16px 48px rgba(0,0,0,0.2)",
      }}>
        {/* Search input */}
        <div style={{
          padding: 16, borderBottom: "1px solid var(--colorNeutralStroke2)",
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <Search style={{ fontSize: 16, color: "var(--colorNeutralForeground4)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder={t("cmd.placeholder")}
            style={{
              width: "100%", background: "transparent", border: "none", outline: "none",
              fontSize: 16, fontFamily: "'Inter', 'Segoe UI', sans-serif",
              color: "var(--colorNeutralForeground1)",
            }}
            aria-label={t("cmd.search_commands")}
          />
        </div>

        {/* Results */}
        <div role="listbox" style={{ flex: 1, overflow: "auto", padding: 8 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--colorNeutralForeground3)", fontSize: 14 }}>
              {t("cmd.no_results")}
            </div>
          ) : (
            groups.map(group => (
              <div key={group}>
                <div style={{
                  padding: "12px 12px 6px", fontSize: 11, fontWeight: 600,
                  color: "var(--colorNeutralForeground3)",
                  textTransform: "uppercase", letterSpacing: "0.05em",
                }}>
                  {group}
                </div>
                {filtered.filter(c => c.group === group).map(cmd => {
                  const globalIdx = filtered.indexOf(cmd);
                  const isSelected = globalIdx === selectedIndex;
                  return (
                    <div
                      key={cmd.id}
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => cmd.action()}
                      onMouseEnter={() => setSelectedIndex(globalIdx)}
                      style={{
                        display: "flex", alignItems: "center", gap: 12,
                        padding: "10px 12px", borderRadius: 8,
                        cursor: "pointer", fontSize: 14,
                        transition: "all 75ms ease",
                        background: isSelected ? "var(--colorBrandBackground2)" : "transparent",
                        color: isSelected ? "var(--colorBrandForeground1)" : "var(--colorNeutralForeground2)",
                        fontWeight: isSelected ? 500 : 400,
                      }}
                    >
                      <span style={{ color: "var(--colorNeutralForeground3)", flexShrink: 0 }}>{cmd.icon}</span>
                      <span className="flex-1">{cmd.label}</span>
                      {cmd.shortcut && (
                        <span style={{
                          fontSize: 11, color: "var(--colorNeutralForeground4)",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
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
        <div style={{
          padding: "10px 16px", borderTop: "1px solid var(--colorNeutralStroke2)",
          fontSize: 11, color: "var(--colorNeutralForeground3)",
          display: "flex", gap: 16, fontWeight: 500,
        }}>
          <span className="flex items-center gap-1.5">{t("cmd.navigate")} <KBD>↑↓</KBD></span>
          <span className="flex items-center gap-1.5">{t("cmd.select")} <KBD>↵</KBD></span>
          <span className="flex items-center gap-1.5">{t("cmd.close")} <KBD>Esc</KBD></span>
        </div>
      </DialogSurface>
    </Dialog>
  );
}

function KBD({ children }: { children: React.ReactNode }) {
  return (
    <kbd style={{
      fontSize: 10, padding: "2px 6px",
      background: "var(--colorNeutralBackground3)",
      border: "1px solid var(--colorNeutralStroke2)",
      borderRadius: 4, fontFamily: "'JetBrains Mono', monospace",
    }}>{children}</kbd>
  );
}
