import { useState, useEffect, useCallback, useRef } from "react";
import { Button, Dialog, DialogSurface, DialogBody, Checkbox, ProgressBar } from "@fluentui/react-components";
import {
  ArrowDownloadRegular as Download,
  CheckmarkRegular as Check,
  SpinnerIosRegular as LoaderCircle,
} from "@fluentui/react-icons";
import { useSettings } from "../store";
import { ALL_MODELS } from "../hooks/useModelStatus";

const MODELS = ALL_MODELS;
const BACKEND = "http://127.0.0.1:8000";

export default function ModelDownloader() {
  const { t } = useSettings();
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [modelStatus, setModelStatus] = useState<Record<string, { done: boolean; progress: number; error?: string }>>({});
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    const hasRun = localStorage.getItem("autodub_first_launch_v2");
    if (!hasRun) {
      setSelected(new Set(["whisper-large-v3", "pyannote-segmentation", "xttsv2", "gemma4"]));
    }
    fetchModelStatus();
  }, []);

  const fetchModelStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/models/status`);
      if (resp.ok) {
        const data = await resp.json();
        const status: typeof modelStatus = {};
        for (const m of MODELS) {
          const ds = data.downloading?.[m.id];
          status[m.id] = {
            done: data.models?.[m.id] || ds?.done || false,
            progress: ds?.progress || (data.models?.[m.id] ? 100 : 0),
            error: ds?.error,
          };
        }
        setModelStatus(status);
        setSelected(prev => {
          const cleaned = new Set(prev);
          for (const m of MODELS) {
            if (status[m.id]?.done) cleaned.delete(m.id);
          }
          return cleaned;
        });
        return status;
      }
    } catch { /* backend offline */ }
    return null;
  }, []);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      let attempts = 0;
      while (mounted && attempts < 10) {
        const res = await fetchModelStatus();
        if (res !== null) break;
        attempts++;
        await new Promise(r => setTimeout(r, 2000));
      }
    };
    init();
    return () => { mounted = false; };
  }, [fetchModelStatus]);

  useEffect(() => {
    const hasDownloading = Object.values(modelStatus).some(s => !s.done && s.progress > 0 && !s.error);
    if (hasDownloading) {
      intervalRef.current = window.setInterval(fetchModelStatus, 2000);
    } else {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [modelStatus, fetchModelStatus]);

  const toggleModel = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const downloadSelected = useCallback(async () => {
    localStorage.setItem("autodub_first_launch_v2", "done");
    const toDownload = MODELS.filter(m => selected.has(m.id) && !modelStatus[m.id]?.done);
    for (const model of toDownload) {
      setModelStatus(prev => ({ ...prev, [model.id]: { done: false, progress: -1 } }));
      try {
        await fetch(`${BACKEND}/api/models/preload/${model.id}`, { method: "POST" });
      } catch { /* backend handles */ }
    }
    fetchModelStatus();
    setIsOpen(false);
  }, [selected, modelStatus, fetchModelStatus]);

  const skipAll = useCallback(() => {
    localStorage.setItem("autodub_first_launch_v2", "done");
    setIsOpen(false);
  }, []);

  // Compact statusbar indicator
  if (!isOpen) {
    const downloading = Object.values(modelStatus).filter(s => !s.done && s.progress > 0).length;
    if (downloading > 0) {
      return (
        <div className="flex items-center gap-1.5 cursor-pointer" style={{
          height: "100%", padding: "0 8px",
          color: "var(--colorBrandForeground1)",
        }} onClick={() => setIsOpen(true)}>
          <Download style={{ fontSize: 13 }} />
          <span style={{ fontSize: 11, fontWeight: 500 }}>{downloading} model(s)</span>
        </div>
      );
    }
    return null;
  }

  const pendingDownloadCount = MODELS.filter(m => selected.has(m.id) && !modelStatus[m.id]?.done).length;
  const cardBorder = "1px solid var(--colorNeutralStroke2)";

  return (
    <Dialog open={isOpen} onOpenChange={(_, data) => { if (!data.open) setIsOpen(false); }}>
      <DialogSurface style={{
        width: 600, maxHeight: "85vh", overflowY: "auto",
        padding: 32, borderRadius: 16,
      }}>
        <DialogBody>
        <div className="text-center mb-6">
          <img src="/logo-icon.png" alt="AutoDub Studio" style={{ width: 64, height: 64, marginBottom: 16, borderRadius: 12, marginLeft: "auto", marginRight: "auto" }} />
          <h2 className="text-xl font-semibold">{t("dl.title")}</h2>
          <p className="text-sm leading-relaxed mt-2" style={{ color: "var(--colorNeutralForeground2)", maxWidth: 360, marginLeft: "auto", marginRight: "auto" }}>
            {t("dl.desc")}
          </p>
        </div>

        <div className="flex flex-col gap-2 mb-6">
          {MODELS.map(model => {
            const st = modelStatus[model.id];
            const isDone = st?.done;
            const isDownloading = !isDone && (st?.progress === -1 || (st?.progress !== undefined && st?.progress > 0));
            const hasRealProgress = (st?.progress ?? 0) >= 5;
            const isChecked = selected.has(model.id) || isDone;

            const labelStyle: React.CSSProperties = {
              display: "flex", alignItems: "center", gap: 16,
              padding: 16, borderRadius: 12,
              border: isDone ? "1px solid var(--colorPaletteGreenBorder1)" : isChecked ? "1px solid var(--colorBrandStroke1)" : cardBorder,
              background: isDone ? "var(--colorPaletteGreenBackground2)" : isChecked ? "var(--colorBrandBackground2)" : "var(--colorNeutralBackground2)",
              cursor: isDone ? "default" : "pointer",
              transition: "all 150ms",
              opacity: isDownloading ? 0.7 : 1,
            };

            return (
              <label key={model.id} style={labelStyle}>
                <Checkbox checked={isChecked} disabled={!!isDone || !!isDownloading} onChange={() => !isDone && toggleModel(model.id)} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold">
                    {model.name}
                    <span className="font-normal text-xs ml-2" style={{ color: "var(--colorNeutralForeground3)" }}>{model.size}</span>
                  </div>
                  <div className="text-xs mt-1" style={{ color: "var(--colorNeutralForeground2)" }}>{t(model.descKey as any)}</div>
                  <div className="text-xs mt-1" style={{ color: "var(--colorBrandForeground1)" }}>{t(model.descDetailKey as any)}</div>
                  {isDownloading && hasRealProgress && (
                    <div style={{ marginTop: 8 }}><ProgressBar value={st.progress} max={100} thickness="medium" /></div>
                  )}
                  {isDownloading && !hasRealProgress && (
                    <div className="text-xs mt-1 font-medium flex items-center gap-1.5" style={{ color: "var(--colorBrandForeground1)" }}>
                      <LoaderCircle style={{ fontSize: 12, animation: "spin 1s linear infinite" }} />
                      {t("dl.downloading")}
                    </div>
                  )}
                  {st?.error && <div className="text-xs mt-1" style={{ color: "var(--colorPaletteRedForeground1)" }}>{st.error}</div>}
                </div>
                {isDone && (
                  <BadgeSmall color="green"><Check style={{ fontSize: 12 }} /></BadgeSmall>
                )}
                {isDownloading && hasRealProgress && (
                  <span className="text-xs font-semibold font-mono" style={{ color: "var(--colorBrandForeground1)" }}>{st.progress}%</span>
                )}
              </label>
            );
          })}
        </div>

        <div className="flex gap-4 mt-4">
          <Button appearance="primary" className="flex-1" icon={<Download style={{ fontSize: 16 }} />} onClick={downloadSelected} disabled={pendingDownloadCount === 0}>
            {t("dl.btn_download")} ({pendingDownloadCount})
          </Button>
          <Button appearance="subtle" onClick={skipAll}>{t("dl.btn_skip")}</Button>
        </div>
        <div className="mt-4 text-xs text-center" style={{ color: "var(--colorNeutralForeground3)" }}>
          {t("dl.note")}
        </div>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

function BadgeSmall({ children, color = "green" }: { children: React.ReactNode; color?: "green" | "neutral" }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", fontSize: 12, fontWeight: 600, borderRadius: 8,
      background: color === "green" ? "var(--colorPaletteGreenBackground2)" : "var(--colorNeutralBackground2)",
      color: color === "green" ? "var(--colorPaletteGreenForeground1)" : "var(--colorNeutralForeground2)",
    }}>{children}</span>
  );
}
