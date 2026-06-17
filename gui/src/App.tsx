import { useState, useEffect, useCallback } from "react";
// motion/react removed — pages are always mounted to preserve pipeline state
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

// ─── App ───
const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("dubbing");
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const { t } = useSettings();

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

  return (
    <div className="flex flex-col h-screen w-full bg-base-100 text-base-content overflow-hidden font-sans">
      {/* ── Titlebar (Tauri drag region) ── */}
      <div className="h-9 flex items-center px-4 bg-base-200 border-b border-base-content/10 shrink-0 select-none drag-region">
        <img src="/logo-icon.png" alt="" className="w-4 h-4 mr-2 object-contain pointer-events-none" />
        <span className="text-xs font-semibold tracking-wide opacity-80 pointer-events-none">AutoDub Studio</span>
      </div>

      {/* ── Body: Sidebar + Main ── */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* ── Sidebar (DaisyUI) ── */}
        <aside className="w-60 bg-base-200/50 border-r border-base-content/5 flex flex-col shrink-0" role="complementary" aria-label="Sidebar">
          {/* Brand */}
          <div className="h-14 flex items-center px-4 gap-3 shrink-0 select-none drag-region">
            <img src="/logo-icon.png" alt="AutoDub Studio" className="w-6 h-6 object-contain" />
            <span className="font-semibold text-sm tracking-wide">AutoDub Studio</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-2 py-4" role="navigation" aria-label="Main navigation">
            <ul className="menu menu-sm gap-1">
              {/* TOOLS section */}
              <li className="menu-title uppercase tracking-widest text-[10px] font-bold opacity-50 px-2 mt-2 mb-1">{t('nav.tools')}</li>
              {toolItems.map((item) => (
                <li key={item.id}>
                  <a
                    role="tab"
                    aria-selected={activeTab === item.id}
                    className={activeTab === item.id ? "active bg-primary text-primary-content" : "hover:bg-base-content/10 text-base-content/80"}
                    onClick={() => setActiveTab(item.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setActiveTab(item.id);
                      }
                    }}
                  >
                    <span className="opacity-70">{item.icon}</span>
                    <span className="font-medium">{t(item.labelKey as any)}</span>
                    {item.badge && (
                      <span className="badge badge-xs badge-info ml-1">{item.badge}</span>
                    )}
                    {item.kbShortcut && (
                      <span className="ml-auto text-[10px] opacity-40 font-mono tracking-widest">{item.kbShortcut}</span>
                    )}
                  </a>
                </li>
              ))}

              {/* SYSTEM section */}
              <li className="menu-title uppercase tracking-widest text-[10px] font-bold opacity-50 px-2 mt-4 mb-1">{t('nav.system')}</li>
              {systemItems.map((item) => (
                <li key={item.id}>
                  <a
                    role="tab"
                    aria-selected={activeTab === item.id}
                    className={activeTab === item.id ? "active bg-primary text-primary-content" : "hover:bg-base-content/10 text-base-content/80"}
                    onClick={() => setActiveTab(item.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setActiveTab(item.id);
                      }
                    }}
                  >
                    <span className="opacity-70">{item.icon}</span>
                    <span className="font-medium">{t(item.labelKey as any)}</span>
                    {item.kbShortcut && (
                      <span className="ml-auto text-[10px] opacity-40 font-mono tracking-widest">{item.kbShortcut}</span>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Footer */}
          <div className="flex items-center gap-3 p-4 border-t border-base-content/5 mt-auto">
            <div className="w-8 h-8 rounded-lg bg-base-300 flex items-center justify-center border border-base-content/5 overflow-hidden shrink-0">
              <img src="/logo-icon.png" alt="LiskinLabs" className="w-full h-full object-cover opacity-80" />
            </div>
            <span className="text-[10px] font-bold opacity-40 uppercase tracking-widest">{t('brand.powered_by')}</span>
          </div>
        </aside>

        {/* ── Main Content (all pages kept mounted to preserve state) ── */}
        <main className="flex-1 relative overflow-hidden bg-base-100" role="main" aria-label="Page content">
          <div style={{ display: activeTab === 'dubbing' ? 'block' : 'none', height: '100%' }}>
            <DubbingStudio />
          </div>
          <div style={{ display: activeTab === 'live' ? 'block' : 'none', height: '100%' }}>
            <LiveSubtitles />
          </div>
          <div style={{ display: activeTab === 'chat' ? 'block' : 'none', height: '100%' }}>
            <AIChat />
          </div>
          <div style={{ display: activeTab === 'settings' ? 'block' : 'none', height: '100%' }}>
            <Settings />
          </div>
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
