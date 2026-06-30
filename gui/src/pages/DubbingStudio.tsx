import { useState, useCallback, useEffect, type DragEvent } from "react";
import { Button, Select, Input, Switch, ProgressBar, Field, Badge, Card, CardHeader, Radio, RadioGroup, Spinner, Dialog, DialogSurface, DialogTitle, DialogBody, DialogActions, DialogContent, Textarea, Text, Checkbox, Popover, PopoverTrigger, PopoverSurface, Slider, Label, makeStyles, typographyStyles, tokens } from "@fluentui/react-components";
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
  SettingsRegular,
  CloudArrowDownRegular
} from "@fluentui/react-icons";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store";
import { useOllama } from "../hooks/useOllama";
import { usePipelineWebSocket } from "../hooks/usePipelineWebSocket";
import { notifyToast } from "../lib/toast";
import VirtualLogViewer from "../components/VirtualLogViewer";
import TimelineEditor from "../components/TimelineEditor";
import SpeakerManager from "../components/SpeakerManager";


type PipelineState = "idle" | "running" | "review" | "done";
type PipelineMode = "automatic" | "manual";

interface Config {
  targetLanguage: string; voiceModel: string; translationEngine: string;
  translatorModel: string; pipelineMode: PipelineMode;
  autoMux: boolean; voiceCloning: boolean; audioSeparation: boolean;
  exportSrt: boolean; keepIntermediate: boolean; autoOpenFolder: boolean;
  demucsModel: string; useGenderAI: boolean; useYoutubeSubs: boolean; useLipSync: boolean;
  whisperEngine: "whisper" | "whisperX";
  useNlpSplitter: boolean;
}

const PIPELINE_STEPS = ["source", "demucs", "whisper", "translate", "tts", "mux"] as const;
type StepKey = (typeof PIPELINE_STEPS)[number];
const STEP_T_KEY: Record<StepKey, string> = {
  source: "dubbing.step.source", demucs: "dubbing.step.demucs", whisper: "dubbing.step.whisper",
  translate: "dubbing.step.translate", tts: "dubbing.step.tts", mux: "dubbing.step.mux",
};


const ALL_LANGUAGES = [
  { code: "af", name: "Afrikaans" }, { code: "sq", name: "Albanian" }, { code: "am", name: "Amharic" },
  { code: "ar", name: "Arabic" }, { code: "hy", name: "Armenian" }, { code: "az", name: "Azerbaijani" },
  { code: "eu", name: "Basque" }, { code: "be", name: "Belarusian" }, { code: "bn", name: "Bengali" },
  { code: "bs", name: "Bosnian" }, { code: "bg", name: "Bulgarian" }, { code: "ca", name: "Catalan" },
  { code: "ceb", name: "Cebuano" }, { code: "ny", name: "Chichewa" }, { code: "zh-CN", name: "Chinese (Simplified)" },
  { code: "zh-TW", name: "Chinese (Traditional)" }, { code: "co", name: "Corsican" }, { code: "hr", name: "Croatian" },
  { code: "cs", name: "Czech" }, { code: "da", name: "Danish" }, { code: "nl", name: "Dutch" },
  { code: "en", name: "English" }, { code: "eo", name: "Esperanto" }, { code: "et", name: "Estonian" },
  { code: "tl", name: "Filipino" }, { code: "fi", name: "Finnish" }, { code: "fr", name: "French" },
  { code: "fy", name: "Frisian" }, { code: "gl", name: "Galician" }, { code: "ka", name: "Georgian" },
  { code: "de", name: "German" }, { code: "el", name: "Greek" }, { code: "gu", name: "Gujarati" },
  { code: "ht", name: "Haitian Creole" }, { code: "ha", name: "Hausa" }, { code: "haw", name: "Hawaiian" },
  { code: "iw", name: "Hebrew" }, { code: "hi", name: "Hindi" }, { code: "hmn", name: "Hmong" },
  { code: "hu", name: "Hungarian" }, { code: "is", name: "Icelandic" }, { code: "ig", name: "Igbo" },
  { code: "id", name: "Indonesian" }, { code: "ga", name: "Irish" }, { code: "it", name: "Italian" },
  { code: "ja", name: "Japanese" }, { code: "jw", name: "Javanese" }, { code: "kn", name: "Kannada" },
  { code: "kk", name: "Kazakh" }, { code: "km", name: "Khmer" }, { code: "rw", name: "Kinyarwanda" },
  { code: "ko", name: "Korean" }, { code: "ku", name: "Kurdish (Kurmanji)" }, { code: "ky", name: "Kyrgyz" },
  { code: "lo", name: "Lao" }, { code: "la", name: "Latin" }, { code: "lv", name: "Latvian" },
  { code: "lt", name: "Lithuanian" }, { code: "lb", name: "Luxembourgish" }, { code: "mk", name: "Macedonian" },
  { code: "mg", name: "Malagasy" }, { code: "ms", name: "Malay" }, { code: "ml", name: "Malayalam" },
  { code: "mt", name: "Maltese" }, { code: "mi", name: "Maori" }, { code: "mr", name: "Marathi" },
  { code: "mn", name: "Mongolian" }, { code: "my", name: "Myanmar (Burmese)" }, { code: "ne", name: "Nepali" },
  { code: "no", name: "Norwegian" }, { code: "or", name: "Odia (Oriya)" }, { code: "ps", name: "Pashto" },
  { code: "fa", name: "Persian" }, { code: "pl", name: "Polish" }, { code: "pt", name: "Portuguese" },
  { code: "pa", name: "Punjabi" }, { code: "ro", name: "Romanian" }, { code: "ru", name: "Russian" },
  { code: "sm", name: "Samoan" }, { code: "gd", name: "Scots Gaelic" }, { code: "sr", name: "Serbian" },
  { code: "st", name: "Sesotho" }, { code: "sn", name: "Shona" }, { code: "sd", name: "Sindhi" },
  { code: "si", name: "Sinhala" }, { code: "sk", name: "Slovak" }, { code: "sl", name: "Slovenian" },
  { code: "so", name: "Somali" }, { code: "es", name: "Spanish" }, { code: "su", name: "Sundanese" },
  { code: "sw", name: "Swahili" }, { code: "sv", name: "Swedish" }, { code: "tg", name: "Tajik" },
  { code: "ta", name: "Tamil" }, { code: "tt", name: "Tatar" }, { code: "te", name: "Telugu" },
  { code: "th", name: "Thai" }, { code: "tr", name: "Turkish" }, { code: "tk", name: "Turkmen" },
  { code: "uk", name: "Ukrainian" }, { code: "ur", name: "Urdu" }, { code: "ug", name: "Uyghur" },
  { code: "uz", name: "Uzbek" }, { code: "vi", name: "Vietnamese" }, { code: "cy", name: "Welsh" },
  { code: "xh", name: "Xhosa" }, { code: "yi", name: "Yiddish" }, { code: "yo", name: "Yoruba" },
  { code: "zu", name: "Zulu" }
];

