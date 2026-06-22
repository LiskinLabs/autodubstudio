import { useState, useCallback, useEffect, type DragEvent } from "react";
import { Button, Select, Input, Switch, ProgressBar, Field, Badge, Card, CardHeader, Radio, RadioGroup, Spinner } from "@fluentui/react-components";
import {
  MoviesAndTvRegular as Film,
  ClipboardRegular as Clipboard,
  PlayRegular as Play,
  CheckmarkRegular as Check,
  InfoRegular as Info,
  SquareRegular as Square,
  FastForwardRegular as FastForward,
  ClipboardPasteRegular as CopyIcon,
  FolderOpenRegular,
} from "@fluentui/react-icons";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { useSettings } from "../store";
import { useOllama } from "../hooks/useOllama";
import { usePipelineWebSocket } from "../hooks/usePipelineWebSocket";
import { notifyToast } from "../lib/toast";
import VirtualLogViewer from "../components/VirtualLogViewer";

type PipelineState = "idle" | "running" | "review" | "done";
type PipelineMode = "automatic" | "manual";

interface Config {
  targetLanguage: string; voiceModel: string; translationEngine: string;
  translatorModel: string; pipelineMode: PipelineMode;
  autoMux: boolean; voiceCloning: boolean; audioSeparation: boolean;
  exportSrt: boolean; keepIntermediate: boolean; autoOpenFolder: boolean;
  demucsModel: string;
}

const PIPELINE_STEPS = ["source", "demucs", "whisper", "translate", "tts", "mux"] as const;
type StepKey = (typeof PIPELINE_STEPS)[number];
const STEP_T_KEY: Record<StepKey, string> = {
  source: "dubbing.step.source", demucs: "dubbing.step.demucs", whisper: "dubbing.step.whisper",
  translate: "dubbing.step.translate", tts: "dubbing.step.tts", mux: "dubbing.step.mux",
};

const LANG_T_KEY: Record<string, string> = {
  ru: "lang.ru", tr: "lang.tr", en: "lang.en", es: "lang.es", fr: "lang.fr",
  de: "lang.de", ar: "lang.ar", zh: "lang.zh", ja: "lang.ja", ko: "lang.ko",
  it: "lang.it", pt: "lang.pt", pl: "lang.pl", hi: "lang.hi",
};
const LANGS = ["ru", "tr", "en", "es", "fr", "de", "ar", "zh", "ja", "ko", "it", "pt", "pl", "hi"];

const TTS_BY_LANG: Record<string, string[]> = {
  "ru": ["qwen3-tts", "xttsv2", "f5-tts", "f5-onnx", "azure", "edge-tts"],
  "en": ["qwen3-tts", "xttsv2", "f5-tts", "f5-onnx", "azure", "edge-tts"],
  "tr": ["xttsv2", "f5-tts", "f5-onnx", "azure", "edge-tts"],
  "es": ["qwen3-tts", "xttsv2", "azure", "edge-tts"],
  "fr": ["qwen3-tts", "xttsv2", "azure", "edge-tts"],
  "de": ["xttsv2", "azure", "edge-tts"],
  "ar": ["xttsv2", "azure", "edge-tts"],
  "zh": ["qwen3-tts", "f5-tts", "azure", "edge-tts"],
  "ja": ["azure", "edge-tts"], "ko": ["azure", "edge-tts"],
  "it": ["xttsv2", "azure", "edge-tts"], "pt": ["xttsv2", "azure", "edge-tts"],
  "pl": ["xttsv2", "azure", "edge-tts"], "hi": ["azure", "edge-tts"]
};

const TTS_T_KEY: Record<string, string> = {
  "qwen3-tts": "dubbing.voice.qwen3_full", "xttsv2": "dubbing.voice.xttsv2_full",
  "f5-tts": "dubbing.voice.f5tts_full", "f5-onnx": "dubbing.voice.f5onnx_full",
  "azure": "dubbing.voice.azure_cloud", "edge-tts": "dubbing.voice.edge_cloud",
};

