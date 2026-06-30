import { useState, useEffect, useCallback } from "react";
import {
  Button,
  Tooltip,
  makeStyles,
  tokens,
  typographyStyles,
  mergeClasses,
} from "@fluentui/react-components";
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
  BookRegular as Book,
} from "@fluentui/react-icons";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import { useSettings } from "./store";
import { isThemeDark } from "./theme";
import DubbingStudio from "./pages/DubbingStudio";
import LiveSubtitles from "./pages/LiveSubtitles";
import AIChat from "./pages/AIChat";
import SettingsPage from "./pages/Settings";
import FirstRunWizard from "./components/FirstRunWizard";

type TabId =
  | "dubbing"
  | "live"
  | "chat"
  | "settings-general"
  | "settings-models"
  | "settings-keys"
  | "settings-glossaries"
  | "settings-about";

interface NavEntry {
  id: TabId;
  labelKey: string;
  icon: React.ReactElement;
  kbShortcut?: string;
}

/* ── Win11 Design Tokens (Fluent UI v9) ── */
const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    overflow: "hidden",
    overflowX: "hidden",
    minWidth: 0,
  },
  titlebar: {
    height: "48px",
    paddingLeft: tokens.spacingHorizontalM,
    paddingRight: tokens.spacingHorizontalM,
    display: "flex",
    alignItems: "center",
    flexShrink: 0,
    gap: tokens.spacingHorizontalL,
    userSelect: "none",
  },
  titlebarLeft: {
    display: "flex",
    alignItems: "center",
    gap: tokens.spacingHorizontalS,
  },
  titlebarRight: {
    display: "flex",
    alignItems: "center",
    gap: tokens.spacingHorizontalXS,
    marginLeft: "auto",
  },
  logoIcon: {
    width: "20px",
    height: "20px",
    opacity: 0.8,
    marginLeft: tokens.spacingHorizontalS,
  },
  appName: {
    ...typographyStyles.body1Strong,
    letterSpacing: "-0.01em",
  },
  navIcon: { fontSize: "20px" },
  toolbarIcon: { fontSize: "16px" },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
    minHeight: 0,
    position: "relative",
  },
  backdrop: {
    position: "fixed",
    inset: 0,
    zIndex: 40,
    backgroundColor: "rgba(0,0,0,0.3)",
  },
  sidebar: {
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
    overflowX: "hidden",
    overflowY: "auto",
    zIndex: 50,
    paddingTop: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalL,
    backgroundColor: tokens.colorNeutralBackground2,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  sidebarOpen: {},
  navButton: {
    width: "calc(100% - 16px)",
    marginLeft: tokens.spacingHorizontalS,
    marginRight: tokens.spacingHorizontalS,
    marginBottom: "4px",
    justifyContent: "flex-start",
  },
  navButtonActive: { fontWeight: "600" },
  navButtonInactive: { fontWeight: "400" },
  navLabel: { flex: 1, textAlign: "left" as const },
  activeIndicator: {
    width: "3px",
    height: "16px",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorBrandForeground1,
    flexShrink: 0,
  },
  sectionHeader: { marginTop: tokens.spacingVerticalS },
  sidebarFooter: {
    display: "flex",
    alignItems: "center",
    gap: tokens.spacingHorizontalM,
    flexShrink: 0,
    marginTop: "auto",
    paddingTop: tokens.spacingVerticalL,
    paddingBottom: tokens.spacingVerticalS,
    paddingLeft: tokens.spacingHorizontalM,
  },
  footerLogo: { width: "22px", height: "22px", borderRadius: "6px", opacity: 0.3 },
  footerText: { opacity: 0.25, letterSpacing: "0.08em" },
  main: {
    flex: 1,
    minWidth: 0,
    overflowY: "auto",
    overflowX: "hidden",
    backgroundColor: tokens.colorNeutralBackground1,
  },
  pageHidden: { display: "none" },
  pageVisible: { display: "block" },
});

const TOP_NAV: NavEntry[] = [
  { id: "dubbing", labelKey: "nav.dubbing", icon: <Film fontSize={20} />, kbShortcut: "Ctrl+1" },
  { id: "live", labelKey: "nav.live", icon: <Mic fontSize={20} />, kbShortcut: "Ctrl+2" },
  { id: "chat", labelKey: "nav.chat", icon: <Chat fontSize={20} />, kbShortcut: "Ctrl+3" },
];

const SETTINGS_NAV: NavEntry[] = [
  { id: "settings-general", labelKey: "settings.general", icon: <Theme fontSize={20} /> },
  { id: "settings-models", labelKey: "settings.models", icon: <Cpu fontSize={20} /> },
  { id: "settings-keys", labelKey: "settings.keys", icon: <Key fontSize={20} /> },
  { id: "settings-glossaries", labelKey: "settings.glossaries", icon: <Book fontSize={20} /> },
  { id: "settings-about", labelKey: "settings.about", icon: <Person fontSize={20} /> },
];