const LANGS = ALL_LANGUAGES.map(l => l.code);
const LANG_T_KEY: Record<string, string> = {};
ALL_LANGUAGES.forEach(l => {
  LANG_T_KEY[l.code] = `lang.${l.code}`;
});

const getLanguageDisplayName = (code: string, t: any) => {
  const trans = t(LANG_T_KEY[code] as any);
  if (trans && trans !== LANG_T_KEY[code]) return trans;
  const match = ALL_LANGUAGES.find(l => l.code === code);
  return match ? match.name : code;
};

const TTS_BY_LANG: Record<string, string[]> = {
  // Common TTS voices (xttsv2, azure, edge-tts, openai, gpt-sovits)
  "ru": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "en": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "tr": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "es": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "fr": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "de": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "ar": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "zh": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "ja": ["azure", "edge-tts", "openai", "gpt-sovits"], 
  "ko": ["azure", "edge-tts", "openai", "gpt-sovits"],
  "it": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"], 
  "pt": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"],
  "pl": ["xttsv2", "azure", "edge-tts", "openai", "gpt-sovits"], 
  "hi": ["azure", "edge-tts", "openai", "gpt-sovits"]
};
// Add fallback for all other languages to have basic TTS options if supported globally
ALL_LANGUAGES.forEach(l => {
  if (!TTS_BY_LANG[l.code]) TTS_BY_LANG[l.code] = ["azure", "edge-tts", "openai"];
});

