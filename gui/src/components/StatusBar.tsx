import { useState, useEffect, useCallback } from "react";
import { Button, Dialog, DialogSurface, DialogTitle, DialogBody, DialogActions, Tooltip } from "@fluentui/react-components";
import { ArrowSyncRegular as Restart } from "@fluentui/react-icons";
import { invoke } from "@tauri-apps/api/core";
import UpdateChecker from "./UpdateChecker";
import ModelDownloader from "./ModelDownloader";
import pkg from "../../package.json";

const BACKEND = "http://127.0.0.1:8000";

interface GpuInfo { cuda_available: boolean; gpu_name: string; vram_used_gb: number; vram_total_gb: number; }
interface PipelineStatus {
  active: boolean; step: string; step_index: number; total_steps: number;
  vram_used_gb: number; vram_total_gb: number; gpu_name: string;
  pytorch_allocated_gb?: number; pytorch_reserved_gb?: number;
  models: Record<string, "idle" | "running" | "done" | "error">;
  translate_engine?: string;
  tts_engine?: string;
}

type ModelType = "local" | "internet" | "paid" | "free";

type ModelDef = { key: string; label: string; type: ModelType; desc: string };

const MODEL_LIST: ModelDef[] = [
  { key: "demucs",    label: "Demucs",    type: "local", desc: "Voice isolation" },
  { key: "whisper",   label: "Whisper",   type: "local", desc: "Speech recognition" },
  { key: "pyannote",  label: "Pyannote",  type: "local", desc: "Speaker diarization" },
  { key: "translate", label: "Translate", type: "paid",  desc: "Text translation" },
  { key: "tts",       label: "TTS",       type: "local", desc: "Speech synthesis" },
  { key: "mux",       label: "Mux",       type: "local", desc: "Audio/video merge" },
];

// Dynamic engine info — reflects actual pipeline configuration
const ENGINE_META: Record<string, { label: string; type: ModelType }> = {
  // Translate engines
  "google":                   { label: "Google",  type: "free" },
  "google translate (free)":  { label: "Google",  type: "free" },
  "deepl":                    { label: "DeepL",   type: "paid" },
  "gemma4":                   { label: "Gemma4",  type: "local" },
  "deepseek":                 { label: "DeepSeek", type: "paid" },
  "gemini":                   { label: "Gemini",  type: "paid" },
  // TTS engines
  "f5-tts":                   { label: "F5",      type: "local" },
  "f5-onnx":                  { label: "F5-ONNX", type: "local" },
  "xttsv2":                   { label: "XTTS",    type: "local" },
  "qwen3-tts":                { label: "Qwen3",   type: "local" },
  "edge-tts":                 { label: "Edge",    type: "free" },
  "azure":                    { label: "Azure",   type: "paid" },
};

function getModelLabel(key: string, pipeline: PipelineStatus): string {
  if (key === "translate") {
    const eng = (pipeline.translate_engine || "").toLowerCase();
    const meta = ENGINE_META[eng];
    return meta ? `⇄ ${meta.label}` : "Translate";
  }
  if (key === "tts") {
    const eng = (pipeline.tts_engine || "").toLowerCase();
    const meta = ENGINE_META[eng];
    return meta ? `🎙 ${meta.label}` : "TTS";
  }
  return MODEL_LIST.find(m => m.key === key)?.label || key;
}

function getModelType(key: string, pipeline: PipelineStatus): ModelType {
  if (key === "translate") {
    const eng = (pipeline.translate_engine || "").toLowerCase();
    return ENGINE_META[eng]?.type || "paid";
  }
  if (key === "tts") {
    const eng = (pipeline.tts_engine || "").toLowerCase();
    return ENGINE_META[eng]?.type || "local";
  }
  return MODEL_LIST.find(m => m.key === key)?.type || "local";
}

function getModelDesc(key: string, pipeline: PipelineStatus): string {
  if (key === "translate") {
    const eng = (pipeline.translate_engine || "").toLowerCase();
    const meta = ENGINE_META[eng];
    return meta ? `${meta.label} translation` : "Text translation";
  }
  if (key === "tts") {
    const eng = (pipeline.tts_engine || "").toLowerCase();
    const meta = ENGINE_META[eng];
    return meta ? `${meta.label} speech synthesis` : "Speech synthesis";
  }
  return MODEL_LIST.find(m => m.key === key)?.desc || key;
}

const STATUS_LABELS: Record<string, string> = {
  idle: "Waiting", running: "Active", done: "Completed", error: "Error",
};

const TYPE_ICON: Record<string, string> = {
  local: "⬇", internet: "🌐", paid: "💲", free: "🆓",
};

function fmt(n: number): string {
  if (n <= 0) return "—";
  if (n >= 10) return `${n.toFixed(0)} GB`;
  return `${n.toFixed(1)} GB`;
}

function fmtPct(pct: number): string {
  if (pct <= 0) return "0%";
  return `${(pct * 100).toFixed(0)}%`;
}