const App: React.FC = () => {
  const s = useStyles();
  const [activeTab, setActiveTab] = useState<TabId>("dubbing");
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showFirstRun, setShowFirstRun] = useState(
    () => localStorage.getItem("autodub_first_run_completed") !== "true",
  );
  const { t, theme, themeLight, themeDark, setTheme } = useSettings();

  const dark = isThemeDark(theme);
  const ThemeIcon = dark ? Sun : Moon;
  const isSettings = activeTab.startsWith("settings");

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    switch (e.key) {
      case "k": case "K": e.preventDefault(); setCmdPaletteOpen((p) => !p); break;
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

  if (showFirstRun) {
    return (
      <FirstRunWizard
        onComplete={() => {
          localStorage.setItem("autodub_first_run_completed", "true");
          setShowFirstRun(false);
        }}
      />
    );
  }

  const selectTab = (id: TabId) => {
    setActiveTab(id);
    if (window.innerWidth <= 768) setSidebarCollapsed(true);
  };

  return (
    <div className={s.root}>
      <a href="#main-content" className="skip-to-content">{t("app.skip_to_content")}</a>

      {/* ── Win11 Mica Titlebar ── */}
      <div className={mergeClasses("titlebar", "titlebar-surface", s.titlebar)}>
        <div className={s.titlebarLeft}>
          <Button
            appearance="transparent"
            className="win11-hamburger no-drag"
            onClick={() => setSidebarCollapsed((p) => !p)}
            aria-label={t("app.toggle_menu") || "Toggle Menu"}
            icon={<Hamburger fontSize={16} />}
          />
          <img src="/logo-icon.png" alt="" className={s.logoIcon} />
          <span className={s.appName}>AutoDub Studio</span>
        </div>

        <div className={mergeClasses(s.titlebarRight, "no-drag")}>
          <Tooltip content={t("app.search_commands")} relationship="label">
            <Button appearance="subtle" size="small" shape="circular"
              icon={<Search fontSize={16} />}
              onClick={() => setCmdPaletteOpen(true)} />
          </Tooltip>
          <Tooltip content={t("app.toggle_theme")} relationship="label">
            <Button appearance="subtle" size="small" shape="circular"
              icon={<ThemeIcon fontSize={16} />}
              onClick={() => setTheme(dark ? themeLight : themeDark)} />
          </Tooltip>
        </div>
      </div>

      {/* ── Body: Sidebar + Content ── */}
      <div className={s.body}>
        {!sidebarCollapsed && (
          <div className={mergeClasses("win11-sidebar-backdrop", "visible")}
            onClick={() => setSidebarCollapsed(true)}
            role="button" tabIndex={-1}
            aria-label={t("app.close_menu") || "Close menu"} />
        )}

        {/* ── Win11 Settings Sidebar ── */}
        <nav
          className={mergeClasses("win11-sidebar", s.sidebar, sidebarCollapsed && "collapsed", !sidebarCollapsed && "open")}
          role="navigation"
        >
          <div className="win11-nav-section">{t("nav.tools")}</div>
          {TOP_NAV.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <Button key={item.id} role="tab" id={`tab-${item.id}`}
                aria-selected={isActive}
                appearance={isActive ? "secondary" : "subtle"}
                icon={item.icon}
                className="win11-nav-button"
                onClick={() => selectTab(item.id)}>
                <div className={mergeClasses("nav-label", s.navLabel)}>{t(item.labelKey as never)}</div>
              </Button>
            );
          })}

          <div className={mergeClasses("win11-nav-section", s.sectionHeader)}>{t("nav.settings")}</div>
          {SETTINGS_NAV.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <Button key={item.id} role="tab" id={`tab-${item.id}`}
                aria-selected={isActive}
                appearance={isActive ? "secondary" : "subtle"}
                icon={item.icon}
                className="win11-nav-button"
                onClick={() => selectTab(item.id)}>
                <div className={mergeClasses("nav-label", s.navLabel)}>{t(item.labelKey as never)}</div>
                {isActive && <span className={mergeClasses("active-indicator", s.activeIndicator)} />}
              </Button>
            );
          })}

          <div className={s.sidebarFooter}>
            <img src="/logo-icon.png" alt="LiskinLabs" className={s.footerLogo} />
            <span className={mergeClasses("sidebar-footer-text", s.footerText)}>{t("brand.powered_by")}</span>
          </div>
        </nav>

        {/* ── Main Content ── */}
        <main id="main-content" className={s.main}>
          <Page show={activeTab === "dubbing"}><DubbingStudio /></Page>
          <Page show={activeTab === "live"}><LiveSubtitles /></Page>
          <Page show={activeTab === "chat"}><AIChat /></Page>
          <Page show={isSettings}><SettingsPage activeTab={activeTab} /></Page>
        </main>
      </div>

      <StatusBar />
      <CommandPalette
        isOpen={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onNavigate={(tab) => setActiveTab(tab as TabId)}
        onStartPipeline={() => window.dispatchEvent(new CustomEvent("autodub:start-pipeline"))}
      />
    </div>
  );
};

function Page({ show, children }: { show: boolean; children: React.ReactNode }) {
  const s = useStyles();
  return <div className={mergeClasses("animate-slide-up", show ? s.pageVisible : s.pageHidden)}>{children}</div>;
}

export default App;