// Fluent UI v9 semantic badge colors
type BadgeColor = "brand" | "danger" | "important" | "informative" | "severe" | "subtle" | "success" | "warning";
const SPEAKER_BADGE_COLORS: Record<string, BadgeColor> = {
  SPEAKER_00: "informative", // Blue
  SPEAKER_01: "danger",      // Red
  SPEAKER_02: "success",     // Green
  SPEAKER_03: "warning",     // Yellow/Amber
  SPEAKER_04: "important",   // Gray/Dark
  SPEAKER_05: "severe",      // Dark Orange/Red
  default:    "subtle",      // Light Gray
};

function PipelineSteps({ activeStep, t }: { activeStep: number; t: (k: string) => string }) {
  return (
    <div className="win11-steps">
      {PIPELINE_STEPS.map((key, i) => {
        const num = i + 1;
        const state = num < activeStep ? "done" : num === activeStep ? "active" : "";
        return (
          <div key={key} className={`win11-step${state ? ` ${state}` : ""}`}>
            {state === "done" ? <Check style={{ fontSize: 14 }} /> : <span style={{ width: 16, textAlign: "center", fontSize: 12 }}>{num}</span>}
            {t(STEP_T_KEY[key] as any)}
          </div>
        );
      })}
    </div>
  );
}

