/**
 * FirstRunWizard — Dependency Auto-Installer
 *
 * При первом запуске приложения проверяет наличие Python, uv, Ollama и FFmpeg.
 * Показывает понятный UI со списком недостающих зависимостей.
 * Пользователь может установить их одним кликом (через winget) или вручную по ссылкам.
 *
 * Интегрируется с Tauri бекендом (lib.rs commands: check_dependency, install_dependency, get_missing_deps).
 */
import { useState, useEffect, useCallback } from "react";
import { Button, Spinner, Badge, Card, CardHeader } from "@fluentui/react-components";
import {
  CheckmarkRegular as Check,
  DismissRegular as Dismiss,
  ArrowDownloadRegular as Download,
  OpenRegular as Open,
  WarningRegular as Warning,
} from "@fluentui/react-icons";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

// Описание зависимостей с человеческими названиями и иконками/эмодзи
const DEPS_INFO: Record<string, { label: string; desc: string; emoji: string }> = {
  python: { label: "Python 3.12+", desc: "Язык для AI-бекенда (распознавание речи, перевод, синтез)", emoji: "🐍" },
  uv: { label: "uv (менеджер пакетов)", desc: "Установка Python-зависимостей в 10-100x быстрее pip", emoji: "⚡" },
  ollama: { label: "Ollama", desc: "Локальные AI-модели для перевода и чата", emoji: "🦙" },
  ffmpeg: { label: "FFmpeg", desc: "Обработка видео/аудио и сборка финального файла", emoji: "🎬" },
};

interface DepStatus {
  id: string;
  installed: boolean;
  installing: boolean;
  error?: string;
}

export default function FirstRunWizard({ onComplete }: { onComplete: () => void }) {
  const [deps, setDeps] = useState<DepStatus[]>([]);
  const [checking, setChecking] = useState(true);
  const [installingAll, setInstallingAll] = useState(false);

  // Проверяем все зависимости при монтировании
  const checkAllDeps = useCallback(async () => {
    setChecking(true);
    const results: DepStatus[] = [];
    for (const id of Object.keys(DEPS_INFO)) {
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
        // winget не сработал — открываем URL в браузере
        await openUrl(res.url || DEPS_INFO[id]?.desc || "");
        setDeps(prev => prev.map(d => d.id === id ? { ...d, installing: false, error: "Opened download page" } : d));
        // Перепроверим через 10 секунд
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
    // Повторная проверка
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
                🚀 Добро пожаловать в AutoDub Studio
              </h1>
              <p style={{ color: "var(--colorNeutralForeground3)", marginTop: 8, fontSize: 14 }}>
                Для работы приложения нужны несколько бесплатных программ.
                Выберите что установить — или нажмите «Установить всё».
              </p>
            </div>
          }
        />

        {/* Список зависимостей */}
        <div style={{ margin: "16px 0" }}>
          {deps.map(dep => {
            const info = DEPS_INFO[dep.id];
            return (
              <div key={dep.id} style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "12px 0", borderBottom: "1px solid var(--colorNeutralStroke2)",
              }}>
                <span style={{ fontSize: 24 }}>{info.emoji}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{info.label}</div>
                  <div style={{ color: "var(--colorNeutralForeground3)", fontSize: 12 }}>{info.desc}</div>
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
                    <Badge appearance="filled" color="success" icon={<Check />}>Готово</Badge>
                  ) : dep.installing ? (
                    <Badge appearance="filled" color="brand" icon={<Spinner size="tiny" />}>Установка...</Badge>
                  ) : (
                    <Button
                      size="small"
                      appearance="primary"
                      icon={<Download />}
                      onClick={() => installOne(dep.id)}
                    >
                      Установить
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
              Всё готово — продолжить
            </Button>
          ) : (
            <>
              <Button
                size="large"
                appearance="primary"
                icon={installingAll ? <Spinner size="tiny" /> : <Download />}
                onClick={installAll}
                disabled={installingAll || checking || missingCount === 0}
                style={{ minWidth: 180 }}
              >
                {installingAll ? "Устанавливаю..." : `Установить всё (${missingCount})`}
              </Button>
              <Button
                size="large"
                appearance="secondary"
                icon={<Open />}
                onClick={async () => {
                  await openUrl("https://github.com/LiskinLabs/autodubstudio#readme");
                }}
              >
                Инструкция
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
              Пропустить — я установлю позже вручную
            </Button>
          </div>
        )}

        {/* Powered by */}
        <div style={{
          textAlign: "center", marginTop: 24,
          color: "var(--colorNeutralForeground4)", fontSize: 11,
        }}>
          Все компоненты бесплатны и устанавливаются с официальных сайтов.
          {" "}Powered by LiskinLabs ❤️
        </div>
      </Card>
    </div>
  );
}
