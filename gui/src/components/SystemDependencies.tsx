import { useState, useEffect, useCallback } from "react";
import { Button, Spinner, Badge } from "@fluentui/react-components";
import {
  CheckmarkRegular as Check,
  ArrowDownloadRegular as DownloadIcon,
  ArrowClockwiseRegular as RefreshIcon,
} from "@fluentui/react-icons";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useSettings } from "../store";

const DEPS_EMOJI: Record<string, string> = {
  python: "🐍", uv: "⚡", ollama: "🦙", ffmpeg: "🎬", packages: "📦",
};

interface DepStatus {
  id: string;
  installed: boolean;
  installing: boolean;
  error?: string;
}

export default function SystemDependencies() {
  const { t } = useSettings();
  const [deps, setDeps] = useState<DepStatus[]>([]);
  const [checking, setChecking] = useState(true);

  const checkAllDeps = useCallback(async () => {
    setChecking(true);
    const results: DepStatus[] = [];
    for (const id of Object.keys(DEPS_EMOJI)) {
      try {
        const res = await invoke("check_dependency", { name: id }) as any;
        results.push({ id, installed: res.installed, installing: false });
      } catch {
        results.push({ id, installed: false, installing: false });
      }
    }
    setDeps(results);
    setChecking(false);
  }, []);

  useEffect(() => {
    checkAllDeps();
  }, [checkAllDeps]);

  const installOne = async (id: string) => {
    setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: true, error: undefined } : d));
    try {
      const res = await invoke("install_dependency", { name: id }) as any;
      if (res.status === "installed") {
        setDeps(prev => prev.map(d => d.id === id ? { ...d, installed: true, installing: false } : d));
      } else {
        await openUrl(res.url || "");
        setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: false, error: t("frun.opened_url") || "Opened URL for manual installation" } : d));
        setTimeout(() => checkAllDeps(), 10000);
      }
    } catch (e: any) {
      setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: false, error: String(e) } : d));
    }
  };

  return (
    <div className="win11-card mb-6">
      <div className="win11-card-header flex items-center justify-between">
        <span>{t("settings.system_deps") || "System Dependencies"}</span>
        <Button 
          appearance="subtle" 
          icon={<RefreshIcon />} 
          size="small" 
          onClick={checkAllDeps} 
          disabled={checking}
          title={t("settings.refresh_deps") || "Refresh Status"}
        />
      </div>
      <div className="win11-card-body">
        <p className="text-xs mb-4" style={{ color: "var(--colorNeutralForeground3)" }}>
          {t("settings.system_deps_desc") || "Core dependencies required for the application to function properly."}
        </p>

        <div className="flex flex-col gap-2">
          {deps.map(dep => {
            const labelKey = `frun.deps_${dep.id}` as any;
            return (
              <div key={dep.id} className="flex items-center justify-between p-3 rounded-md" style={{ background: "var(--colorNeutralBackground2)" }}>
                <div className="flex items-center gap-3">
                  <span style={{ fontSize: 20 }}>{DEPS_EMOJI[dep.id]}</span>
                  <div>
                    <div className="text-sm font-semibold display-flex items-center gap-2">
                      {t(labelKey) || dep.id}
                      {dep.id === "ollama" && (
                        <Badge size="small" appearance="tint" color="warning" style={{ marginLeft: 8 }}>
                          {t("frun.optional_cloud") || "Optional (Cloud Fallback)"}
                        </Badge>
                      )}
                    </div>
                    {dep.error && (
                      <div className="text-xs mt-1" style={{ color: "var(--colorStatusDangerForeground1)" }}>
                        ⚠ {dep.error}
                      </div>
                    )}
                  </div>
                </div>
                <div className="shrink-0 ml-4">
                  {checking ? (
                    <Spinner size="tiny" />
                  ) : dep.installed ? (
                    <Badge appearance="tint" color="success" icon={<Check />}>{t("frun.ready") || "Installed"}</Badge>
                  ) : dep.installing ? (
                    <Badge appearance="filled" color="brand" icon={<Spinner size="tiny" />}>{t("frun.installing") || "Installing..."}</Badge>
                  ) : (
                    <Button
                      size="small"
                      appearance="primary"
                      icon={<DownloadIcon />}
                      onClick={() => installOne(dep.id)}
                    >
                      {t("frun.install") || "Install"}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
