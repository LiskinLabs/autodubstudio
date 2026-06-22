import { useState, useEffect, useCallback } from "react";
import { Button, Tooltip } from "@fluentui/react-components";
import {
  MoviesAndTvRegular as Film,
  MicRegular as Mic,
  ChatRegular as Chat,
  SearchRegular as Search,
  WeatherSunnyRegular as Sun,
  WeatherMoonRegular as Moon,
  PaintBrushRegular as Theme,
  KeyRegular as Key,
  PersonRegular as Person,
  BoardRegular as Cpu,
  NavigationRegular as Hamburger,
} from "@fluentui/react-icons";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import { useSettings } from "./store";
import { isThemeDark } from "./theme";
import DubbingStudio from "./pages/DubbingStudio";
import LiveSubtitles from "./pages/LiveSubtitles";
import AIChat from "./pages/AIChat";
import SettingsPage from "./pages/Settings";

type TabId = "dubbing" | "live" | "chat" | "settings-general" | "settings-models" | "settings-keys" | "settings-about";

interface NavEntry {
  id: TabId;
  labelKey: string;
  icon: React.ReactElement;
  kbShortcut?: string;
}

// Win11 Settings-style navigation: flat list with section headers
const TOP_NAV: NavEntry[] = [
  { id: "dubbing", labelKey: "nav.dubbing", icon: <Film style={{ fontSize: 20 }} />, kbShortcut: "Ctrl+1" },
  { id: "live", labelKey: "nav.live", icon: <Mic style={{ fontSize: 20 }} />, kbShortcut: "Ctrl+2" },
  { id: "chat", labelKey: "nav.chat", icon: <Chat style={{ fontSize: 20 }} />, kbShortcut: "Ctrl+3" },
];

