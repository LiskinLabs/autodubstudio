import { useState, useEffect, useCallback } from "react";
import { Badge } from "@fluentui/react-components";
import { useSettings } from "../store";
import UpdateChecker from "./UpdateChecker";
import ModelDownloader from "./ModelDownloader";
import pkg from "../../package.json";

const BACKEND = "http://127.0.0.1:8000";

interface GpuInfo { cuda_available: boolean; gpu_name: string; vram_used_gb: number; vram_total_gb: number; }
interface PipelineStatus {
  active: boolean; step: string; step_index: number; total_steps: number;
  vram_used_gb: number; vram_total_gb: number; gpu_name: string;
  models: Record<string, "idle" | "running" | "done" | "error">;
}

type ModelDef = { key: string; label: string; type: "local" | "internet" | "paid" };

const MODEL_LIST: ModelDef[] = [
  { key: "demucs",    label: "Demucs",    type: "local" },
  { key: "whisper",   label: "Whisper",   type: "local" },
  { key: "pyannote",  label: "Pyannote",  type: "local" },
  { key: "translate", label: "Translate", type: "paid" },
  { key: "tts",       label: "TTS",       type: "local" },
  { key: "mux",       label: "Mux",       type: "local" },
];

const TYPE_ICON: Record<string, string> = {
  local: "⬇",      // локальная модель
  internet: "🌐",  // нужен интернет
  paid: "💲",      // платный API
};

function fmt(n: number): string {
  if (n <= 0) return "—";
  if (n >= 10) return `${n.toFixed(0)} GB`;
  return `${n.toFixed(1)} GB`;
}

function ModelDot({ state, label, modelType }: { state: string; label: string; modelType: string }) {
  const dotColor =
    state === "running" ? "var(--colorPaletteGreenForeground1)" :
    state === "done"    ? "var(--colorPaletteGreenForeground1)" :
    state === "error"   ? "var(--colorPaletteRedForeground1)" :
    "var(--colorNeutralForeground4)";

  const anim = state === "running" ? "animate-pulse" : "";
  const opacity = state === "idle" ? 0.35 : 1;

  return (
    <span title={`${label} [${modelType}] — ${state}`} style={{ display: "flex", alignItems: "center", gap: 3, opacity, transition: "opacity 300ms" }}>
      <span className={anim} style={{
        width: 6, height: 6, borderRadius: "50%", background: dotColor,
        display: "inline-block", flexShrink: 0,
      }} />
      <span style={{ fontSize: 9, fontWeight: 500, whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontSize: 8, opacity: 0.5 }}>{TYPE_ICON[modelType] || ""}</span>
    </span>
  );
}

const StatusBar: React.FC = () => {
  const { t } = useSettings();
  const [gpu, setGpu] = useState<GpuInfo>({ cuda_available: false, gpu_name: "", vram_used_gb: 0, vram_total_gb: 0 });
  const [pipeline, setPipeline] = useState<PipelineStatus>({
    active: false, step: "", step_index: 0, total_steps: 6,
    vram_used_gb: 0, vram_total_gb: 0, gpu_name: "",
    models: { demucs: "idle", whisper: "idle", pyannote: "idle", translate: "idle", tts: "idle", mux: "idle" },
  });

  const fetchStatus = useCallback(async () => {
    try {
      const [gpuResp, pipeResp] = await Promise.all([
        fetch(`${BACKEND}/api/system/gpu`),
        fetch(`${BACKEND}/api/pipeline/status`),
      ]);
      if (gpuResp.ok) setGpu(await gpuResp.json());
      if (pipeResp.ok) setPipeline(await pipeResp.json());
    } catch {}
  }, []);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 2000);
    return () => clearInterval(iv);
  }, [fetchStatus]);

  const hasVram = gpu.vram_total_gb > 0;
  const vramPct = hasVram ? gpu.vram_used_gb / gpu.vram_total_gb : 0;
  const vramColor = vramPct > 0.9 ? "var(--colorPaletteRedForeground1)" : vramPct > 0.7 ? "var(--colorPaletteYellowForeground1)" : "var(--colorPaletteGreenForeground1)";

  return (
    <div className="flex items-center shrink-0 select-none z-50" style={{
      height: 34, padding: "0 8px", fontSize: 11, fontWeight: 500,
      background: "var(--colorNeutralBackground2)",
      color: "var(--colorNeutralForeground3)",
      borderTop: "1px solid var(--colorNeutralStroke2)",
      gap: 0,
    }}>
      {/* GPU / VRAM */}
      <span style={{ display: "flex", alignItems: "center", gap: 4, padding: "0 6px", whiteSpace: "nowrap" }}>
        <span className={`status-dot ${gpu.cuda_available ? "green" : "yellow"}`} />
        <span style={{ opacity: 0.7, fontSize: 10 }}>
          {gpu.cuda_available ? (gpu.gpu_name?.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "") || "GPU") : "CPU"}
        </span>
        {hasVram && (
          <>
            <span style={{ opacity: 0.3, margin: "0 2px" }}>|</span>
            <span style={{ fontWeight: 600, color: vramColor, fontSize: 10 }}>
              {fmt(gpu.vram_used_gb)}/{fmt(gpu.vram_total_gb)}
            </span>
          </>
        )}
      </span>

      <span className="status-separator" style={{ margin: "0 4px" }} />

      {/* Pipeline step info when active */}
      {pipeline.active && (
        <>
          <span style={{ fontSize: 10, opacity: 0.6, whiteSpace: "nowrap", padding: "0 4px" }}>
            {pipeline.step_index}/{pipeline.total_steps}
          </span>
          <span className="status-separator" style={{ margin: "0 4px" }} />
        </>
      )}

      {/* Model indicators */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {MODEL_LIST.map(m => (
          <ModelDot key={m.key} state={pipeline.models[m.key] || "idle"} label={m.label} modelType={m.type} />
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Ollama status — simple dot */}
      <span style={{ display: "flex", alignItems: "center", gap: 3, opacity: 0.5, fontSize: 9, padding: "0 4px" }}>
        <span className="status-dot red" style={{ width: 5, height: 5 }} />
        Ollama
      </span>

      <UpdateChecker />
      <ModelDownloader />

      <span style={{ opacity: 0.25, marginLeft: 4, fontSize: 9 }}>v{pkg.version}</span>
    </div>
  );
};

export default StatusBar;