const TTS_T_KEY: Record<string, string> = {
  "xttsv2": "dubbing.voice.xttsv2_full",
  "azure": "dubbing.voice.azure_cloud",
  "edge-tts": "dubbing.voice.edge_cloud",
  "openai": "dubbing.voice.openai_cloud",
  "gpt-sovits": "dubbing.voice.gpt_sovits",
  "none": "dubbing.voice.none" // Subtitles only
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

const usePipelineStyles = makeStyles({
  stepIconDone: {
    fontSize: "14px",
  },
  stepIconActive: {
    width: "16px",
    textAlign: "center",
    ...typographyStyles.caption1,
  }
});

function PipelineSteps({ activeStep, t }: { activeStep: number; t: (k: string) => string }) {
  const s = usePipelineStyles();
  return (
    <div className="win11-steps">
      {PIPELINE_STEPS.map((key, i) => {
        const num = i + 1;
        const state = num < activeStep ? "done" : num === activeStep ? "active" : "";
        return (
          <div key={key} className={`win11-step${state ? ` ${state}` : ""}`}>
            {state === "done" ? <Check className={s.stepIconDone} /> : <span className={s.stepIconActive}>{num}</span>}
            {t(STEP_T_KEY[key] as any)}
          </div>
        );
      })}
    </div>
  );
}

const useStudioStyles = makeStyles({
  card: { marginBottom: "24px", padding: "16px 20px" },
  cardCol: { display: "flex", flexDirection: "column", gap: "16px" },
  cardTitle: { margin: 0, fontSize: "16px", fontWeight: 600 },
  dropzone: {
    padding: "32px 20px",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    border: `2px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: "12px",
    transitionProperty: "all",
    transitionDuration: "0.2s",
  },
  dropzoneIcon: { fontSize: "48px", color: tokens.colorBrandForeground1, opacity: 0.8 },
  dropzoneInputRow: { width: "100%", maxWidth: "600px", display: "flex", gap: "8px" },
  fileSelectedText: { fontSize: "15px", marginTop: "8px" },
  fileSelectedHighlight: { color: tokens.colorBrandForeground1 },
  supportedText: { color: tokens.colorNeutralForeground3 },
  youtubeControls: { display: "flex", flexDirection: "column", gap: "16px", marginTop: "8px" },
  youtubeAuthBtnAuth: { backgroundColor: tokens.colorPaletteGreenBackground2, border: `1px solid ${tokens.colorPaletteGreenBorder1}` },
  youtubeAuthBtnNoAuth: { backgroundColor: tokens.colorPaletteRedBackground2, border: `1px solid ${tokens.colorPaletteRedBorder1}` },
  ytScanCard: { padding: "16px", backgroundColor: tokens.colorNeutralBackground2, borderRadius: "8px", border: `1px solid ${tokens.colorNeutralStroke1}` },
  ytScanTitle: { fontSize: "16px", fontWeight: 600, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" },
  ytScanGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" },
  ytScanListTitle: { fontSize: "14px", fontWeight: 600, marginBottom: "8px", color: tokens.colorNeutralForeground2 },
  ytScanList: { display: "flex", flexDirection: "column", gap: "6px", maxHeight: "150px", overflowY: "auto", paddingRight: "8px" },
  ytScanEmpty: { fontSize: "12px" },
  ytScanCheckbox: { fontSize: "13px" },
  ytScanActions: { display: "flex", gap: "12px", marginTop: "16px", justifyContent: "flex-end", borderTop: `1px solid ${tokens.colorNeutralStroke2}`, paddingTop: "16px" },
  configGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" },
  fieldInput: { padding: "8px 0" },
  flexRowGap8: { display: "flex", gap: "8px" },
  flex1: { flexGrow: 1 },
  modeDesc: { color: tokens.colorNeutralForeground3, lineHeight: 1.4 },
  advSelect: { width: "180px" },
  advFormRowStart: { alignItems: "flex-start" },
  advLabelMargin: { marginTop: "4px" },
  advTextarea: { width: "250px", minHeight: "80px" },
  advColGap8: { display: "flex", flexDirection: "column", gap: "8px" },
  startBtn: { width: "100%", height: "52px", fontSize: "16px", fontWeight: 600, marginTop: "8px" },
  progressCard: { marginBottom: "24px" },
  progressInner: { padding: "24px" },
  progressStatus: { color: tokens.colorNeutralForeground2 },
  progressPercent: { fontSize: "20px", color: tokens.colorBrandForeground1 },
  statusActions: { minHeight: "32px" },
  runningStatus: { color: tokens.colorNeutralForeground3 },
  stopBtn: { color: tokens.colorPaletteRedForeground1 },
  dialogContent: { display: "flex", flexDirection: "column", gap: "16px", paddingTop: "16px" },
  infoBox: { padding: "16px", borderRadius: "8px", marginBottom: "24px", backgroundColor: tokens.colorPaletteYellowBackground2, border: `1px solid ${tokens.colorPaletteYellowBorder1}` },
  infoIcon: { fontSize: "20px", flexShrink: 0, color: tokens.colorPaletteYellowForeground1, marginTop: "2px" },
  reviewContainer: { display: "flex", gap: "16px", alignItems: "flex-start", marginBottom: "24px" },
  reviewCard: { flexGrow: 1, minWidth: 0 },
  reviewHeader: { display: "flex", gap: 0, fontSize: "12px", fontWeight: 600 },
  reviewHeaderCellSpeaker: { width: "80px", flexShrink: 0 },
  reviewHeaderCellTime: { width: "120px", flexShrink: 0 },
  reviewHeaderCellTrans: { flexGrow: 1, color: tokens.colorBrandForeground1 },
  reviewListContainer: { maxHeight: "420px", overflowY: "auto", overflowX: "hidden", borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  reviewRow: { display: "flex", gap: 0, alignItems: "flex-start", padding: "8px 16px", borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, fontSize: "12px", lineHeight: 1.55 },
  reviewRowEven: { backgroundColor: tokens.colorNeutralBackground1 },
  reviewRowOdd: { backgroundColor: tokens.colorNeutralBackground2 },
  reviewCellSpeaker: { width: "80px", flexShrink: 0, paddingTop: "1px" },
  reviewCellTime: { width: "120px", flexShrink: 0, fontFamily: "monospace", fontSize: "11px", color: tokens.colorNeutralForeground3, paddingTop: "3px" },
  reviewCellOrig: { flexGrow: 1, paddingRight: "12px", paddingTop: "1px", color: tokens.colorNeutralForeground2, whiteSpace: "pre-wrap", flexBasis: "0%" },
  reviewCellTransBox: { flexGrow: 1, display: "flex", gap: "8px", alignItems: "center", flexBasis: "0%" },
  reviewInput: { flexGrow: 1, fontSize: "12px", fontFamily: "'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif" },
  popoverSurface: { minWidth: "200px", padding: "12px", display: "flex", flexDirection: "column", gap: "12px" },
  popoverRow: { display: "flex", justifyContent: "space-between", marginBottom: "4px" },
  popoverLabelMono: { fontFamily: "monospace" },
  segmentCount: { color: tokens.colorNeutralForeground3 },
});

export default function DubbingStudio() {
  const styles = useStudioStyles();
  const { t, settings, lang, apiKeys, setApiKeys, userGlossary, setUserGlossary } = useSettings();
  const [pipelineState, setPipelineState] = useState<PipelineState>("idle");
  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [editedSegments, setEditedSegments] = useState<any[]>([]);

  const handleRenameSpeaker = useCallback((oldSpeakerId: string, newSpeakerId: string) => {
    setEditedSegments(prev => prev.map(seg => 
      seg.speaker === oldSpeakerId ? { ...seg, speaker: newSpeakerId } : seg
    ));
  }, []);

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
    autoMux: true, voiceCloning: false, audioSeparation: false,
    exportSrt: true, keepIntermediate: false, autoOpenFolder: true,
    demucsModel: "htdemucs_ft", useGenderAI: true, useYoutubeSubs: true, useLipSync: true,
    whisperEngine: "whisperX", useNlpSplitter: true,
  });
  const [showConfigModal, setShowConfigModal] = useState<string | null>(null);
  const [tempKey, setTempKey] = useState<string>("");


  useEffect(() => { checkConnection(); }, [checkConnection]);

  useEffect(() => {
    const valid = TTS_BY_LANG[config.targetLanguage] || [];
    if (!valid.includes(config.voiceModel) && valid.length > 0) updateConfig("voiceModel", valid[0]);
  }, [config.targetLanguage, config.voiceModel]);

  const [ytScanResult, setYtScanResult] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [selectedYtSubs, setSelectedYtSubs] = useState<string[]>([]);
  const [selectedYtAudios, setSelectedYtAudios] = useState<string[]>([]);
  const [isDownloadingYt, setIsDownloadingYt] = useState(false);
  const [hasCookies, setHasCookies] = useState(false);

  const [playingSegment, setPlayingSegment] = useState<number | null>(null);

  const handlePreviewTTS = async (index: number, text: string, speaker: string, speed: number = 1.0, pitch: number = 0) => {
    if (playingSegment !== null) return;
    setPlayingSegment(index);
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/preview_tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language: config.targetLanguage,
          tts_engine: config.voiceModel,
          speaker: speaker || "SPEAKER_00",
          speed,
          pitch,
        })
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to generate preview");
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setPlayingSegment(null);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setPlayingSegment(null);
      };
      audio.play().catch(e => {
        notifyToast.error("Playback Error", { description: e.message });
        setPlayingSegment(null);
      });
    } catch (e: any) {
      notifyToast.error("TTS Error", { description: e.message || String(e) });
      setPlayingSegment(null);
    }
  };

  const checkCookies = useCallback(async () => {
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/youtube/has_cookies");
      if (resp.ok) {
        const data = await resp.json();
        setHasCookies(data.has_cookies);
      }
    } catch (e) {}
  }, []);

  useEffect(() => { checkCookies(); }, [checkCookies]);
  
  useEffect(() => {
    if (hasCookies) return;
    const interval = setInterval(checkCookies, 2000);
    return () => clearInterval(interval);
  }, [hasCookies, checkCookies]);

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
    if (e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0] as any;
      setFileName(file.path || file.name);
    }
  }, []);

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setYoutubeUrl(text);
    } catch {
      notifyToast.error("Clipboard access denied", { description: "Please paste the URL manually or grant clipboard permission." });
    }
  }, []);

  const handleScanYoutube = async () => {
    if (!youtubeUrl) return;
    setIsScanning(true);
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/youtube/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: youtubeUrl })
      });
      if (resp.ok) {
        const data = await resp.json();
        setYtScanResult(data);
        setSelectedYtSubs([]);
        setSelectedYtAudios([]);
      } else {
        notifyToast.error("Scan Failed");
      }
    } catch (e) {
      notifyToast.error("Failed to connect to backend");
    } finally {
      setIsScanning(false);
    }
  };

  const handleDownloadYoutube = async (mux: boolean) => {
    if (!youtubeUrl) return;
    setIsDownloadingYt(true);
    notifyToast.success("Starting download...");
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/youtube/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: youtubeUrl,
          subtitle_langs: selectedYtSubs,
          audio_format_ids: selectedYtAudios,
          mux: mux
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        notifyToast.success("Download complete!", { description: `Saved to: ${data.folder}` });
      } else {
        const err = await resp.json();
        notifyToast.error("Download Failed", { description: err.detail });
      }
    } catch (e) {
      notifyToast.error("Backend Error");
    } finally {
      setIsDownloadingYt(false);
    }
  };

  const handleStart = useCallback(async () => {
    if (!fileName && !youtubeUrl) return;
    if (!isConnected) {
      try {
        const state = await invoke<string>("get_backend_state");
        if (state.includes("Installing") || state.includes("Downloading")) {
          notifyToast.error(t("toast.backend_error"), { description: "Installing AI dependencies. Please wait." });
          return;
        }
      } catch {
        console.warn("[DubbingStudio] Could not query backend state — assuming offline");
      }
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
      whisper_engine: config.whisperEngine,
      device: "cuda", translation_engine: config.translationEngine, dub_engine: config.voiceModel,
      gemini_key: settings.geminiKey, deepseek_key: settings.deepseekKey, deepl_key: settings.deeplKey,
      hf_key: settings.hfKey,
      manual_mode: config.pipelineMode === "manual",
      ui_language: lang || "ru",
      demucs_model: config.demucsModel,
      use_gender_ai: config.useGenderAI,
      use_youtube_subs: config.useYoutubeSubs,
      translator_model: config.translatorModel,
      lip_sync: config.useLipSync,
      use_nlp_splitter: config.useNlpSplitter,
      user_glossary: userGlossary,
    });
  }, [fileName, youtubeUrl, config, startPipeline, settings, isConnected, t, onLog, lang, userGlossary]);

  const handleContinue = useCallback(() => {
    setPipelineState("running"); setActiveStep(5); setProgress(67);
    resumePipeline(editedSegments);
  }, [resumePipeline, editedSegments]);

  const handleReset = useCallback(() => {
    setPipelineState("idle"); setActiveStep(0); setProgress(0); setFileName(""); setYoutubeUrl("");
    setLogs([]); setEditedSegments([]); setOutputPath(""); setYtScanResult(null);
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
          {/* Source Selection Card (Unified) */}
          <Card className={`win11-card ${styles.card}`}>
            <div className={styles.cardCol}>
              <h3 className={styles.cardTitle}>{t("dubbing.source.title") || "Select Video Source"}</h3>
              
              {/* Unified Drop/Input Zone */}
              <div 
                className={`win11-dropzone flex-col gap-4 ${styles.dropzone} ${isDragging ? " drag-over" : ""}`}
                onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
              >
                <CloudArrowDownRegular className={styles.dropzoneIcon} />
                
                <div className={styles.dropzoneInputRow}>
                  <Input 
                    className="flex-1" 
                    placeholder={t("dubbing.youtube_placeholder") || "Paste YouTube/Web URL or Click Browse..."} 
                    value={youtubeUrl}
                    onChange={(e) => { setYoutubeUrl(e.target.value); setFileName(""); setYtScanResult(null); }} 
                    size="large" 
                  />
                  <Button onClick={handleSelectFile} size="large" icon={<FolderOpenRegular />}>{t("settings.browse") || "Browse"}</Button>
                  <Button icon={<Clipboard />} onClick={handlePaste} size="large" title={t("dubbing.btn.paste_title") as string} />
                </div>
                
                <div className={`font-semibold ${styles.fileSelectedText}`}>
                  {fileName ? <>{t("dubbing.file.selected")} <span className={styles.fileSelectedHighlight}>{fileName}</span></> : t("dubbing.dropzone") || "Drag & Drop video/audio here"}
                </div>
                <span className={`text-xs ${styles.supportedText}`}>{t("dubbing.supported")}</span>
              </div>

              {/* YouTube specific controls (appear only if URL is pasted) */}
              {youtubeUrl && !fileName && (
                <div className={`animate-fade-in ${styles.youtubeControls}`}>
                  <div className="flex gap-3 items-center">
                    <Button onClick={handleScanYoutube} disabled={isScanning} appearance="primary">
                      {isScanning ? t("dubbing.yt.scanning") : t("dubbing.yt.scan")}
                    </Button>
                    <Button onClick={async () => {
                      try {
                        const resp = await fetch("http://127.0.0.1:8000/api/youtube/login", { method: "POST" });
                        const data = await resp.json();
                        notifyToast.success("Browser opened", { description: data.message });
                      } catch (e) { notifyToast.error("Failed to open browser"); }
                    }} size="small" className={hasCookies ? styles.youtubeAuthBtnAuth : styles.youtubeAuthBtnNoAuth}>
                      {hasCookies ? t("dubbing.yt.auth_btn_done") : t("dubbing.yt.auth_btn")}
                    </Button>
                  </div>

                  {ytScanResult && (
                    <div className={styles.ytScanCard}>
                      <h3 className={styles.ytScanTitle}>
                        <Film /> {ytScanResult.title}
                      </h3>
                      <div className={styles.ytScanGrid}>
                        <div>
                          <h4 className={styles.ytScanListTitle}>{t("dubbing.yt.subs")}</h4>
                          <div className={styles.ytScanList}>
                            {ytScanResult.subtitles.length === 0 ? <span className={styles.ytScanEmpty}>{t("dubbing.yt.none")}</span> : ytScanResult.subtitles.map((sub: any) => (
                              <Checkbox key={sub.lang} label={sub.name} className={styles.ytScanCheckbox}
                                checked={selectedYtSubs.includes(sub.lang)}
                                onChange={(_, data) => setSelectedYtSubs(prev => data.checked ? [...prev, sub.lang] : prev.filter(l => l !== sub.lang))} />
                            ))}
                          </div>
                        </div>
                        <div>
                          <h4 className={styles.ytScanListTitle}>{t("dubbing.yt.audio")}</h4>
                          <div className={styles.ytScanList}>
                            {ytScanResult.audio_tracks.length === 0 ? <span className={styles.ytScanEmpty}>{t("dubbing.yt.none")}</span> : ytScanResult.audio_tracks.map((trk: any) => (
                              <Checkbox key={trk.format_id} label={trk.name} className={styles.ytScanCheckbox}
                                checked={selectedYtAudios.includes(trk.format_id)}
                                onChange={(_, data) => setSelectedYtAudios(prev => data.checked ? [...prev, trk.format_id] : prev.filter(l => l !== trk.format_id))} />
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className={styles.ytScanActions}>
                        <Button disabled={isDownloadingYt || (selectedYtSubs.length === 0 && selectedYtAudios.length === 0)}
                          onClick={() => handleDownloadYoutube(false)}>
                          {isDownloadingYt ? t("dubbing.yt.downloading") : t("dubbing.yt.download_only")}
                        </Button>
                        <Button appearance="primary" disabled={isDownloadingYt || (selectedYtSubs.length === 0 && selectedYtAudios.length === 0)}
                          onClick={() => handleDownloadYoutube(true)}>
                          {isDownloadingYt ? t("dubbing.yt.downloading") : t("dubbing.yt.download_mux")}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Configuration Card */}
          <Card className="win11-card">
            <CardHeader header={<Text weight="semibold">{t("dubbing.config")}</Text>} />
            <div className="win11-card-body">
              <div className={`win11-config-grid ${styles.configGrid}`}>
                <Field label={t("dubbing.target_lang")} className={styles.fieldInput}>
                  <Select value={config.targetLanguage} onChange={(e) => updateConfig("targetLanguage", e.target.value)} size="large">
                    {LANGS.map(c => (<option key={c} value={c}>{getLanguageDisplayName(c, t)}</option>))}
                  </Select>
                </Field>
                <Field label={t("dubbing.voice_model")} className={styles.fieldInput}>
                  <div className={styles.flexRowGap8}>
                    <Select value={config.voiceModel} onChange={(e) => { 
                      updateConfig("voiceModel", e.target.value); 
                      if (["openai", "azure"].includes(e.target.value) && !apiKeys[e.target.value]) {
                        setTempKey("");
                        setShowConfigModal(e.target.value);
                      }
                    }} size="large" className={styles.flex1}>
                      <option value="none">{t("dubbing.voice.none") || "Subtitles Only (No TTS)"}</option>
                      {(TTS_BY_LANG[config.targetLanguage] || []).map(k => (<option key={k} value={k}>{t(TTS_T_KEY[k] as any) || k}</option>))}
                    </Select>
                    {["openai", "azure", "deepseek", "gemini", "deepl"].some(v => config.voiceModel === v || config.translationEngine === v) && (
                      <Button icon={<SettingsRegular />} size="large" onClick={() => { setTempKey(""); setShowConfigModal(config.translationEngine === "deepseek" ? "deepseek" : config.voiceModel); }} title="API Settings" />
                    )}
                  </div>
                </Field>
                <Field label={t("dubbing.translation_engine")} className={styles.fieldInput}>
                  <div className={styles.flexRowGap8}>
                    <Select value={config.translationEngine} onChange={(e) => { 
                      updateConfig("translationEngine", e.target.value); 
                      if (["openai", "azure", "deepseek", "gemini", "deepl"].includes(e.target.value) && !apiKeys[e.target.value]) {
                        setTempKey("");
                        setShowConfigModal(e.target.value);
                      }
                    }} size="large" className={styles.flex1}>
                      <option value="deepseek">{t("dubbing.engine.deepseek")}</option>
                      <option value="openai">OpenAI API</option>
                      <option value="gemini">{t("dubbing.engine.gemini")}</option>
                      <option value="deepl">{t("dubbing.engine.deepl")}</option>
                      <option value="ollama">{t("dubbing.engine.ollama")}</option>
                      <option value="google">{t("dubbing.engine.google")}</option>
                    </Select>
                  </div>
                </Field>
                <Field label={t("dubbing.translator_model")} className={styles.fieldInput}>
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
          </Card>

          {/* Pipeline Mode Card */}
          <Card className="win11-card">
            <CardHeader header={<Text weight="semibold">{t("dubbing.mode")}</Text>} />
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
                    className={styles.flex1}
                  />
                ))}
              </RadioGroup>
              <div className={`text-xs mt-3 ${styles.modeDesc}`}>
                {t(`dubbing.mode.${config.pipelineMode === "automatic" ? "auto" : "manual"}_desc` as any)}
              </div>
            </div>
          </Card>

          {/* Advanced Settings Card */}
          <Card className="win11-card">
            <CardHeader header={<Text weight="semibold">{t("dubbing.advanced")}</Text>} />
            <div className="win11-card-body">
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.whisper_engine") || "Whisper Engine"}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.whisper_desc") || "Select the speech recognition backend"}</div>
                </div>
                <div className="win11-form-control">
                  <Select value={config.whisperEngine} onChange={(e) => updateConfig("whisperEngine", e.target.value as any)} className={styles.advSelect}>
                    <option value="whisper">{t("dubbing.adv.whisper_std") || "Whisper (Standard)"}</option>
                    <option value="whisperX">{t("dubbing.adv.whisperx") || "WhisperX (Faster, Better Align)"}</option>
                  </Select>
                </div>
              </div>
              <div className={`win11-form-row ${styles.advFormRowStart}`}>
                <div className={`win11-form-label ${styles.advLabelMargin}`}>
                  <div className="win11-form-label-text">{t("dubbing.adv.user_glossary") || "User Glossary"}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.user_glossary_desc") || "Specify terms, names, or brand rules for the LLM to follow during translation."}</div>
                </div>
                <div className="win11-form-control">
                  <Textarea 
                    value={userGlossary} 
                    onChange={(_, data) => setUserGlossary(data.value || "")} 
                    placeholder={t("dubbing.glossary.placeholder") || "e.g. Teknorob = Teknorob (do not translate)\nJohn = Джонатан"}
                    resize="vertical"
                    className={styles.advTextarea}
                  />
                </div>
              </div>
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
                  <div className="win11-form-label-text">{t("dubbing.adv.gender_ai")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.gender_ai_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.useGenderAI} onChange={(_, data) => updateConfig("useGenderAI", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.yt_subs")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.yt_subs_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.useYoutubeSubs} onChange={(_, data) => updateConfig("useYoutubeSubs", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.nlp_spacy_title") || "Smart NLP Splitter (Spacy)"}</div>
                  <div className="win11-form-label-desc">{t("dubbing.nlp_spacy_desc") || "Perfect slicing by meaning and punctuation, instead of breaking mid-word."}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.useNlpSplitter} onChange={(_, data) => updateConfig("useNlpSplitter", data.checked)} />
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.demucs")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.demucs_desc")}</div>
                </div>
                <div className={`win11-form-control ${styles.advColGap8}`}>
                  <Switch checked={config.audioSeparation} onChange={(_, data) => updateConfig("audioSeparation", data.checked)} />
                  {config.audioSeparation && (
                    <Select value={config.demucsModel} onChange={(e) => updateConfig("demucsModel", e.target.value)}
                      className={styles.advSelect}>
                      <option value="htdemucs_ft">htdemucs_ft — {t("dubbing.adv.demucs_ft")}</option>
                      <option value="htdemucs">htdemucs — {t("dubbing.adv.demucs_bal")}</option>
                      <option value="htdemucs_6s">htdemucs_6s — {t("dubbing.adv.demucs_6s")}</option>
                    </Select>
                  )}
                </div>
              </div>
              <div className="win11-form-row">
                <div className="win11-form-label">
                  <div className="win11-form-label-text">{t("dubbing.adv.lip_sync")}</div>
                  <div className="win11-form-label-desc">{t("dubbing.adv.lip_sync_desc")}</div>
                </div>
                <div className="win11-form-control">
                  <Switch checked={config.useLipSync} onChange={(_, data) => updateConfig("useLipSync", data.checked)} />
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
          </Card>

          {/* Start Button */}
          <Button appearance="primary" size="large" icon={<Play />}
            className={styles.startBtn}
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
          <Card className={`win11-card ${styles.progressCard}`}>
            <div className={styles.progressInner}>
              <div className="flex items-center justify-between mb-3">
                <span className={`text-sm font-medium ${styles.progressStatus}`}>
                  {pipelineState === "done" ? t("dubbing.status.done") : `${t("dubbing.status.processing")} ${activeStep}/${PIPELINE_STEPS.length}`}
                </span>
                <span className={`font-mono font-semibold ${styles.progressPercent}`}>{progress}%</span>
              </div>
              <ProgressBar thickness="large" value={progress} max={100} color="brand" />
            </div>
          </Card>

          {/* Status + Actions */}
          <div className={`flex items-center justify-between mb-4 ${styles.statusActions}`}>
            <div>
              {pipelineState === "running" && (
                <span className={`text-xs flex items-center gap-2 ${styles.runningStatus}`}>
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
                className={styles.stopBtn}
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
          <Card className="win11-card" style={{ marginBottom: 24 }}>
            <div className="win11-card-header">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Text weight="semibold">{t("dubbing.log.title")}</Text>
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
          </Card>

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

      {/* Modals for API Keys */}
      <Dialog open={showConfigModal !== null} onOpenChange={(_, data) => { if (!data.open) setShowConfigModal(null); }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>{t("settings.keys") || "API Keys Configuration"}</DialogTitle>
            <DialogContent className={styles.dialogContent}>
              <div className="text-sm opacity-80 mb-2">
                {t("dubbing.api_key_required_prefix") || "Provider"} <b>{showConfigModal}</b> {t("dubbing.api_key_required_suffix") || "requires an API key."}
              </div>
              <Input
                value={tempKey}
                onChange={(_, d) => setTempKey(d.value)}
                placeholder={`Enter your ${showConfigModal} API key...`}
                type="password"
              />
              <div className="text-xs opacity-60">
                {t("settings.keys.notice") || "It will be securely stored in your settings."}
              </div>
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setShowConfigModal(null)}>{t("dubbing.btn.cancel")}</Button>
              <Button appearance="primary" onClick={() => {
                if (showConfigModal && tempKey) {
                  setApiKeys({ ...apiKeys, [showConfigModal]: tempKey });
                }
                setShowConfigModal(null);
              }}>
                {t("dubbing.btn.save") || "Save"}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
      
      {/* Review Mode */}
      {pipelineState === "review" && (
        <div className="animate-fade-in">
          <PipelineSteps activeStep={4} t={t} />

          <div className={`flex items-start gap-4 ${styles.infoBox}`}>
            <Info className={styles.infoIcon} />
            <div>
              <div className="font-semibold text-sm">{t("dubbing.review.title")}</div>
              <div className="text-xs opacity-70 mt-1">{t("dubbing.review.desc")}</div>
            </div>
          </div>

          <TimelineEditor 
            mediaPath={fileName} 
            segments={editedSegments} 
            onSegmentsChange={setEditedSegments}
            playingSegmentIndex={playingSegment}
          />

          <div className={styles.reviewContainer}>
            <SpeakerManager segments={editedSegments} onRenameSpeaker={handleRenameSpeaker} />
            {/* Row-Based Review Editor using Fluent UI Card + Badge */}
            <Card appearance="filled" className={styles.reviewCard}>
              <CardHeader
              header={
                <div className={`win11-review-header ${styles.reviewHeader}`}>
                  <span className={styles.reviewHeaderCellSpeaker}>{t("dubbing.review.speaker") || "Speaker"}</span>
                  <span className={styles.reviewHeaderCellTime}>{t("dubbing.review.time") || "Time"}</span>
                  <span className={styles.flex1}>{t("dubbing.review.original")}</span>
                  <span className={styles.reviewHeaderCellTrans}>{t("dubbing.review.translated")}</span>
                </div>
              }
            />
            {/* Scrollable rows */}
            <div className={styles.reviewListContainer}>
              {editedSegments.map((seg, i) => {
                return (
                  <div key={i} className={`win11-review-row ${styles.reviewRow} ${i % 2 === 0 ? styles.reviewRowEven : styles.reviewRowOdd}`}>
                    {/* Speaker — Fluent UI Badge */}
                    <span className={`win11-review-speaker ${styles.reviewCellSpeaker}`}>
                      <Badge
                        appearance="filled"
                        color={SPEAKER_BADGE_COLORS[seg.speaker as string] || SPEAKER_BADGE_COLORS["default"]}
                        size="small"
                      >
                        {seg.speaker || "?"}
                      </Badge>
                    </span>
                    {/* Timestamp */}
                    <span className={`win11-review-time ${styles.reviewCellTime}`}>{seg.time || ""}</span>
                    {/* Original text (read-only) */}
                    <span className={styles.reviewCellOrig}>{seg.orig}</span>
                    {/* Editable translation */}
                    <div className={styles.reviewCellTransBox}>
                      <Input
                        value={seg.trans}
                        appearance="underline"
                        onChange={(_, data) => {
                          const updated = [...editedSegments];
                          updated[i] = { ...updated[i], trans: data.value };
                          setEditedSegments(updated);
                        }}
                        className={styles.reviewInput}
                      />
                      <Button
                        appearance="transparent"
                        icon={playingSegment === i ? <Spinner size="tiny" /> : <Play />}
                        onClick={() => handlePreviewTTS(i, seg.trans, seg.speaker as string, seg.speed ?? 1.0, seg.pitch ?? 0)}
                        title={t("dubbing.review.preview_tts") || "Live Preview"}
                        disabled={playingSegment !== null}
                      />
                      <Popover withArrow positioning="below-end">
                        <PopoverTrigger disableButtonEnhancement>
                          <Button appearance="transparent" icon={<SettingsRegular />} title="Voice Tweaks" />
                        </PopoverTrigger>
                        <PopoverSurface className={styles.popoverSurface}>
                          <div>
                            <div className={styles.popoverRow}>
                              <Label size="small">Speed</Label>
                              <Label size="small" className={styles.popoverLabelMono}>{(seg.speed ?? 1.0).toFixed(1)}x</Label>
                            </div>
                            <Slider
                              min={0.5} max={2.0} step={0.1}
                              value={seg.speed ?? 1.0}
                              onChange={(_, data) => {
                                const updated = [...editedSegments];
                                updated[i] = { ...updated[i], speed: data.value };
                                setEditedSegments(updated);
                              }}
                            />
                          </div>
                          <div>
                            <div className={styles.popoverRow}>
                              <Label size="small">Pitch</Label>
                              <Label size="small" className={styles.popoverLabelMono}>{(seg.pitch ?? 0) > 0 ? "+" : ""}{seg.pitch ?? 0}</Label>
                            </div>
                            <Slider
                              min={-50} max={50} step={1}
                              value={seg.pitch ?? 0}
                              onChange={(_, data) => {
                                const updated = [...editedSegments];
                                updated[i] = { ...updated[i], pitch: data.value };
                                setEditedSegments(updated);
                              }}
                            />
                          </div>
                        </PopoverSurface>
                      </Popover>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
          </div>

          {/* Segment count */}
          <div className={`text-xs mb-4 ${styles.segmentCount}`}>
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