export default function DubbingStudio() {
  const { t, settings, lang } = useSettings();
  const [pipelineState, setPipelineState] = useState<PipelineState>("idle");
  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [editedSegments, setEditedSegments] = useState<any[]>([]);

  const onProgress = useCallback((val: number) => setProgress(val), []);
  const onLog = useCallback((text: string) => {
    setLogs(prev => [...prev, text]);
    const lower = text.toLowerCase();
    if (lower.includes("demucs")) setActiveStep(2);
    else if (lower.includes("whisper") || lower.includes("распознавание")) setActiveStep(3);
    else if (lower.includes("перевод") || lower.includes("translate")) setActiveStep(4);
    else if (lower.includes("озвучка") || lower.includes("tts")) setActiveStep(5);
    else if (lower.includes("сборка") || lower.includes("ffmpeg") || lower.includes("mux")) setActiveStep(6);
  }, []);

  const onReviewReady = useCallback((_orig: string[], _trans: string[], segments: any[]) => {
    setEditedSegments(segments);
    setPipelineState("review");
  }, []);

  const [outputPath, setOutputPath] = useState("");
  const onFinished = useCallback((success: boolean, msg: string) => {
    setPipelineState("done");
    onLog(`[FINISHED] Success: ${success}, Message: ${msg}`);
    // Extract output file path from message: "Успешно: C:\...\file.mkv"
    const match = msg.match(/([A-Z]:\\[^\s]+\.(mkv|mp4|avi|srt))/i);
    if (match) setOutputPath(match[1]);
  }, [onLog]);

  const { isConnected, startPipeline, resumePipeline, stopPipeline } = usePipelineWebSocket(onProgress, onLog, onReviewReady, onFinished);
  const { models: ollamaModels, checkConnection } = useOllama();

  const [config, setConfig] = useState<Config>({
    targetLanguage: "ru", voiceModel: "xttsv2", translationEngine: "deepseek",
    translatorModel: "gemma2", pipelineMode: "automatic",
    autoMux: true, voiceCloning: true, audioSeparation: true,
    exportSrt: true, keepIntermediate: false, autoOpenFolder: true,
    demucsModel: "htdemucs_ft",
  });

  useEffect(() => { checkConnection(); }, [checkConnection]);

  useEffect(() => {
    const valid = TTS_BY_LANG[config.targetLanguage] || [];
    if (!valid.includes(config.voiceModel) && valid.length > 0) updateConfig("voiceModel", valid[0]);
  }, [config.targetLanguage, config.voiceModel]);

  useEffect(() => {
    if (config.translationEngine === "ollama" && ollamaModels.length > 0) {
      if (!ollamaModels.includes(config.translatorModel)) updateConfig("translatorModel", ollamaModels[0]);
    } else if (config.translationEngine === "deepseek") updateConfig("translatorModel", "deepseek-chat");
    else if (config.translationEngine === "google" || config.translationEngine === "gemini") updateConfig("translatorModel", "default");
  }, [config.translationEngine, ollamaModels, config.translatorModel]);

  const updateConfig = useCallback(<K extends keyof Config>(key: K, value: Config[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => { e.preventDefault(); setIsDragging(true); }, []);
  const handleDragLeave = useCallback(() => setIsDragging(false), []);
  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files.length > 0) setFileName(e.dataTransfer.files[0].name);
  }, []);

  const handlePaste = useCallback(async () => {
    try { const text = await navigator.clipboard.readText(); if (text) setYoutubeUrl(text); } catch {}
  }, []);

  const handleStart = useCallback(() => {
    if (!fileName && !youtubeUrl) return;
    if (!isConnected) {
      notifyToast.error(t("toast.backend_error"), { description: t("toast.backend_offline") });
      onLog(`[SYSTEM] ${t("toast.backend_offline")}`);
      return;
    }
    notifyToast.success(t("toast.pipeline_started"), { description: t("toast.pipeline_init"), duration: 3000 });
    setPipelineState("running"); setActiveStep(1); setProgress(0); setLogs([]);
    startPipeline({
      video_path: fileName || youtubeUrl, out_dir: "",
      langs: [config.targetLanguage.toLowerCase()],
      whisper_model: JSON.parse(localStorage.getItem("autodub_models") || "{}")?.whisperModel || "large-v3",
      device: "cuda", translation_engine: config.translationEngine, dub_engine: config.voiceModel,
      gemini_key: settings.geminiKey, deepseek_key: settings.deepseekKey, deepl_key: settings.deeplKey,
      hf_key: settings.hfKey,
      manual_mode: config.pipelineMode === "manual",
      ui_language: lang || "ru",
      demucs_model: config.demucsModel,
    });
  }, [fileName, youtubeUrl, config, startPipeline, settings, isConnected, t, onLog]);

  const handleContinue = useCallback(() => {
    setPipelineState("running"); setActiveStep(5); setProgress(67);
    resumePipeline(editedSegments);
  }, [resumePipeline, editedSegments]);

  const handleReset = useCallback(() => {
    setPipelineState("idle"); setActiveStep(0); setProgress(0); setFileName(""); setYoutubeUrl("");
    setLogs([]); setEditedSegments([]); setOutputPath("");
    // Сброс бекенда — индикаторы моделей станут серыми
    fetch("http://127.0.0.1:8000/api/pipeline/reset", { method: "POST" }).catch(() => {});
  }, []);

  const handleSelectFile = async () => {
    try {
      const sel = await open({ multiple: false, filters: [{ name: t("dubbing.file_filter"), extensions: ["mp4", "mkv", "avi", "webm", "mov"] }] });
      if (sel) setFileName(sel as string);
    } catch (e) { console.error(e); }
  };

  return (
    <div className="win11-page">
      <h1 className="win11-page-title">{t("dubbing.title")}</h1>
      <p className="win11-page-subtitle">{t("dubbing.subtitle")}</p>

      {/* Idle State */}
      {pipelineState === "idle" && (
        <>
          {/* Drop Zone */}
          <div className={`win11-dropzone${isDragging ? " drag-over" : ""}`}
            onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={handleSelectFile}>
            <Film style={{ fontSize: 48, color: "var(--colorNeutralForeground3)", opacity: 0.4 }} />
            <div className="font-semibold" style={{ fontSize: 16 }}>
              {fileName ? <>{t("dubbing.file.selected")} <span style={{ color: "var(--colorBrandForeground1)" }}>{fileName}</span></> : t("dubbing.dropzone")}
            </div>
            <span className="text-xs" style={{ color: "var(--colorNeutralForeground3)" }}>{t("dubbing.supported")}</span>
          </div>

          {/* YouTube URL */}
          <div className="flex gap-3" style={{ marginBottom: 24 }}>
            <Input className="flex-1" placeholder={t("dubbing.youtube_placeholder")} value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)} size="large" />
            <Button icon={<Clipboard />} onClick={handlePaste} size="large">{t("dubbing.btn.paste")}</Button>
          </div>

          {/* Configuration Card */}
          <div className="win11-card">
            <div className="win11-card-header">{t("dubbing.config")}</div>
            <div className="win11-card-body">
              <div className="win11-config-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                <Field label={t("dubbing.target_lang")} style={{ padding: "8px 0" }}>
                  <Select value={config.targetLanguage} onChange={(e) => updateConfig("targetLanguage", e.target.value)} size="large">
                    {LANGS.map(c => (<option key={c} value={c}>{t(LANG_T_KEY[c] as any)}</option>))}
                  </Select>
                </Field>
                <Field label={t("dubbing.voice_model")} style={{ padding: "8px 0" }}>
                  <Select value={config.voiceModel} onChange={(e) => updateConfig("voiceModel", e.target.value)} size="large">
                    {(TTS_BY_LANG[config.targetLanguage] || []).map(k => (<option key={k} value={k}>{t(TTS_T_KEY[k] as any) || k}</option>))}
                  </Select>
                </Field>
                <Field label={t("dubbing.translation_engine")} style={{ padding: "8px 0" }}>
                  <Select value={config.translationEngine} onChange={(e) => updateConfig("translationEngine", e.target.value)} size="large">
                    <option value="deepseek">{t("dubbing.engine.deepseek")}</option>
                    <option value="gemini">{t("dubbing.engine.gemini")}</option>
                    <option value="deepl">{t("dubbing.engine.deepl")}</option>
                    <option value="ollama">{t("dubbing.engine.ollama")}</option>
                    <option value="google">{t("dubbing.engine.google")}</option>
                  </Select>
                </Field>
                <Field label={t("dubbing.translator_model")} style={{ padding: "8px 0" }}>
                  <Select value={config.translatorModel}
                    onChange={(e) => updateConfig("translatorModel", e.target.value)}
                    disabled={config.translationEngine === "google" || config.translationEngine === "gemini"} size="large">
                    {config.translationEngine === "ollama"
                      ? (ollamaModels.length > 0 ? ollamaModels.map(m => <option key={m} value={m}>{m}</option>) : <option value="">{t("dubbing.no_models")}</option>)
                      : config.translationEngine === "deepseek"
                        ? <><option value="deepseek-chat">deepseek-chat</option><option value="deepseek-reasoner">deepseek-reasoner</option></>
                        : config.translationEngine === "deepl"
                          ? <option value="deepl-api">{t("dubbing.translator.deepl_api")}</option>
                          : <option value="default">{t("dubbing.translator.default")}</option>
                    }
                  </Select>
                </Field>
              </div>
            </div>
          </div>

          {/* Pipeline Mode Card */}
          <div className="win11-card">
            <div className="win11-card-header">{t("dubbing.mode")}</div>
            <div className="win11-card-body">
              <RadioGroup
                value={config.pipelineMode}
                onChange={(_, data) => updateConfig("pipelineMode", data.value as PipelineMode)}
                layout="horizontal"
              >
                {(["automatic", "manual"] as const).map(mode => (
                  <Radio
                    key={mode}
                    value={mode}
                    label={t(`dubbing.mode.${mode === "automatic" ? "auto" : "manual"}_label` as any)}
                    style={{ flex: 1 }}
                  />
                ))}
              </RadioGroup>
              <div className="text-xs mt-3" style={{ color: "var(--colorNeutralForeground3)", lineHeight: 1.4 }}>
                {t(`dubbing.mode.${config.pipelineMode === "automatic" ? "auto" : "manual"}_desc` as any)}
              </div>
            </div>
          </div>

          {/* Advanced Settings Card */}
          <div className="win11-card">
            <div className="win11-card-header">{t("dubbing.advanced")}</div>
            <div className="win11-card-body">
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.mux")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.mux_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.autoMux} onChange={(_, data) => updateConfig("autoMux", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.clone")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.clone_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.voiceCloning} onChange={(_, data) => updateConfig("voiceCloning", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.demucs")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.demucs_desc")}</div>
                </div>
                <div className="win11-form-control" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <Switch checked={config.audioSeparation} onChange={(_, data) => updateConfig("audioSeparation", data.checked)} />
                  {config.audioSeparation && (
                    <Select value={config.demucsModel} onChange={(e) => updateConfig("demucsModel", e.target.value)}
                      style={{ width: 180 }}>
                      <option value="htdemucs_ft">htdemucs_ft — {t("dubbing.adv.demucs_ft")}</option>
                      <option value="htdemucs">htdemucs — {t("dubbing.adv.demucs_bal")}</option>
                      <option value="htdemucs_6s">htdemucs_6s — {t("dubbing.adv.demucs_6s")}</option>
                    </Select>
                  )}
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.export_srt")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.export_srt_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.exportSrt} onChange={(_, data) => updateConfig("exportSrt", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.keep_temp")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.keep_temp_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.keepIntermediate} onChange={(_, data) => updateConfig("keepIntermediate", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.auto_open")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.auto_open_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.autoOpenFolder} onChange={(_, data) => updateConfig("autoOpenFolder", data.checked)} />
                </div>
              </div>
            </div>
          </div>

          {/* Start Button */}
          <Button appearance="primary" size="large" icon={<Play />}
            style={{ width: "100%", height: 52, fontSize: 16, fontWeight: 600, marginTop: 8 }}
            onClick={handleStart} disabled={!fileName && !youtubeUrl}>
            {t("dubbing.start")}
          </Button>
        </>
      )}

      {/* Running / Done */}
      {(pipelineState === "running" || pipelineState === "done") && (
        <div className="animate-fade-in">
          <PipelineSteps activeStep={activeStep} t={t} />

          {/* Progress Card */}
          <div className="win11-card" style={{ marginBottom: 24 }}>
            <div style={{ padding: 24 }}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium" style={{ color: "var(--colorNeutralForeground2)" }}>
                  {pipelineState === "done" ? t("dubbing.status.done") : `${t("dubbing.status.processing")} ${activeStep}/${PIPELINE_STEPS.length}`}
                </span>
                <span className="font-mono font-semibold" style={{ fontSize: 20, color: "var(--colorBrandForeground1)" }}>{progress}%</span>
              </div>
              <ProgressBar thickness="large" value={progress} max={100} color="brand" />
            </div>
          </div>

          {/* Status + Actions */}
          <div className="flex items-center justify-between mb-4" style={{ minHeight: 32 }}>
            <div>
              {pipelineState === "running" && (
                <span className="text-xs flex items-center gap-2" style={{ color: "var(--colorNeutralForeground3)" }}>
                  <Spinner size="extra-tiny" />
                  {activeStep}/{PIPELINE_STEPS.length} — {t(STEP_T_KEY[PIPELINE_STEPS[Math.max(0, activeStep - 1)] || "source"] as any)}
                </span>
              )}
              {pipelineState === "done" && (
                <Badge appearance="tint" color="success" size="large" icon={<Check style={{ fontSize: 12 }} />}>
                  {t("dubbing.badge.done")}
                </Badge>
              )}
            </div>
            {pipelineState === "running" && (
              <Button appearance="subtle" icon={<Square />}
                style={{ color: "var(--colorPaletteRedForeground1)" }}
                onClick={() => {
                  stopPipeline();
                  handleReset();
                  notifyToast.info(t("toast.pipeline_stopping"), { description: t("toast.pipeline_cancel") });
                }}>
                {t("dubbing.btn.cancel")}
              </Button>
            )}
          </div>

          {/* Log Card */}
          <div className="win11-card" style={{ marginBottom: 24 }}>
            <div className="win11-card-header">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span>{t("dubbing.log.title")}</span>
                  <Badge appearance="outline" size="small" className="font-mono">{logs.length} {t("dubbing.log.entries")}</Badge>
                </div>
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<CopyIcon />}
                  disabled={logs.length === 0}
                  title={t("dubbing.log.copy")}
                  onClick={() => {
                    const text = logs.join("\n");
                    navigator.clipboard.writeText(text).then(() => {
                      notifyToast.success(t("dubbing.log.copied"));
                    }).catch(() => {
                      notifyToast.error(t("dubbing.log.copy_failed"));
                    });
                  }}
                >
                  {t("dubbing.log.copy")}
                </Button>
              </div>
            </div>
            <div className="win11-card-body">
              {logs.length > 0
                ? <VirtualLogViewer logs={logs} maxHeight={480} />
                : <div className="text-xs font-mono opacity-60">[{new Date().toLocaleTimeString()}] {t("dubbing.status.waiting_backend")}</div>}
            </div>
          </div>

          {/* Done actions */}
          {pipelineState === "done" && (
            <div className="flex gap-4 animate-fade-in">
              <Button appearance="primary" size="large" icon={<FolderOpenRegular />} disabled={!outputPath} onClick={async () => {
                if (outputPath) {
                  try {
                    // Open the video file directly
                    await openPath(outputPath);
                  } catch (e) { console.error("Failed to open file:", e); }
                }
              }}>{t("dubbing.btn.open")}</Button>
              <Button appearance="secondary" size="large" onClick={handleReset}>{t("dubbing.btn.new")}</Button>
            </div>
          )}
        </div>
      )}

      {/* Review Mode */}
      {pipelineState === "review" && (
        <div className="animate-fade-in">
          <PipelineSteps activeStep={4} t={t} />

          <div className="flex items-start gap-4" style={{
            padding: 16, borderRadius: 8, marginBottom: 24,
            background: "var(--colorPaletteYellowBackground2)",
            border: "1px solid var(--colorPaletteYellowBorder1)",
          }}>
            <Info style={{ fontSize: 20, flexShrink: 0, color: "var(--colorPaletteYellowForeground1)", marginTop: 2 }} />
            <div>
              <div className="font-semibold text-sm">{t("dubbing.review.title")}</div>
              <div className="text-xs opacity-70 mt-1">{t("dubbing.review.desc")}</div>
            </div>
          </div>

          {/* Row-Based Review Editor using Fluent UI Card + Badge */}
          <Card appearance="filled" style={{ marginBottom: 24 }}>
            <CardHeader
              header={
                <div className="win11-review-header" style={{ display: "flex", gap: 0, fontSize: 12, fontWeight: 600 }}>
                  <span style={{ width: 80, flexShrink: 0 }}>{t("dubbing.review.speaker") || "Speaker"}</span>
                  <span style={{ width: 120, flexShrink: 0 }}>{t("dubbing.review.time") || "Time"}</span>
                  <span style={{ flex: 1 }}>{t("dubbing.review.original")}</span>
                  <span style={{ flex: 1, color: "var(--colorBrandForeground1)" }}>{t("dubbing.review.translated")}</span>
                </div>
              }
            />
            {/* Scrollable rows */}
            <div style={{
              maxHeight: 420, overflowY: "auto", overflowX: "hidden",
              borderTop: "1px solid var(--colorNeutralStroke2)",
            }}>
              {editedSegments.map((seg, i) => {
                return (
                  <div key={i} className="win11-review-row" style={{
                    display: "flex", gap: 0, alignItems: "flex-start",
                    padding: "8px 16px",
                    borderBottom: "1px solid var(--colorNeutralStroke2)",
                    fontSize: 12, lineHeight: 1.55,
                    background: i % 2 === 0 ? "var(--colorNeutralBackground1)" : "var(--colorNeutralBackground2)",
                  }}>
                    {/* Speaker — Fluent UI Badge */}
                    <span className="win11-review-speaker" style={{ width: 80, flexShrink: 0, paddingTop: 1 }}>
                      <Badge
                        appearance="filled"
                        color={SPEAKER_BADGE_COLORS[seg.speaker as string] || SPEAKER_BADGE_COLORS["default"]}
                        size="small"
                      >
                        {seg.speaker || "?"}
                      </Badge>
                    </span>
                    {/* Timestamp */}
                    <span className="win11-review-time" style={{
                      width: 120, flexShrink: 0,
                      fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                      color: "var(--colorNeutralForeground3)", paddingTop: 3,
                    }}>{seg.time || ""}</span>
                    {/* Original text (read-only) */}
                    <span style={{
                      flex: 1, paddingRight: 12, paddingTop: 1,
                      color: "var(--colorNeutralForeground2)", whiteSpace: "pre-wrap",
                    }}>{seg.orig}</span>
                    {/* Editable translation */}
                    <Input
                      value={seg.trans}
                      appearance="underline"
                      onChange={(_, data) => {
                        const updated = [...editedSegments];
                        updated[i] = { ...updated[i], trans: data.value };
                        setEditedSegments(updated);
                      }}
                      style={{
                        flex: 1,
                        fontFamily: "'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif",
                        fontSize: 12,
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Segment count */}
          <div className="text-xs mb-4" style={{ color: "var(--colorNeutralForeground3)" }}>
            {editedSegments.length} {t("dubbing.review.segments") || "segments"} — {t("dubbing.review.edit_hint") || "Click any translation to edit it inline"}
          </div>

          <div className="flex gap-4">
            <Button appearance="primary" size="large" className="flex-1" icon={<FastForward />} onClick={handleContinue}>
              {t("dubbing.btn.continue")}
            </Button>
            <Button appearance="secondary" size="large" onClick={handleReset}>{t("dubbing.btn.cancel")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
