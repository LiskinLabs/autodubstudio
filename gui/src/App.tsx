import { useState, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import { useSettings } from "./store";

import DubbingStudio from "./pages/DubbingStudio";
import LiveSubtitles from "./pages/LiveSubtitles";
import AIChat from "./pages/AIChat";
import Settings from "./pages/Settings";

// ─── Tab type ───
type TabId = "dubbing" | "live" | "chat" | "settings";

interface NavEntry {
  id: TabId;
  labelKey: string;
  icon: React.ReactNode;
  badge?: string;
  kbShortcut?: string;
  section: "tools" | "system";
}

// ─── SVG Icons (18×18, stroke-based) ───
const IconFilm = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 7h5M17 17h5M2 2h20v20H2z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconMicrophone = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v4 M8 23h8"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconChat = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconSettings = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle
      cx="12"
      cy="12"
      r="3"
      stroke="currentColor"
      strokeWidth="1.5"
      fill="none"
    />
    <path
      d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// ─── Navigation config ───
const NAV_ITEMS: NavEntry[] = [
  { id: "dubbing", labelKey: "nav.dubbing", icon: IconFilm, kbShortcut: "⌘1", section: "tools" },
  {
    id: "live",
    labelKey: "nav.live",
    icon: IconMicrophone,
    kbShortcut: "⌘2",
    section: "tools",
  },
  {
    id: "chat",
    labelKey: "nav.chat",
    icon: IconChat,
    badge: "NEW",
    kbShortcut: "⌘3",
    section: "tools",
  },
  { id: "settings", labelKey: "nav.settings", icon: IconSettings, kbShortcut: "⌘,", section: "system" },
];

// ─── Page map ───
const PAGE_MAP: Record<TabId, React.FC> = {
  dubbing: DubbingStudio,
  live: LiveSubtitles,
  chat: AIChat,
  settings: Settings,
};

// ─── App ───
const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("dubbing");
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const { t } = useSettings();

  const ActivePage = PAGE_MAP[activeTab];

  const toolItems = NAV_ITEMS.filter((n) => n.section === "tools");
  const systemItems = NAV_ITEMS.filter((n) => n.section === "system");

  // ─── Keyboard shortcuts ───
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;

    switch (e.key) {
      case 'k':
      case 'K':
        e.preventDefault();
        setCmdPaletteOpen(prev => !prev);
        break;
      case '1': e.preventDefault(); setActiveTab('dubbing'); break;
      case '2': e.preventDefault(); setActiveTab('live'); break;
      case '3': e.preventDefault(); setActiveTab('chat'); break;
      case ',': e.preventDefault(); setActiveTab('settings'); break;
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const tabOrder: TabId[] = ['dubbing', 'live', 'chat', 'settings'];
  const handleNavKey = useCallback((e: React.KeyboardEvent, direction: 1 | -1) => {
    const idx = tabOrder.indexOf(activeTab);
    const next = tabOrder[idx + direction];
    if (next) setActiveTab(next);
  }, [activeTab]);

  return (
    <div className="app-root">
      {/* ── Titlebar (Tauri drag region) ── */}
      <div className="titlebar">
        <span className="titlebar-title">AutoDub Studio</span>
      </div>

      {/* ── Body: Sidebar + Main ── */}
      <div className="app-body">
        {/* ── Sidebar (inline) ── */}
        <aside className="sidebar" role="complementary" aria-label="Sidebar">
          {/* Brand */}
          <div className="sidebar-brand">
            <img
              src="/logo.png"
              alt="AutoDub Studio"
              className="sidebar-brand-icon"
            />
            <span className="sidebar-brand-text">AutoDub Studio</span>
          </div>

          {/* Navigation */}
          <nav className="sidebar-nav" role="navigation" aria-label="Main navigation">
            {/* TOOLS section */}
            <div className="sidebar-section-label">{t('nav.tools')}</div>
            {toolItems.map((item) => (
              <div
                key={item.id}
                role="tab"
                aria-selected={activeTab === item.id}
                aria-label={t(item.labelKey as any)}
                tabIndex={0}
                className={`nav-item${activeTab === item.id ? " active" : ""}`}
                onClick={() => setActiveTab(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActiveTab(item.id);
                  }
                }}
              >
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{t(item.labelKey as any)}</span>
                {item.badge && (
                  <span className="nav-badge new">{item.badge}</span>
                )}
                {item.kbShortcut && (
                  <span className="nav-kb">{item.kbShortcut}</span>
                )}
              </div>
            ))}

            {/* SYSTEM section */}
            <div className="sidebar-section-label">{t('nav.system')}</div>
            {systemItems.map((item) => (
              <div
                key={item.id}
                role="tab"
                aria-selected={activeTab === item.id}
                aria-label={t(item.labelKey as any)}
                tabIndex={0}
                className={`nav-item${activeTab === item.id ? " active" : ""}`}
                onClick={() => setActiveTab(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActiveTab(item.id);
                  }
                }}
              >
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{t(item.labelKey as any)}</span>
                {item.kbShortcut && (
                  <span className="nav-kb">{item.kbShortcut}</span>
                )}
              </div>
            ))}
          </nav>

          {/* Footer */}
          <div className="sidebar-footer">
            <img
              src="/logo.png"
              alt="Teknorob"
              className="sidebar-footer-logo"
            />
            <span className="sidebar-footer-text">Powered by LiskinLabs</span>
          </div>
        </aside>

        {/* ── Main Content ── */}
        <main className="main-content" role="main" aria-label="Page content">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              style={{ height: '100%' }}
            >
              <ActivePage />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* ── Status Bar ── */}
      <StatusBar />

      {/* ── Command Palette ── */}
      <CommandPalette
        isOpen={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onNavigate={(tab) => setActiveTab(tab as TabId)}
        onStartPipeline={() => {
          const event = new CustomEvent('autodub:start-pipeline');
          window.dispatchEvent(event);
        }}
      />
    </div>
  );
};

export default App;
