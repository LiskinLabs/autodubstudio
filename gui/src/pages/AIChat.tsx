import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button, Select, Textarea } from "@fluentui/react-components";
import {
  ArrowSyncRegular as RefreshCw, AddRegular as Plus, SendRegular as Send,
  WarningRegular as AlertTriangle, FlashRegular as Zap, FlashOffRegular as ZapOff,
  BotRegular as Bot, PersonRegular as User,
} from "@fluentui/react-icons";
import { useOllama, type OllamaMessage } from "../hooks/useOllama";
import { useSettings } from "../store";

function AIChat() {
  const { t } = useSettings();
  const [messages, setMessages] = useState<OllamaMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, abort, isConnected, models, checkConnection, startOllama, stopOllama } = useOllama();

  useEffect(() => {
    const fetchModels = () => checkConnection().then(availableModels => {
      if (availableModels.length > 0 && !selectedModel) setSelectedModel(availableModels[0]);
    });
    fetchModels();
    const interval = setInterval(fetchModels, 10000);
    return () => clearInterval(interval);
  }, [checkConnection, selectedModel]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) { el.style.height = "44px"; el.style.height = Math.min(el.scrollHeight, 120) + "px"; }
  }, [input]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setError(null);
    const userMsg: OllamaMessage = { role: "user", content: trimmed };
    const newMsgs = [...messages, userMsg];
    setMessages(newMsgs); setInput(""); setIsStreaming(true);
    setMessages([...newMsgs, { role: "assistant", content: "" }]);

    await sendMessage({
      model: selectedModel,
      messages: [{ role: "system", content: "You are an AI assistant for AutoDubStudio, a professional video dubbing software. Help with translations, scripts, and content. Be concise and professional." }, ...newMsgs],
      onChunk: (chunk) => setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") updated[updated.length - 1] = { ...last, content: last.content + chunk };
        return updated;
      }),
      onDone: () => setIsStreaming(false),
      onError: (errMsg) => {
        setIsStreaming(false); setError(errMsg || t("chat.ollama_error"));
        setMessages(prev => prev[prev.length - 1]?.role === "assistant" && prev[prev.length - 1].content === "" ? prev.slice(0, -1) : prev);
      },
    });
  }, [input, isStreaming, messages, selectedModel, sendMessage, t]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="flex flex-col" style={{ height: "100%" }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3 shrink-0"
        style={{ padding: "12px max(20px, min(48px, 4vw))", borderBottom: "1px solid var(--colorNeutralStroke2)", background: "var(--colorNeutralBackground1)" }}>
        <div className="flex items-center gap-3 flex-wrap">
          {isConnected && (
            <div className="flex items-center gap-2" style={{ padding: "4px 8px", borderRadius: 8, background: "var(--colorNeutralBackground2)", border: "1px solid var(--colorNeutralStroke2)" }}>
              <Select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} size="small" aria-label={t("chat.model_selector")}>
                {models.length === 0 ? <option value="">{t("chat.no_models")}</option> : models.map(m => <option key={m} value={m}>{m}</option>)}
              </Select>
              <Button appearance="subtle" size="small" shape="circular" icon={<RefreshCw style={{ fontSize: 14 }} />} onClick={() => checkConnection()} />
            </div>
          )}
          <div className="flex items-center gap-2" style={{ padding: "4px 8px", borderRadius: 8, background: "var(--colorNeutralBackground2)", border: "1px solid var(--colorNeutralStroke2)" }}>
            <span className="status-dot" style={{ background: isConnected ? "var(--colorPaletteGreenForeground1)" : "var(--colorPaletteRedForeground1)", width: 8, height: 8 }} />
            <span className="text-sm">{isConnected ? t("status.ollama") : t("status.ollama_off")}</span>
            <Button appearance={isConnected ? "subtle" : "primary"} size="small"
              icon={isConnected ? <ZapOff style={{ fontSize: 14 }} /> : <Zap style={{ fontSize: 14 }} />}
              onClick={isConnected ? stopOllama : startOllama}
              style={isConnected ? { color: "var(--colorPaletteRedForeground1)" } : undefined}>
              {isConnected ? t("chat.stop_ollama") : t("chat.start_ollama")}
            </Button>
          </div>
        </div>
        <Button appearance="outline" size="small" icon={<Plus style={{ fontSize: 14 }} />} onClick={() => { abort(); setMessages([]); setError(null); setIsStreaming(false); setInput(""); }}>
          {t("chat.new_chat")}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: "12px max(20px, min(48px, 4vw))" }}>
          <div className="flex gap-3 p-4 rounded-lg" style={{ background: "var(--colorPaletteYellowBackground2)", border: "1px solid var(--colorPaletteYellowBorder1)" }}>
            <AlertTriangle style={{ fontSize: 18, color: "var(--colorPaletteYellowForeground1)" }} />
            <span className="text-sm font-medium">{error}</span>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto" style={{ padding: "24px max(20px, min(48px, 4vw))" }}>
        {!isConnected ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div style={{ padding: 20, borderRadius: 16, background: "var(--colorNeutralBackground3)" }}>
              <ZapOff style={{ fontSize: 48, opacity: 0.3 }} />
            </div>
            <h2 className="text-xl font-semibold">{t("chat.ollama_off_title")}</h2>
            <p className="text-sm" style={{ color: "var(--colorNeutralForeground2)" }}>{t("chat.ollama_off_desc")}</p>
            <Button appearance="primary" icon={<Zap />} onClick={startOllama}>{t("chat.start_ollama")}</Button>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div style={{ padding: 20, borderRadius: 16, background: "var(--colorBrandBackground2)" }}>
              <Bot style={{ fontSize: 48, color: "var(--colorBrandForeground1)", opacity: 0.6 }} />
            </div>
            <h2 className="text-xl font-semibold">{t("chat.empty.title")}</h2>
            <p className="text-sm" style={{ color: "var(--colorNeutralForeground2)" }}>{t("chat.empty.subtitle")}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6" style={{ maxWidth: 768, margin: "0 auto" }}>
            {messages.map((msg, i) => {
              const isAssistant = msg.role === "assistant";
              const isLastAssistant = isAssistant && i === messages.length - 1 && isStreaming;
              const showTyping = isLastAssistant && msg.content === "";
              return (
                <div key={i} className={`chat-message ${isAssistant ? "assistant" : "user"}`} style={{
                  display: "flex", gap: 12, maxWidth: "85%",
                  alignSelf: isAssistant ? "flex-start" : "flex-end",
                  flexDirection: isAssistant ? "row" : "row-reverse",
                }}>
                  <div className="flex items-center justify-center shrink-0" style={{
                    width: 32, height: 32, borderRadius: "50%",
                    background: isAssistant ? "var(--colorBrandBackground2)" : "var(--colorNeutralBackground3)",
                    color: isAssistant ? "var(--colorBrandForeground1)" : "var(--colorNeutralForeground2)",
                  }}>
                    {isAssistant ? <Bot style={{ fontSize: 16 }} /> : <User style={{ fontSize: 16 }} />}
                  </div>
                  <div className="win11-chat-bubble" style={{ background: isAssistant ? "var(--colorNeutralBackground2)" : "var(--colorBrandBackground)", color: isAssistant ? "var(--colorNeutralForeground1)" : "var(--colorNeutralForegroundStaticInverted)", border: isAssistant ? "1px solid var(--colorNeutralStroke2)" : "none" }}>
                    {showTyping ? (
                      <span><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></span>
                    ) : (
                      <div className="prose" style={{ color: "inherit" }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        {isLastAssistant && <span className="animate-pulse" style={{ display: "inline-block", width: 4, height: 14, background: "currentColor", marginLeft: 2, verticalAlign: "text-bottom", borderRadius: 2 }} />}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      {isConnected && (
        <div className="shrink-0" style={{ padding: "16px max(20px, min(48px, 4vw)) 24px", borderTop: "1px solid var(--colorNeutralStroke2)" }}>
          <div className="flex items-end gap-3" style={{ maxWidth: 768, margin: "0 auto" }}>
            <Textarea ref={textareaRef} value={input}
              onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
              placeholder={t("chat.placeholder")} disabled={isStreaming}
              className="flex-1" style={{ minHeight: 44, maxHeight: 120, resize: "none", borderRadius: 12 }} />
            <Button appearance="primary" shape="circular" icon={<Send style={{ fontSize: 16 }} />}
              onClick={handleSend} disabled={isStreaming || !input.trim()} />
          </div>
          <div className="text-center mt-3 text-xs" style={{ color: "var(--colorNeutralForeground4)" }}>
            {t("chat.disclaimer")}
          </div>
        </div>
      )}
    </div>
  );
}

export default AIChat;