const SETTINGS_NAV: NavEntry[] = [
  { id: "settings-general", labelKey: "settings.general", icon: <Theme style={{ fontSize: 20 }} /> },
  { id: "settings-models", labelKey: "settings.models", icon: <Cpu style={{ fontSize: 20 }} /> },
  { id: "settings-keys", labelKey: "settings.keys", icon: <Key style={{ fontSize: 20 }} /> },
  { id: "settings-about", labelKey: "settings.about", icon: <Person style={{ fontSize: 20 }} /> },
];

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("dubbing");
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { t, theme, themeLight, themeDark, setTheme } = useSettings();

  const dark = isThemeDark(theme);
  const ThemeIcon = dark ? Sun : Moon;
  const isSettings = activeTab.startsWith("settings");

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    switch (e.key) {
      case "k": case "K": e.preventDefault(); setCmdPaletteOpen(p => !p); break;
      case "1": e.preventDefault(); setActiveTab("dubbing"); break;
      case "2": e.preventDefault(); setActiveTab("live"); break;
      case "3": e.preventDefault(); setActiveTab("chat"); break;
      case ",": e.preventDefault(); setActiveTab("settings-general"); break;
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <a href="#main-content" className="skip-to-content">{t("app.skip_to_content")}</a>

      {/* ── Win11 Mica Titlebar ── */}
      <div className="titlebar titlebar-surface flex items-center shrink-0 select-none"
        style={{ height: 48, padding: "0 16px 0 16px", gap: 16 }}>
        
        <div className="flex items-center gap-2">
          {/* Hamburger Menu Button (visible only on small screens) */}
          <Button
            appearance="transparent"
            className="win11-hamburger no-drag"
            onClick={() => setSidebarOpen(p => !p)}
            aria-label={t("app.toggle_menu") || "Toggle Menu"}
            icon={<Hamburger style={{ fontSize: 16 }} />}
          />
          
          <img src="/logo-icon.png" alt="" style={{ width: 20, height: 20, opacity: 0.8, marginLeft: 8 }} />
          <span style={{ fontSize: 13, fontWeight: 500, opacity: 0.7 }}>AutoDub Studio</span>
        </div>

        <div className="flex items-center gap-1 ml-auto no-drag">
          <Tooltip content={t("app.search_commands")} relationship="label">
            <Button appearance="subtle" size="small" shape="circular"
              icon={<Search style={{ fontSize: 16 }} />}
              onClick={() => setCmdPaletteOpen(true)} />
          </Tooltip>
          <Tooltip content={t("app.toggle_theme")} relationship="label">
            <Button appearance="subtle" size="small" shape="circular"
              icon={<ThemeIcon style={{ fontSize: 16 }} />}
              onClick={() => setTheme(dark ? themeLight : themeDark)} />
          </Tooltip>
        </div>
      </div>

      {/* ── Body: Sidebar + Content ── */}
      <div className="flex flex-1 overflow-hidden min-h-0 relative">
        
        {/* Backdrop for mobile sidebar */}
        <div 
          className={`win11-sidebar-backdrop z-40 ${sidebarOpen ? "visible" : ""}`} 
          onClick={() => setSidebarOpen(false)}
        />

        {/* ── Win11 Settings Sidebar (acrylic) ── */}
        <nav className={`win11-sidebar flex flex-col shrink-0 overflow-y-auto z-50 ${sidebarOpen ? "open" : ""}`} role="navigation"
          style={{
            width: 280, padding: "8px 0 16px",
            background: "var(--colorNeutralBackground2)",
            borderRight: "1px solid var(--colorNeutralStroke2)",
          }}>
          {/* Tools section */}
          <div className="win11-nav-section">{t("nav.tools")}</div>
          {TOP_NAV.map(item => (
            <Button key={item.id}
              role="tab" id={`tab-${item.id}`}
              aria-selected={activeTab === item.id}
              appearance={activeTab === item.id ? "secondary" : "subtle"}
              icon={item.icon}
              style={{ width: "calc(100% - 16px)", margin: "0 8px 4px", justifyContent: "flex-start", fontWeight: activeTab === item.id ? 600 : 400 }}
              onClick={() => { setActiveTab(item.id); setSidebarOpen(false); }}>
              {t(item.labelKey as any)}
            </Button>
          ))}

          {/* Settings section */}
          <div className="win11-nav-section" style={{ marginTop: 8 }}>{t("nav.settings")}</div>
          {SETTINGS_NAV.map(item => {
            const isActive = activeTab === item.id;
            return (
              <Button key={item.id}
                role="tab" id={`tab-${item.id}`}
                aria-selected={isActive}
                appearance={isActive ? "secondary" : "subtle"}
                icon={item.icon}
                style={{ width: "calc(100% - 16px)", margin: "0 8px 4px", justifyContent: "flex-start", fontWeight: isActive ? 600 : 400 }}
                onClick={() => { setActiveTab(item.id); setSidebarOpen(false); }}>
                <div style={{ flex: 1, textAlign: "left" }}>{t(item.labelKey as any)}</div>
                {isActive && (
                  <span style={{ width: 3, height: 16, borderRadius: 2, background: "var(--colorBrandForeground1)", flexShrink: 0 }} />
                )}
              </Button>
            );
          })}

          {/* Footer branding */}
          <div className="flex items-center gap-3 shrink-0" style={{ marginTop: "auto", padding: "16px 20px 8px" }}>
            <img src="/logo-icon.png" alt="LiskinLabs" style={{ width: 22, height: 22, borderRadius: 6, opacity: 0.3 }} />
            <span className="text-xs font-semibold opacity-25" style={{ letterSpacing: "0.08em" }}>{t("brand.powered_by")}</span>
          </div>
        </nav>

        {/* ── Main Content ── */}
        <main id="main-content" className="flex-1 overflow-y-auto" role="main"
          style={{ background: "var(--colorNeutralBackground1)" }}>

          <Page key="dubbing" show={activeTab === "dubbing"}><DubbingStudio /></Page>
          <Page key="live" show={activeTab === "live"}><LiveSubtitles /></Page>
          <Page key="chat" show={activeTab === "chat"}><AIChat /></Page>
          <Page key="settings" show={isSettings}><SettingsPage activeTab={activeTab} /></Page>
        </main>
      </div>

      {/* ── Status Bar ── */}
      <StatusBar />

      {/* ── Command Palette ── */}
      <CommandPalette
        isOpen={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onNavigate={(tab) => setActiveTab(tab as TabId)}
        onStartPipeline={() => window.dispatchEvent(new CustomEvent("autodub:start-pipeline"))}
      />
    </div>
  );
};

/** Win11 page wrapper — hides/shows without unmounting to preserve pipeline state */
function Page({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <div className="animate-slide-up" style={{ display: show ? "block" : "none" }}>
      {children}
    </div>
  );
}

export default App;
