import { useState, type ChangeEvent } from "react";
import { Button, Select, Field, Badge } from "@fluentui/react-components";
import {
  InfoRegular as Info, MicRegular as Mic,
  Speaker0Regular as AudioLines, ClosedCaptionRegular as Captions,
  SquareRegular as Square, PlayRegular as Play,
} from "@fluentui/react-icons";
import { useSettings } from "../store";
import { useLiveWebSocket } from "../hooks/useLiveWebSocket";

interface SubtitleConfig {
  translationEngine: string; sourceLanguage: string; targetLanguage: string;
  subtitlePosition: string; fontSize: string;
}

export default function LiveSubtitles() {
  const { t } = useSettings();
  const [state, setState] = useState<"idle" | "listening">("idle");
  const { isConnected, isCapturing, subtitleText, startCapture, stopCapture } = useLiveWebSocket();
  const [config, setConfig] = useState<SubtitleConfig>({
    translationEngine: "deepseek", sourceLanguage: "auto", targetLanguage: "ru",
    subtitlePosition: "bottom", fontSize: "medium",
  });

  const updateConfig = <K extends keyof SubtitleConfig>(key: K, value: SubtitleConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleToggle = () => {
    if (state === "idle") { setState("listening"); startCapture(config); }
    else { setState("idle"); stopCapture(); }
  };

  const statusBadge = isCapturing ? { color: "success" as const, label: t("live.listening") }
    : isConnected ? { color: "brand" as const, label: t("live.standby") }
    : { color: "subtle" as const, label: t("status.ollama_off") };

  return (
    <div className="win11-page">
      <h1 className="win11-page-title">{t("live.title")}</h1>
      <p className="win11-page-subtitle">{t("live.subtitle")}</p>

      {/* Info Banner */}
      <div className="flex gap-3 p-4 rounded-lg mb-4" style={{ background: "var(--colorNeutralBackground2)", border: "1px solid var(--colorNeutralStroke2)" }}>
        <Info style={{ fontSize: 18, flexShrink: 0, color: "var(--colorNeutralForeground3)" }} />
        <span className="text-sm" style={{ color: "var(--colorNeutralForeground2)" }}>{t("live.callout")}</span>
      </div>

      {/* Configuration Card */}
      <div className="win11-card">
        <div className="win11-card-header">{t("live.config")}</div>
        <div className="win11-card-body">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            <Field label={t("live.engine_label")} style={{ gridColumn: "1 / -1", padding: "8px 0" }}>
              <Select value={config.translationEngine} onChange={(e: ChangeEvent<HTMLSelectElement>) => updateConfig("translationEngine", e.target.value)}>
                <option value="deepseek">{t("live.engine.deepseek")}</option>
                <option value="whisper-local">{t("live.engine.whisper_local")}</option>
              </Select>
            </Field>
            {[
              { id: "sourceLanguage", label: t("live.source_lang"), opts: [{ v: "auto", l: t("live.auto") }, { v: "en", l: t("lang.en") }, { v: "tr", l: t("lang.tr") }, { v: "ar", l: t("lang.ar") }, { v: "ru", l: t("lang.ru") }] },
              { id: "targetLanguage", label: t("live.target_lang"), opts: [{ v: "ru", l: t("lang.ru") }, { v: "tr", l: t("lang.tr") }, { v: "en", l: t("lang.en") }] },
              { id: "subtitlePosition", label: t("live.position"), opts: [{ v: "bottom", l: t("pos.bottom") }, { v: "top", l: t("pos.top") }, { v: "center", l: t("pos.center") }] },
              { id: "fontSize", label: t("live.fontsize"), opts: [{ v: "small", l: t("size.small") }, { v: "medium", l: t("size.medium") }, { v: "large", l: t("size.large") }] },
            ].map(({ id, label, opts }) => (
              <Field key={id} label={label} style={{ padding: "8px 0" }}>
                <Select value={config[id as keyof SubtitleConfig]} onChange={(e) => updateConfig(id as keyof SubtitleConfig, e.target.value)}>
                  {opts.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
                </Select>
              </Field>
            ))}
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div style={{ marginBottom: 24 }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold" style={{ fontSize: 16 }}>{t("live.audio_status")}</h2>
          <Badge appearance="tint" color={statusBadge.color} size="small">{statusBadge.label}</Badge>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          {[
            { icon: <Mic style={{ fontSize: 18 }} />, title: t("live.status_audio"), desc: isCapturing ? t("live.status_audio.active") : t("live.status_audio.idle") },
            { icon: <AudioLines style={{ fontSize: 18 }} />, title: t("live.status_engine"), desc: isCapturing ? t("live.status_engine.active") : t("live.status_engine.idle") },
            { icon: <Captions style={{ fontSize: 18 }} />, title: t("live.status_overlay"), desc: isCapturing ? t("live.status_overlay.active") : t("live.status_overlay.idle") },
          ].map((card, i) => (
            <div key={i} style={{
              padding: 20, textAlign: "center", borderRadius: 8,
              background: "var(--colorNeutralBackground2)", border: "1px solid var(--colorNeutralStroke2)",
            }}>
              <div className="flex items-center gap-2 justify-center mb-3">
                <span className="status-dot" style={{ background: isCapturing ? "var(--colorPaletteGreenForeground1)" : "var(--colorNeutralForeground3)", animation: isCapturing ? "pulse 2s ease-in-out infinite" : "none" }} />
                <span style={{ color: "var(--colorNeutralForeground3)" }}>{card.icon}</span>
              </div>
              <div className="text-sm font-semibold">{card.title}</div>
              <div className="text-xs mt-1" style={{ color: "var(--colorNeutralForeground3)" }}>{card.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Live Preview */}
      {isCapturing && (
        <div style={{
          padding: 20, marginBottom: 24, borderRadius: 8,
          background: "var(--colorNeutralBackground3)", border: "1px solid var(--colorNeutralStroke2)",
        }}>
          <div className="flex items-center justify-between mb-3 opacity-60">
            <span className="text-xs font-bold" style={{ textTransform: "uppercase", letterSpacing: "0.05em" }}>{t("live.preview")}</span>
            <div className="flex items-center gap-2">
              <span className="status-dot" style={{ background: "var(--colorPaletteGreenForeground1)", animation: "pulse 2s ease-in-out infinite" }} />
              <span className="text-xs">{t("live.recording")}</span>
            </div>
          </div>
          <div className="font-mono text-sm text-center" style={{ minHeight: "3em" }}>
            {subtitleText || <span className="opacity-30" style={{ fontStyle: "italic" }}>{t("live.waiting_audio")}</span>}
          </div>
        </div>
      )}

      <Button appearance="primary" size="large" icon={isCapturing ? <Square /> : <Play />}
        style={{ width: "100%", height: 52, fontSize: 16, fontWeight: 600,
          background: isCapturing ? "var(--colorPaletteRedBackground3)" : undefined,
          color: isCapturing ? "var(--colorPaletteRedForeground1)" : undefined }}
        onClick={handleToggle}>
        {isCapturing ? t("live.stop") : t("live.start")}
      </Button>
    </div>
  );
}
