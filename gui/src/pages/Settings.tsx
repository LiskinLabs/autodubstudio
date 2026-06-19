import React, { useState, useEffect, useRef, useCallback } from "react";
import { Button, Select, Input, Switch, Badge, Dialog, DialogSurface, DialogBody, DialogTitle, DialogActions } from "@fluentui/react-components";
import {
  InfoRegular as Info, ArrowDownloadRegular as Download, DeleteRegular as Trash,
  DismissRegular as X, CheckmarkRegular as Check, SpinnerIosRegular as LoaderCircle,
  OpenRegular as ExternalLink, PersonRegular as User, GlobeRegular as Globe,
} from "@fluentui/react-icons";
import { useSettings, Language } from "../store";
import { open } from "@tauri-apps/plugin-dialog";
import { fetch } from "@tauri-apps/plugin-http";
import { notifyToast } from "../lib/toast";
import { useModelStatus, ALL_MODELS } from "../hooks/useModelStatus";
import { THEME_OPTIONS } from "../theme";

type SettingsTab = "general" | "models" | "keys" | "about";

interface ApiKeys {
  deepseek: string; openai: string; azure: string; google: string;
  gemini: string; huggingface: string; deepl: string;
}

function Settings({ activeTab = "settings-general" }: { activeTab?: string }) {
  const { lang, theme, setLanguage, setTheme, t } = useSettings();
  const currentTab: SettingsTab = (activeTab.startsWith("settings-") ? activeTab.replace("settings-", "") : "general") as SettingsTab;
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const [general, setGeneral] = useState({ gpuMemory: "auto", autoUpdate: true });
  const [models, setModels] = useState({ whisperModel: "large-v3", ollamaUrl: "http://localhost:11434", ttsCacheDir: "" });
  const [keys, setKeys] = useState<ApiKeys>(() => ({
    deepseek: "", openai: "", azure: "", google: "", gemini: "", huggingface: "", deepl: "",
  }));

  const { setApiKeys, apiKeys: storedKeys } = useSettings();
  const { modelStatus, isLoading, startDownload, cancelDownload, deleteModel } = useModelStatus(keys.huggingface);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [deleteConfirmModel, setDeleteConfirmModel] = useState<string | null>(null);
  type KeyStatus = "idle" | "testing" | "success" | "error";
  const [keyStatus, setKeyStatus] = useState<Record<string, KeyStatus>>({});

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  useEffect(() => {
    const nonEmpty = Object.entries(storedKeys).filter(([_, v]) => v).length > 0;
    if (nonEmpty) setKeys(prev => ({ ...prev, ...storedKeys }));
    // Mark keys with values as "idle" (untested)
    const initialStatus: Record<string, KeyStatus> = {};
    Object.entries(storedKeys).forEach(([k, v]) => { if (v) initialStatus[k] = "idle"; });
    if (Object.keys(initialStatus).length > 0) setKeyStatus(prev => ({ ...initialStatus, ...prev }));
  }, [storedKeys]);

  const debouncedSave = useCallback((newKeys: ApiKeys) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => setApiKeys(newKeys as unknown as Record<string, string>), 500);
  }, [setApiKeys]);

  useEffect(() => { return () => { if (saveTimer.current) clearTimeout(saveTimer.current); }; }, []);

  const updateKey = (id: keyof ApiKeys, value: string) => {
    setKeys(prev => { const next = { ...prev, [id]: value }; debouncedSave(next); return next; });
  };

  const renderStatus = (id: string) => {
    const s = keyStatus[id];
    if (s === "testing") return (
      <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--colorPaletteYellowForeground1)" }}>
        <LoaderCircle style={{ fontSize: 12, animation: "spin 1s linear infinite" }} /> {t("settings.keys.testing")}
      </span>
    );
    if (s === "success") return (
      <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, fontWeight: 600, color: "var(--colorPaletteGreenForeground1)" }}>
        <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 16, height: 16, borderRadius: "50%", background: "var(--colorPaletteGreenBackground3)" }}>
          <Check style={{ fontSize: 10 }} />
        </span>
        OK
      </span>
    );
    if (s === "error") return (
      <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, fontWeight: 600, color: "var(--colorPaletteRedForeground1)" }}>
        <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 16, height: 16, borderRadius: "50%", background: "var(--colorPaletteRedBackground3)" }}>
          <X style={{ fontSize: 10 }} />
        </span>
        FAIL
      </span>
    );
    if (keys[id as keyof ApiKeys]) return (
      <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, color: "var(--colorNeutralForeground3)" }}>
        <span className="status-dot" style={{ background: "var(--colorNeutralStroke2)" }} />
        {t("settings.keys.untested")}
      </span>
    );
    return null;
  };

  const handleTestConnection = async () => {
    setIsTesting(true); setTestResult(null); setKeyStatus({});
    const testApi = async (id: keyof ApiKeys, _name: string, url: string, options: RequestInit) => {
      setKeyStatus(prev => ({ ...prev, [id]: "testing" }));
      try {
        const res = await fetch(url, options);
        const ok = res.ok;
        setKeyStatus(prev => ({ ...prev, [id]: ok ? "success" : "error" }));
        return ok;
      } catch { setKeyStatus(prev => ({ ...prev, [id]: "error" })); return false; }
    };
    const promises: Promise<boolean>[] = [];
    if (keys.deepl) promises.push(testApi("deepl", "DeepL", `${keys.deepl.endsWith(":fx") ? "https://api-free.deepl.com" : "https://api.deepl.com"}/v2/usage`, { headers: { Authorization: `DeepL-Auth-Key ${keys.deepl}` } }));
    if (keys.deepseek) promises.push(testApi("deepseek", "DeepSeek", "https://api.deepseek.com/models", { headers: { Authorization: `Bearer ${keys.deepseek}` } }));
    if (keys.openai) promises.push(testApi("openai", "OpenAI", "https://api.openai.com/v1/models", { headers: { Authorization: `Bearer ${keys.openai}` } }));
    if (keys.huggingface) promises.push(testApi("huggingface", "HuggingFace", "https://huggingface.co/api/whoami-v2", { headers: { Authorization: `Bearer ${keys.huggingface}` } }));
    if (keys.gemini || keys.google) {
      const gkey = keys.gemini || keys.google;
      promises.push(testApi(keys.gemini ? "gemini" : "google", "Google", `https://generativelanguage.googleapis.com/v1beta/models?key=${gkey}`, {}));
    }
    if (promises.length === 0) { setIsTesting(false); setTestResult(t("settings.keys.no_keys")); return; }
    const results = await Promise.all(promises);
    const allOk = results.every(r => r);
    setIsTesting(false);
    if (allOk) {
      setTestResult("success");
      notifyToast.success(t("settings.keys.all_ok"));
    } else {
      setTestResult(t("settings.keys.failed"));
      notifyToast.error(t("settings.keys.failed"));
    }
  };

  // ═══ General ═══
  const renderGeneral = () => (
    <>
      <div className="win11-card">
        <div className="win11-card-header">{t("settings.appearance")}</div>
        <div className="win11-card-body">
          <div className="win11-form-row">
            <div className="win11-form-label">
              <div className="win11-form-label-text">{t("settings.language")}</div>
            </div>
            <div className="win11-form-control" style={{ width: 200 }}>
              <Select value={lang} onChange={(e) => setLanguage(e.target.value as Language)}>
                <option value="en">{t("settings.lang.en_label")}</option>
                <option value="ru">{t("settings.lang.ru_label")}</option>
                <option value="tr">{t("settings.lang.tr_label")}</option>
              </Select>
            </div>
          </div>
          <div className="win11-form-row">
            <div className="win11-form-label">
              <div className="win11-form-label-text">{t("settings.theme")}</div>
            </div>
            <div className="win11-form-control" style={{ width: 200 }}>
              <Select value={theme} onChange={(e) => setTheme(e.target.value)}>
                {THEME_OPTIONS.map(o => <option key={o.value} value={o.value}>{t(o.labelKey)}</option>)}
              </Select>
            </div>
          </div>
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.performance")}</div>
        <div className="win11-card-body">
          <div className="win11-form-row">
            <div className="win11-form-label">
              <div className="win11-form-label-text">{t("settings.gpu_limit")}</div>
              <div className="win11-form-label-desc">{t("settings.gpu_desc")}</div>
            </div>
            <div className="win11-form-control" style={{ width: 200 }}>
              <Select value={general.gpuMemory} onChange={(e) => setGeneral({ ...general, gpuMemory: e.target.value })}>
                <option value="auto">{t("settings.gpu.auto")}</option>
                <option value="4">{t("settings.gpu_4gb")}</option><option value="6">{t("settings.gpu_6gb")}</option>
                <option value="8">{t("settings.gpu_8gb")}</option><option value="12">{t("settings.gpu_12gb")}</option>
              </Select>
            </div>
          </div>
          <div className="win11-form-row">
            <div className="win11-form-label">
              <div className="win11-form-label-text">{t("settings.auto_update")}</div>
              <div className="win11-form-label-desc">{t("settings.auto_update_desc")}</div>
            </div>
            <div className="win11-form-control">
              <Switch checked={general.autoUpdate} onChange={(_, data) => setGeneral({ ...general, autoUpdate: data.checked })} />
            </div>
          </div>
        </div>
      </div>
    </>
  );

  // ═══ Models ═══
  const renderModels = () => (
    <>
      <div className="win11-card">
        <div className="win11-card-header">{t("settings.speech_rec")}</div>
        <div className="win11-card-body">
          <div className="win11-form-row">
            <div className="win11-form-label"><div className="win11-form-label-text">{t("settings.whisper_model")}</div></div>
            <div className="win11-form-control" style={{ width: 220 }}>
              <Select value={models.whisperModel} onChange={(e) => setModels({ ...models, whisperModel: e.target.value })}>
                <option value="tiny">{t("models.whisper_tiny")} — {t("settings.whisper.tiny")}</option>
                <option value="base">{t("models.whisper_base")} — {t("settings.whisper.base")}</option>
                <option value="small">{t("models.whisper_small")} — {t("settings.whisper.small")}</option>
                <option value="medium">{t("models.whisper_medium")} — {t("settings.whisper.medium")}</option>
                <option value="large-v2">{t("models.whisper_large_v2")} — {t("settings.whisper.large")}</option>
                <option value="large-v3">{t("models.whisper_large_v3")} — {t("settings.whisper.large")}</option>
              </Select>
            </div>
          </div>
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.ollama_config")}</div>
        <div className="win11-card-body">
          <div className="win11-form-row">
            <div className="win11-form-label"><div className="win11-form-label-text">{t("settings.ollama_url")}</div></div>
            <div className="win11-form-control" style={{ width: 280 }}>
              <Input className="font-mono" value={models.ollamaUrl} onChange={(e) => setModels({ ...models, ollamaUrl: e.target.value })} placeholder="http://localhost:11434" />
            </div>
          </div>
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.tts_audio")}</div>
        <div className="win11-card-body">
          <div className="win11-form-row">
            <div className="win11-form-label"><div className="win11-form-label-text">{t("settings.tts_cache")}</div></div>
            <div className="win11-form-control flex items-center gap-2">
              <Input style={{ width: 260 }} value={models.ttsCacheDir} onChange={(e) => setModels({ ...models, ttsCacheDir: e.target.value })} />
              <Button size="small" onClick={async () => {
                try { const s = await open({ directory: true, multiple: false }); if (s) setModels({ ...models, ttsCacheDir: s as string }); } catch {}
              }}>{t("settings.browse")}</Button>
            </div>
          </div>
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.model_status")}</div>
        <div className="win11-card-body">
          <p className="text-xs mb-4" style={{ color: "var(--colorNeutralForeground3)" }}>{t("settings.model_status_desc")}</p>

          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <label className="flex items-center gap-2 cursor-pointer text-xs">
              <input type="checkbox" checked={ALL_MODELS.length > 0 && ALL_MODELS.every(m => selectedModels.has(m.id))}
                onChange={(e) => setSelectedModels(e.target.checked ? new Set(ALL_MODELS.map(m => m.id)) : new Set())} />
              {t("dl.select_all")}
            </label>
            <span className="text-xs" style={{ color: "var(--colorNeutralForeground3)" }}>{selectedModels.size}/{ALL_MODELS.length}</span>
            <Button size="small" appearance="primary" disabled={isLoading || selectedModels.size === 0}
              icon={<Download style={{ fontSize: 14 }} />}
              onClick={() => selectedModels.forEach(id => { if (!modelStatus[id]?.done) startDownload(id); })}>
              {t("dl.btn_download")}
            </Button>
            <Button size="small" appearance="outline" disabled={isLoading || selectedModels.size === 0}
              style={{ color: "var(--colorPaletteRedForeground1)" }}
              icon={<Trash style={{ fontSize: 14 }} />}
              onClick={() => { const f = [...selectedModels].find(id => modelStatus[id]?.done); if (f) setDeleteConfirmModel(f); }}>
              {t("dl.btn_delete")}
            </Button>
          </div>

          {ALL_MODELS.map((model, i, arr) => {
            const st = modelStatus[model.id];
            const isDone = st?.done;
            const isDownloading = !isDone && st?.progress !== undefined && st.progress > 0 && st.progress < 100;
            const hasProgress = (st?.progress ?? 0) >= 5;
            return (
              <React.Fragment key={model.id}>
                <div className="flex items-center gap-3 py-3">
                  <input type="checkbox" checked={selectedModels.has(model.id)}
                    onChange={() => setSelectedModels(prev => { const n = new Set(prev); n.has(model.id) ? n.delete(model.id) : n.add(model.id); return n; })} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">{model.name}
                      <span className="font-normal text-xs ml-2" style={{ color: "var(--colorNeutralForeground3)" }}>{model.size}</span>
                    </span>
                    <div className="text-xs mt-0.5" style={{ color: "var(--colorBrandForeground1)" }}>{t(model.descDetailKey as any)}</div>
                    {isDownloading && hasProgress && <progress value={st.progress} max="100" style={{ width: "100%", maxWidth: 200, height: 4, marginTop: 8 }} />}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {isDownloading && hasProgress && <span className="text-xs font-semibold font-mono" style={{ color: "var(--colorBrandForeground1)", minWidth: 36, textAlign: "right" }}>{st.progress}%</span>}
                    {isDownloading && !hasProgress && (
                      <span className="text-xs flex items-center gap-1" style={{ color: "var(--colorBrandForeground1)" }}>
                        <LoaderCircle style={{ fontSize: 12, animation: "spin 1s linear infinite" }} />{t("dl.downloading_short")}
                      </span>
                    )}
                    {isDownloading && <Button size="small" appearance="outline" icon={<X style={{ fontSize: 12 }} />} style={{ color: "var(--colorPaletteRedForeground1)" }} onClick={() => cancelDownload(model.id)} />}
                    {isDone && <Button size="small" appearance="outline" icon={<Trash style={{ fontSize: 12 }} />} style={{ color: "var(--colorPaletteRedForeground1)" }} onClick={() => setDeleteConfirmModel(model.id)} />}
                    {!isDone && !isDownloading && <Button size="small" appearance="primary" icon={<Download style={{ fontSize: 12 }} />} onClick={() => startDownload(model.id)} disabled={isLoading} />}
                  </div>
                </div>
                {i < arr.length - 1 && <div style={{ height: 1, background: "var(--colorNeutralStroke2)" }} />}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </>
  );

  // ═══ Keys ═══
  const renderKeys = () => (
    <>
      <div className="flex gap-3 p-4 rounded-lg mb-4" style={{ background: "var(--colorNeutralBackground2)", border: "1px solid var(--colorNeutralStroke2)" }}>
        <Info style={{ fontSize: 18, flexShrink: 0 }} />
        <span className="text-sm">{t("settings.keys.notice")}</span>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.keys.translation_apis")}</div>
        <div className="win11-card-body">
          {([
            { id: "gemini" as keyof ApiKeys, label: t("settings.keys.gemini_label"), link: "https://aistudio.google.com/app/apikey", linkLabel: t("settings.keys.gemini_get"), ph: "AIzaSy..." },
            { id: "deepl" as keyof ApiKeys, label: t("settings.deepl_key"), desc: t("settings.deepl_desc"), link: "https://www.deepl.com/pro-api", linkLabel: `${t("settings.deepl_key")} ↗`, ph: "xxx:fx" },
            { id: "deepseek" as keyof ApiKeys, label: t("settings.keys.deepseek_label"), link: "https://platform.deepseek.com/api_keys", linkLabel: t("settings.keys.deepseek_get"), ph: "sk-..." },
            { id: "openai" as keyof ApiKeys, label: t("settings.keys.openai_label"), link: "https://platform.openai.com/api-keys", linkLabel: t("settings.keys.openai_get"), ph: "sk-proj-..." },
          ]).map(({ id, label, desc, link, linkLabel, ph }) => (
            <div key={id} className="win11-form-row">
              <div className="win11-form-label">
                <div className="win11-form-label-text">{label} {renderStatus(id)}</div>
                {desc && <div className="win11-form-label-desc">{desc}</div>}
                <a href={link} target="_blank" rel="noreferrer" className="text-xs flex items-center gap-1 mt-1" style={{ color: "var(--colorBrandForeground1)" }}>
                  {linkLabel}<ExternalLink style={{ fontSize: 10 }} />
                </a>
              </div>
              <div className="win11-form-control" style={{ width: 300 }}>
                <Input className="font-mono" type="password" value={keys[id]} onChange={(e) => updateKey(id, e.target.value)} placeholder={ph} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.keys.speech_apis")}</div>
        <div className="win11-card-body">
          {[
            { id: "azure" as keyof ApiKeys, label: t("settings.keys.azure_label"), link: "https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/SpeechServices", linkLabel: t("settings.keys.azure_get"), ph: t("settings.keys.azure_placeholder") },
            { id: "google" as keyof ApiKeys, label: t("settings.keys.google_label"), link: "https://console.cloud.google.com/apis/credentials", linkLabel: t("settings.keys.google_get"), ph: "AIzaSy..." },
          ].map(({ id, label, link, linkLabel, ph }) => (
            <div key={id} className="win11-form-row">
              <div className="win11-form-label">
                <div className="win11-form-label-text">{label} {renderStatus(id)}</div>
                <a href={link} target="_blank" rel="noreferrer" className="text-xs flex items-center gap-1 mt-1" style={{ color: "var(--colorBrandForeground1)" }}>
                  {linkLabel}<ExternalLink style={{ fontSize: 10 }} />
                </a>
              </div>
              <div className="win11-form-control" style={{ width: 300 }}>
                <Input className="font-mono" type="password" value={keys[id]} onChange={(e) => updateKey(id, e.target.value)} placeholder={ph} />
              </div>
            </div>
          ))}
          <div className="win11-form-row">
            <div className="win11-form-label">
              <div className="win11-form-label-text">{t("settings.hf_key")} {renderStatus("huggingface")}</div>
              <div className="win11-form-label-desc">
                {t("settings.hf_desc")} ·{" "}
                <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer" style={{ color: "var(--colorBrandForeground1)" }}>
                  {t("settings.keys.hf_get")}
                </a>
              </div>
              <div style={{
                marginTop: 12, padding: 12, borderRadius: 8,
                background: "var(--colorPaletteYellowBackground2)",
                border: "1px solid var(--colorPaletteYellowBorder1)",
                fontSize: 12, lineHeight: 1.6,
              }}>
                <strong style={{ color: "var(--colorPaletteYellowForeground1)" }}>⚠ {t("settings.hf_terms")}:</strong>
                <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                  <a href="https://huggingface.co/pyannote/speaker-diarization-3.1" target="_blank" rel="noreferrer"
                    className="flex items-center gap-1"
                    style={{ color: "var(--colorBrandForeground1)", fontWeight: 500 }}>
                    pyannote/speaker-diarization-3.1 <ExternalLink style={{ fontSize: 10 }} />
                  </a>
                  <a href="https://huggingface.co/pyannote/segmentation-3.0" target="_blank" rel="noreferrer"
                    className="flex items-center gap-1"
                    style={{ color: "var(--colorBrandForeground1)", fontWeight: 500 }}>
                    pyannote/segmentation-3.0 <ExternalLink style={{ fontSize: 10 }} />
                  </a>
                </div>
                <div style={{ marginTop: 6, color: "var(--colorNeutralForeground2)" }}>
                  {t("settings.hf_agree")}
                </div>
              </div>
            </div>
            <div className="win11-form-control" style={{ width: 300 }}>
              <Input className="font-mono" type="password" value={keys.huggingface} onChange={(e) => updateKey("huggingface", e.target.value)} placeholder="hf_..." />
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-4 items-center mt-4">
        <Button appearance="primary" onClick={handleTestConnection} disabled={isTesting}
          icon={isTesting ? <LoaderCircle style={{ fontSize: 16, animation: "spin 1s linear infinite" }} /> : <Check style={{ fontSize: 16 }} />}>
          {isTesting ? t("settings.keys.testing") : t("settings.keys.test_all")}
        </Button>
        {testResult === "success" && <span className="text-sm font-medium" style={{ color: "var(--colorPaletteGreenForeground1)" }}>{t("settings.keys_all_valid")}</span>}
        {testResult && testResult !== "success" && <span className="text-sm" style={{ color: "var(--colorPaletteYellowForeground1)" }}>{testResult}</span>}
      </div>
    </>
  );

  // ═══ About ═══
  const renderAbout = () => (
    <>
      <div className="win11-card" style={{ textAlign: "center" }}>
        <div style={{ padding: 32 }}>
          <img src="/logo-icon.png" alt="AutoDub Studio" style={{ width: 72, height: 72, borderRadius: 16, marginBottom: 16 }} />
          <h2 className="text-xl font-bold mb-1">{t("settings.about.app_name")}</h2>
          <p className="text-sm mb-4" style={{ color: "var(--colorNeutralForeground2)" }}>{t("settings.about.tagline")}</p>
          <div className="flex gap-2 justify-center flex-wrap">
            <Badge size="small">{t("settings.about.version_badge")}</Badge>
            <Badge size="small" appearance="outline">{t("settings.about.tech_badge")}</Badge>
          </div>
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.about.author")}</div>
        <div className="win11-card-body">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center shrink-0" style={{ width: 44, height: 44, borderRadius: 12, background: "var(--colorNeutralBackground3)", border: "1px solid var(--colorNeutralStroke2)" }}>
              <User style={{ fontSize: 22, color: "var(--colorNeutralForeground3)" }} />
            </div>
            <div>
              <div className="font-semibold">{t("settings.about.author_name")}</div>
              <div className="text-xs mt-1" style={{ color: "var(--colorNeutralForeground2)" }}>{t("settings.about.role")}</div>
              <div className="text-xs" style={{ color: "var(--colorNeutralForeground2)" }}>{t("settings.about.company")}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="win11-card" style={{ textAlign: "center" }}>
        <div style={{ padding: 24 }}>
          <div className="text-xs uppercase tracking-wider font-semibold mb-3" style={{ color: "var(--colorNeutralForeground3)" }}>{t("settings.about.partner")}</div>
          <img src="/teknorob.png" alt="Teknorob" style={{ height: 28, opacity: 0.7 }} />
        </div>
      </div>

      <div className="win11-card">
        <div className="win11-card-header">{t("settings.about.links")}</div>
        <div className="win11-card-body">
          {[
            { href: "https://github.com/liskinlabs/autodubstudio", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>, label: t("settings.about.github") },
            { href: "https://liskinlabs.com", icon: <Globe style={{ fontSize: 16 }} />, label: t("settings.about.website") },
          ].map(({ href, icon, label }) => (
            <a key={href} href={href} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-3 text-sm p-3 rounded-lg"
              style={{ color: "var(--colorNeutralForeground2)", textDecoration: "none" }}>
              {icon}{label}<ExternalLink style={{ fontSize: 11, marginLeft: "auto", opacity: 0.4 }} />
            </a>
          ))}
        </div>
      </div>
    </>
  );

  return (
    <div className="win11-page">
      {/* Delete Dialog */}
      <Dialog open={!!deleteConfirmModel} onOpenChange={(_, data) => { if (!data.open) setDeleteConfirmModel(null); }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>{t("dl.delete_confirm_title")}</DialogTitle>
            <p className="text-sm mb-4" style={{ color: "var(--colorNeutralForeground2)" }}>{t("dl.delete_confirm_desc")}</p>
            <p className="text-sm font-mono mb-4" style={{ color: "var(--colorNeutralForeground3)" }}>{deleteConfirmModel}</p>
          </DialogBody>
          <DialogActions>
            <Button appearance="subtle" onClick={() => setDeleteConfirmModel(null)}>{t("dubbing.btn.cancel")}</Button>
            <Button appearance="primary" icon={<Trash style={{ fontSize: 16 }} />}
              style={{ background: "var(--colorPaletteRedBackground3)", color: "var(--colorPaletteRedForeground1)" }}
              onClick={() => { deleteModel(deleteConfirmModel!); setDeleteConfirmModel(null); }}>
              {t("dl.btn_delete")}
            </Button>
          </DialogActions>
        </DialogSurface>
      </Dialog>

      <h1 className="win11-page-title">{t("settings.title")}</h1>
      <p className="win11-page-subtitle">{t("settings.subtitle")}</p>

      <div style={{ display: currentTab === "general" ? "block" : "none" }}>{renderGeneral()}</div>
      <div style={{ display: currentTab === "models" ? "block" : "none" }}>{renderModels()}</div>
      <div style={{ display: currentTab === "keys" ? "block" : "none" }}>{renderKeys()}</div>
      <div style={{ display: currentTab === "about" ? "block" : "none" }}>{renderAbout()}</div>
    </div>
  );
}

export default Settings;