// ── VRAM color: green < 70%, yellow 70-85%, red > 85% ──
function vramColor(pct: number): string {
  if (pct > 0.85) return "var(--colorPaletteRedForeground1)";
  if (pct > 0.70) return "var(--colorPaletteYellowForeground1)";
  return "var(--colorPaletteGreenForeground1)";
}

function ModelDot({ state, label, modelType, desc }: { state: string; label: string; modelType: ModelType; desc: string }) {
  const baseColor =
    state === "running" ? "var(--colorPaletteGreenForeground1)" :
    state === "done"    ? "var(--colorPaletteGreenForeground1)" :
    state === "error"   ? "var(--colorPaletteRedForeground1)" :
    "var(--colorNeutralForeground4)";

  const opacity = state === "idle" ? 0.35 : 1;
  const statusLabel = STATUS_LABELS[state] || state;
  const tooltip = `${desc}\nStatus: ${statusLabel}`;

  return (
    <Tooltip content={tooltip} relationship="label" showDelay={300}>
      <span style={{ display: "flex", alignItems: "center", gap: 3, opacity, transition: "opacity 300ms", cursor: "default" }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", background: baseColor,
          display: "inline-block", flexShrink: 0,
          ...(state === "running" ? { animation: "statusbar-pulse 1.8s ease-in-out infinite" } : {}),
        }} />
        <span style={{ fontSize: 9, fontWeight: 500, whiteSpace: "nowrap" }}>{label}</span>
        <span style={{ fontSize: 8, opacity: 0.5 }}>{TYPE_ICON[modelType] || ""}</span>
      </span>
    </Tooltip>
  );
}

function OllamaDot() {
  const [online, setOnline] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const r = await fetch(`${BACKEND}/api/ollama/status`);
        if (!cancelled && r.ok) { const d = await r.json(); setOnline(d.available === true); }
      } catch { if (!cancelled) setOnline(false); }
    }
    check();
    const iv = setInterval(check, 10000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);
  return (
    <Tooltip content={online ? "Ollama online" : "Ollama offline"} relationship="label" showDelay={300}>
      <span style={{ display: "flex", alignItems: "center", gap: 3, opacity: online ? 0.6 : 0.35, fontSize: 9, padding: "0 4px", transition: "opacity 300ms", cursor: "default" }}>
        <span className={`status-dot ${online ? "green" : "red"}`} style={{ width: 5, height: 5 }} />
        Ollama
      </span>
    </Tooltip>
  );
}

