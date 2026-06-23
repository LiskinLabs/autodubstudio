/**
 * FirstRunWizard — Dependency Auto-Installer
 *
 * При первом запуске приложения проверяет наличие Python, uv, Ollama и FFmpeg.
 * Показывает понятный UI со списком недостающих зависимостей.
 * Пользователь может установить их одним кликом (через winget) или вручную по ссылкам.
 *
 * Все строки используют t() из store.ts для мультиязычности (en/ru/tr).
 */
import { useState, useEffect, useCallback } from "react";
import { Button, Spinner, Badge, Card, CardHeader } from "@fluentui/react-components";
import {
  CheckmarkRegular as Check,
  ArrowDownloadRegular as DownloadIcon,
  OpenRegular as Open,
} from "@fluentui/react-icons";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useSettings } from "../store";

// Эмодзи для зависимостей (языконезависимые)
const DEPS_EMOJI: Record<string, string> = {
  python: "🐍", uv: "⚡", ollama: "🦙", ffmpeg: "🎬", packages: "📦",
};

interface DepStatus {
  id: string;
  installed: boolean;
  installing: boolean;
  error?: string;
}

export default function FirstRunWizard({ onComplete }: { onComplete: () => void }) {
  const { t } = useSettings();
  const [deps, setDeps] = useState<DepStatus[]>([]);
  const [checking, setChecking] = useState(true);
  const [installingAll, setInstallingAll] = useState(false);

  // Проверяем все зависимости при монтировании
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

  // Установка одной зависимости
  const installOne = async (id: string) => {
    setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: true, error: undefined } : d));
    try {
      const res = await invoke("install_dependency", { name: id }) as any;
      if (res.status === "installed") {
        setDeps(prev => prev.map(d => d.id === id ? { ...d, installed: true, installing: false } : d));
      } else {
        await openUrl(res.url || "");
        setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: false, error: t("frun.opened_url") } : d));
        setTimeout(() => checkAllDeps(), 10000);
      }
    } catch (e: any) {
      setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: false, error: String(e) } : d));
    }
  };

  // Установить всё сразу
  const installAll = async () => {
    setInstallingAll(true);
    const missing = deps.filter(d => !d.installed);
    for (const dep of missing) {
      await installOne(dep.id);
    }
    setInstallingAll(false);
    await checkAllDeps();
  };

  const missingCount = deps.filter(d => !d.installed).length;
  const allInstalled = !checking && missingCount === 0;

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "var(--colorNeutralBackground2)", padding: 24,
    }}>
      <Card style={{ maxWidth: 560, width: "100%", padding: 32 }}>
        <CardHeader
          header={
            <div style={{ textAlign: "center" }}>
              <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
                {t("frun.title")}
              </h1>
              <p style={{ color: "var(--colorNeutralForeground3)", marginTop: 8, fontSize: 14 }}>
                {t("frun.subtitle")}
              </p>
            </div>
          }
        />

        {/* Список зависимостей */}
        <div style={{ margin: "16px 0" }}>
          {deps.map(dep => {
            const labelKey = `frun.deps_${dep.id}` as any;
            const descKey = `frun.deps_${dep.id}_desc` as any;
            return (
              <div key={dep.id} style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "12px 0", borderBottom: "1px solid var(--colorNeutralStroke2)",
              }}>
                <span style={{ fontSize: 24 }}>{DEPS_EMOJI[dep.id]}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{t(labelKey)}</div>
                  <div style={{ color: "var(--colorNeutralForeground3)", fontSize: 12 }}>{t(descKey)}</div>
                  {dep.error && (
                    <div style={{ color: "var(--colorStatusDangerForeground1)", fontSize: 11, marginTop: 4 }}>
                      ⚠ {dep.error}
                    </div>
                  )}
                </div>
                <div style={{ minWidth: 100, textAlign: "right" }}>
                  {checking ? (
                    <Spinner size="tiny" />
                  ) : dep.installed ? (
                    <Badge appearance="filled" color="success" icon={<Check />}>{t("frun.ready")}</Badge>
                  ) : dep.installing ? (
                    <Badge appearance="filled" color="brand" icon={<Spinner size="tiny" />}>{t("frun.installing")}</Badge>
                  ) : (
                    <Button
                      size="small"
                      appearance="primary"
                      icon={<DownloadIcon />}
                      onClick={() => installOne(dep.id)}
                    >
                      {t("frun.install")}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Кнопки действий */}
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 20 }}>
          {allInstalled ? (
            <Button
              size="large"
              appearance="primary"
              icon={<Check />}
              onClick={onComplete}
              style={{ minWidth: 200 }}
            >
              {t("frun.all_done")}
            </Button>
          ) : (
            <>
              <Button
                size="large"
                appearance="primary"
                icon={installingAll ? <Spinner size="tiny" /> : <DownloadIcon />}
                onClick={installAll}
                disabled={installingAll || checking || missingCount === 0}
                style={{ minWidth: 180 }}
              >
                {installingAll ? t("frun.installing_all") : t("frun.install_all").replace("{count}", String(missingCount))}
              </Button>
              <Button
                size="large"
                appearance="secondary"
                icon={<Open />}
                onClick={async () => {
                  await openUrl("https://github.com/LiskinLabs/autodubstudio#readme");
                }}
              >
                {t("frun.instructions")}
              </Button>
            </>
          )}
        </div>

        {/* Ссылка "Пропустить" */}
        {!allInstalled && (
          <div style={{ textAlign: "center", marginTop: 16 }}>
            <Button
              appearance="transparent"
              size="small"
              onClick={onComplete}
              style={{ color: "var(--colorNeutralForeground3)" }}
            >
              {t("frun.skip")}
            </Button>
          </div>
        )}

        {/* Footer */}
        <div style={{
          textAlign: "center", marginTop: 24,
          color: "var(--colorNeutralForeground4)", fontSize: 11,
        }}>
          {t("frun.footer")}
          {" "}❤️ LiskinLabs
        </div>
      </Card>
    </div>
  );
}
