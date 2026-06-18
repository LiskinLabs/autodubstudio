import { useState, useEffect, useCallback, useMemo } from "react";
import { useSettings } from "../store";
import { useOllama } from "../hooks/useOllama";
import UpdateChecker from "./UpdateChecker";
import ModelDownloader from "./ModelDownloader";
import pkg from "../../package.json";

interface SystemStatus {
  gpu: "gpu" | "cpu";
  gpuName: string;
  vramUsed: number;
  vramTotal: number;
  ramUsed: number;
  ramTotal: number;
}

const BACKEND = "http://127.0.0.1:8000";

/** Format bytes to human-readable */
function fmt(n: number): string {
  if (n <= 0) return "—";
  if (n >= 10) return `${n.toFixed(0)} GB`;
  return `${n.toFixed(1)} GB`;
}

/** Mini progress bar (compact, GPU-style) */
function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <span style={{
      display: "inline-block", width: 40, height: 4,
      background: "var(--colorNeutralBackground3)", borderRadius: 2,
      verticalAlign: "middle", margin: "0 4px",
    }}>
      <span style={{
        display: "block", height: "100%", width: `${pct}%`,
        background: color, borderRadius: 2,
        transition: "width 800ms ease",
      }} />
    </span>
  );
}

const StatusBar: React.FC = () => {
  const { t } = useSettings();
  const { isConnected, checkConnection } = useOllama();
  const [status, setStatus] = useState<SystemStatus>({
    gpu: "gpu", gpuName: "", vramUsed: 0, vramTotal: 0, ramUsed: 0, ramTotal: 0,
  });
  const [backendOnline, setBackendOnline] = useState(false);

  const fetchSystemStatus = useCallback(async () => {
    // Try backend GPU endpoint
    try {
      const resp = await fetch(`${BACKEND}/api/system/gpu`);
      if (resp.ok) {
        const data = await resp.json();
        setBackendOnline(true);
        setStatus(s => ({
          ...s,
          gpu: data.cuda_available ? "gpu" : "cpu",
          gpuName: data.gpu_name || "",
          vramUsed: data.vram_used_gb ?? data.vram_used ?? 0,
          vramTotal: data.vram_total_gb ?? data.vram_total ?? 0,
        }));
      }
    } catch { setBackendOnline(false); }

    // RAM from browser (approximate)
    if ("memory" in performance) {
      const mem = (performance as any).memory;
      setStatus(s => ({
        ...s,
        ramUsed: mem.usedJSHeapSize / 1e9,
        ramTotal: mem.jsHeapSizeLimit / 1e9,
      }));
    } else {
      // Fallback: estimate from navigator.deviceMemory
      const dm = (navigator as any).deviceMemory;
      if (dm) setStatus(s => ({ ...s, ramTotal: dm }));
    }
  }, []);

  useEffect(() => {
    checkConnection();
    fetchSystemStatus();
    const interval = setInterval(() => {
      checkConnection();
      fetchSystemStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [checkConnection, fetchSystemStatus]);

  const hasVram = status.vramTotal > 0;
  const hasRam = status.ramTotal > 0;

  const vramColor = useMemo(() => {
    if (!hasVram) return "var(--colorNeutralForeground3)";
    const pct = status.vramUsed / status.vramTotal;
    if (pct > 0.9) return "var(--colorPaletteRedForeground1)";
    if (pct > 0.7) return "var(--colorPaletteYellowForeground1)";
    return "var(--colorPaletteGreenForeground1)";
  }, [status.vramUsed, status.vramTotal, hasVram]);

  const ramColor = useMemo(() => {
    if (!hasRam) return "var(--colorNeutralForeground3)";
    const pct = status.ramUsed / status.ramTotal;
    if (pct > 0.9) return "var(--colorPaletteRedForeground1)";
    if (pct > 0.7) return "var(--colorPaletteYellowForeground1)";
    return "var(--colorPaletteGreenForeground1)";
  }, [status.ramUsed, status.ramTotal, hasRam]);

  const chipStyle: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: 5,
    height: "100%", padding: "0 8px",
    borderRadius: 6, cursor: "default",
  };

  return (
    <div className="flex items-center shrink-0 select-none z-50" style={{
      height: 34, padding: "0 10px", fontSize: 11, fontWeight: 500,
      background: "var(--colorNeutralBackground2)",
      color: "var(--colorNeutralForeground3)",
      borderTop: "1px solid var(--colorNeutralStroke2)",
    }}>
      {/* Backend status */}
      <div style={chipStyle} title={backendOnline ? "Backend connected" : "Backend offline"}>
        <span className={`status-dot ${backendOnline ? "green" : "red"}`} />
        <span style={{ opacity: 0.7 }}>{backendOnline ? "API" : "Off"}</span>
      </div>
      <div className="status-separator" />

      {/* GPU */}
      <div style={chipStyle} title={status.gpuName || t("status.gpu")}>
        <span className={`status-dot ${status.gpu === "gpu" ? "green" : "yellow"}`} />
        <span style={{ opacity: status.gpu === "gpu" ? 1 : 0.6 }}>
          {status.gpu === "gpu"
            ? (status.gpuName
              ? status.gpuName.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "")
              : "GPU")
            : "CPU"}
        </span>
      </div>

      {/* VRAM */}
      {hasVram && (
        <>
          <div className="status-separator" />
          <div style={chipStyle} title={`VRAM: ${fmt(status.vramUsed)} / ${fmt(status.vramTotal)}`}>
            <span style={{ opacity: 0.5, marginRight: 1 }}>VRAM</span>
            <MiniBar value={status.vramUsed} max={status.vramTotal} color={vramColor} />
            <span style={{ color: vramColor, fontWeight: 600, minWidth: 56, textAlign: "right" }}>
              {fmt(status.vramUsed)}/{fmt(status.vramTotal)}
            </span>
          </div>
        </>
      )}

      {/* RAM */}
      {hasRam && status.ramTotal > 0.5 && (
        <>
          <div className="status-separator" />
          <div style={chipStyle} title={`RAM: ${fmt(status.ramUsed)} / ${fmt(status.ramTotal)}`}>
            <span style={{ opacity: 0.5, marginRight: 1 }}>RAM</span>
            <MiniBar value={status.ramUsed} max={status.ramTotal} color={ramColor} />
            <span style={{ color: ramColor, fontWeight: 600, minWidth: 56, textAlign: "right" }}>
              {fmt(status.ramUsed)}/{fmt(status.ramTotal)}
            </span>
          </div>
        </>
      )}

      {/* Ollama */}
      <div className="status-separator" />
      <div style={chipStyle} title={isConnected ? t("status.ollama") : t("status.ollama_off")}>
        <span className={`status-dot ${isConnected ? "green" : "red"}`} />
        <span style={{ opacity: 0.6 }}>Ollama</span>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Update + Models */}
      <UpdateChecker />
      <ModelDownloader />

      {/* Version */}
      <div style={{ ...chipStyle, opacity: 0.3, marginLeft: 4 }}>
        <span>v{pkg.version}</span>
      </div>
    </div>
  );
};

export default StatusBar;