const StatusBar: React.FC = () => {
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

  // ── Merge VRAM: prefer pipeline during active dubbing (more accurate) ──
  const activeVramUsed = pipeline.active && pipeline.vram_used_gb > 0 ? pipeline.vram_used_gb : gpu.vram_used_gb;
  const activeVramTotal = pipeline.active && pipeline.vram_total_gb > 0 ? pipeline.vram_total_gb : gpu.vram_total_gb;
  const hasVram = activeVramTotal > 0;
  const vramPct = hasVram ? Math.min(activeVramUsed / activeVramTotal, 1.0) : 0;
  const vramPctDisplay = hasVram ? fmtPct(vramPct) : "—";
  const gpuName = gpu.cuda_available
    ? (gpu.gpu_name?.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "") || "GPU")
    : "CPU";

  // VRAM cleaner dialog
  const [cleanerOpen, setCleanerOpen] = useState(false);
  const [processes, setProcesses] = useState<Array<{pid: number; name: string; ram_mb: number}>>([]);
  const [selectedPids, setSelectedPids] = useState<Set<number>>(new Set());

  const fetchProcesses = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/system/processes`);
      if (resp.ok) {
        const data = await resp.json();
        setProcesses(data.processes || []);
      }
    } catch {}
  }, []);

  const killSelected = async () => {
    for (const pid of selectedPids) {
      try { await fetch(`${BACKEND}/api/system/kill-process`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({pid}) }); } catch {}
    }
    setSelectedPids(new Set());
    setCleanerOpen(false);
  };

  // Show cleaner button when VRAM > 75% (earlier threshold)
  const vramHigh = vramPct > 0.75;
  const vramCritical = vramPct > 0.90;

  return (<>
    {/* VRAM Cleaner Dialog */}
    <Dialog open={cleanerOpen} onOpenChange={(_, d) => setCleanerOpen(d.open)}>
      <DialogSurface>
        <DialogTitle>VRAM Cleaner — GPU Memory</DialogTitle>
        <DialogBody>
          <div style={{ fontSize: 13, marginBottom: 12, color: "var(--colorNeutralForeground2)" }}>
            VRAM: {fmt(activeVramUsed)} / {fmt(activeVramTotal)} ({vramPctDisplay})
          </div>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {processes.map(p => (
              <label key={p.pid} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", cursor: "pointer", borderBottom: "1px solid var(--colorNeutralStroke2)" }}>
                <input type="checkbox" checked={selectedPids.has(p.pid)} onChange={() => {
                  setSelectedPids(prev => { const next = new Set(prev); next.has(p.pid) ? next.delete(p.pid) : next.add(p.pid); return next; });
                }} />
                <span style={{ flex: 1, fontSize: 13 }}>{p.name}</span>
                <span style={{ fontSize: 11, color: "var(--colorNeutralForeground3)", fontFamily: "'JetBrains Mono', monospace" }}>{p.ram_mb} MB</span>
              </label>
            ))}
          </div>
        </DialogBody>
        <DialogActions>
          <Button appearance="secondary" onClick={() => setCleanerOpen(false)}>Cancel</Button>
          <Button appearance="primary" onClick={killSelected} disabled={selectedPids.size === 0}>Kill Selected ({selectedPids.size})</Button>
        </DialogActions>
      </DialogSurface>
    </Dialog>

    {/* Status Bar */}
    <div className="flex items-center shrink-0 select-none z-50" style={{
      height: 34, padding: "0 8px", fontSize: 11, fontWeight: 500,
      background: "var(--colorNeutralBackground2)",
      color: "var(--colorNeutralForeground3)",
      borderTop: "1px solid var(--colorNeutralStroke2)",
      gap: 0,
    }}>
      {/* GPU / VRAM — dynamically reads from THIS PC's hardware */}
      <span style={{ display: "flex", alignItems: "center", gap: 4, padding: "0 6px", whiteSpace: "nowrap" }}>
        <span className={`status-dot ${gpu.cuda_available ? "green" : "yellow"}`} />
        <span style={{ opacity: 0.7, fontSize: 10 }}>{gpuName}</span>
        {hasVram && (
          <>
            <span style={{ opacity: 0.3, margin: "0 2px" }}>|</span>
            <span title={`VRAM used: ${activeVramUsed.toFixed(2)} GB / ${activeVramTotal.toFixed(2)} GB`}
              style={{ fontWeight: 600, color: vramColor(vramPct), fontSize: 10 }}>
              {fmt(activeVramUsed)}/{fmt(activeVramTotal)}
            </span>
          </>
        )}
      </span>

      <span className="status-separator" style={{ margin: "0 4px" }} />

      {/* Pipeline step info when active */}
      {pipeline.active && (
        <>
          <span style={{ fontSize: 10, opacity: 0.6, whiteSpace: "nowrap", padding: "0 4px" }}>
            Step {pipeline.step_index}/{pipeline.total_steps}
          </span>
          <span className="status-separator" style={{ margin: "0 4px" }} />
        </>
      )}

      {/* Model indicators with hover tooltips */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {MODEL_LIST.map(m => (
          <ModelDot key={m.key} state={pipeline.models[m.key] || "idle"}
            label={getModelLabel(m.key, pipeline)}
            modelType={getModelType(m.key, pipeline)}
            desc={getModelDesc(m.key, pipeline)} />
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* VRAM Cleaner button — always visible when VRAM is high */}
      {vramHigh && (
        <span onClick={() => { fetchProcesses(); setCleanerOpen(true); }}
          title="High VRAM usage — click to clean up background processes"
          style={{
            cursor: "pointer", display: "flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 4, marginRight: 4,
            background: vramCritical ? "var(--colorPaletteRedBackground2)" : "var(--colorPaletteYellowBackground2)",
            border: `1px solid ${vramCritical ? "var(--colorPaletteRedBorder1)" : "var(--colorPaletteYellowBorder1)"}`,
            transition: "all 200ms",
          }}>
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: vramCritical ? "var(--colorPaletteRedForeground1)" : "var(--colorPaletteYellowForeground1)",
            display: "inline-block",
            animation: vramCritical ? "statusbar-pulse 0.9s ease-in-out infinite" : "none",
          }} />
          <span style={{
            fontSize: 9, fontWeight: 700,
            color: vramCritical ? "var(--colorPaletteRedForeground1)" : "var(--colorPaletteYellowForeground1)",
          }}>{vramPctDisplay}</span>
        </span>
      )}

      <Tooltip content="Restart backend & clear Python cache" relationship="label" showDelay={300}>
        <span onClick={async () => {
          try {
            await invoke("restart_backend");
          } catch {}
        }}
        style={{ cursor: "pointer", display: "flex", alignItems: "center", padding: "0 4px", opacity: 0.4, transition: "opacity 150ms" }}
        onMouseEnter={e => (e.currentTarget.style.opacity = "0.8")}
        onMouseLeave={e => (e.currentTarget.style.opacity = "0.4")}
        >
          <Restart style={{ fontSize: 12 }} />
        </span>
      </Tooltip>
      <OllamaDot />
      <UpdateChecker />
      <ModelDownloader />

      <span style={{ opacity: 0.25, marginLeft: 4, fontSize: 9 }}>v{pkg.version}</span>
    </div>
  </>
  );
};

export default StatusBar;
