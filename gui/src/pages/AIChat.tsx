import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useOllama, type OllamaMessage } from '../hooks/useOllama';

// Removed hardcoded MODELS

import { useSettings } from '../store';

function AIChat() {
  const { t } = useSettings();
  const [messages, setMessages] = useState<OllamaMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, abort, isConnected, models, checkConnection, startOllama, stopOllama } = useOllama();

  // Check connection on mount and interval
  useEffect(() => {
    const fetchModels = () => {
      checkConnection().then(availableModels => {
        if (availableModels.length > 0 && !selectedModel) {
          setSelectedModel(availableModels[0]);
        }
      });
    };
    fetchModels();
    
    // Poll every 10 seconds to catch newly downloaded models
    const interval = setInterval(fetchModels, 10000);
    return () => clearInterval(interval);
  }, [checkConnection, selectedModel]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = '44px';
      el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    setError(null);

    const userMessage: OllamaMessage = { role: 'user', content: trimmed };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    // Add empty assistant message for streaming
    const assistantMessage: OllamaMessage = { role: 'assistant', content: '' };
    setMessages([...newMessages, assistantMessage]);

    // System prompt for agentic context
    const systemPrompt: OllamaMessage = {
      role: 'system',
      content: 'You are Gemma, the intelligent AI agent of AutoDubStudio. AutoDubStudio is a professional video dubbing software using Whisper for transcription and XTTS v2 for voice cloning. Your goal is to help the user translate scripts, adapt them for lip-sync, analyze emotions, and summarize content. Always keep the conversation context in mind. Be concise and professional.'
    };

    await sendMessage({
      model: selectedModel,
      messages: [systemPrompt, ...newMessages],
      onChunk: (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk,
            };
          }
          return updated;
        });
      },
      onDone: () => {
        setIsStreaming(false);
      },
      onError: (errMsg) => {
        setIsStreaming(false);
        setError(errMsg || t('chat.ollama_error'));
        // Remove the empty assistant message on error
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant' && last.content === '') {
            return prev.slice(0, -1);
          }
          return prev;
        });
      },
    });
  }, [input, isStreaming, messages, selectedModel, sendMessage, t]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    abort();
    setMessages([]);
    setError(null);
    setIsStreaming(false);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-base-100">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between p-4 border-b border-base-content/10 gap-4 shrink-0 bg-base-200/30">
        <div className="flex items-center gap-3 flex-wrap">
          {isConnected && (
            <>
              <select
                className="select select-bordered select-sm w-full max-w-xs"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {models.length === 0 ? (
                  <option value="">
                    {t('chat.no_models')}
                  </option>
                ) : (
                  models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                )}
              </select>
              
              <button 
                className="btn btn-ghost btn-sm btn-square" 
                onClick={() => checkConnection()}
                title="Обновить список моделей"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 4v6h6" />
                  <path d="M3.51 9a7 7 0 1 0-.12-4.46l-2.3 2.3" />
                </svg>
              </button>
            </>
          )}

          {isConnected !== null && (
            <div className="flex items-center gap-2 bg-base-200/50 px-3 py-1.5 rounded-lg border border-base-content/5">
              <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-error shadow-[0_0_8px_rgba(239,68,68,0.6)]'}`} />
              <span className="text-sm font-medium opacity-80">
                {isConnected ? t('status.ollama') : t('status.ollama_off')}
              </span>
              
              {isConnected ? (
                <button 
                  onClick={stopOllama}
                  className="btn btn-ghost btn-xs text-error ml-2" 
                >
                  Выключить
                </button>
              ) : (
                <button 
                  onClick={startOllama}
                  className="btn btn-primary btn-xs ml-2" 
                >
                  Включить Ollama
                </button>
              )}
            </div>
          )}
        </div>

        <button className="btn btn-outline btn-sm gap-2" onClick={handleNewChat}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M3 8h10M8 3v10" />
          </svg>
          {t('chat.new_chat')}
        </button>
      </div>

      {/* Error callout */}
      {error && (
        <div className="px-6 pt-4">
          <div className="alert alert-warning shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6" style={{ minHeight: 0 }}>
        {!isConnected ? (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-80 gap-4">
            <div className="text-6xl grayscale opacity-50 mb-2">💤</div>
            <h2 className="text-2xl font-bold">ИИ выключен</h2>
            <p className="max-w-md text-base-content/70">
              Локальный ИИ движок (Ollama) отключен для экономии памяти.
            </p>
            <button className="btn btn-primary mt-2" onClick={startOllama}>
              Запустить Ollama
            </button>
          </div>
        ) : messages.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full text-center opacity-80 gap-4">
            <div className="text-6xl drop-shadow-md mb-2">🤖</div>
            <h2 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">{t('chat.empty.title')}</h2>
            <p className="max-w-md text-base-content/70">
              {t('chat.empty.subtitle')}
            </p>
          </div>
        ) : (
          /* Messages */
          <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
            {messages.map((msg, i) => {
              const isAssistant = msg.role === 'assistant';
              const isLastAssistant =
                isAssistant && i === messages.length - 1 && isStreaming;
              const showTyping = isLastAssistant && msg.content === '';

              return (
                <div key={i} className={`chat ${isAssistant ? 'chat-start' : 'chat-end'}`}>
                  <div className="chat-image avatar">
                    <div className={`w-10 rounded-full flex items-center justify-center ${isAssistant ? 'bg-primary/20 text-primary' : 'bg-secondary/20 text-secondary'}`}>
                      {isAssistant ? (
                        <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
                          <path d="M8 1a2.5 2.5 0 0 0-2.5 2.5V5H4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1.5V3.5A2.5 2.5 0 0 0 8 1zM6.5 3.5a1.5 1.5 0 1 1 3 0V5h-3V3.5zM6 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm5 1a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
                        </svg>
                      ) : (
                        <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
                          <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm5 6a5 5 0 0 0-10 0h10z" />
                        </svg>
                      )}
                    </div>
                  </div>
                  <div className="chat-header opacity-50 mb-1">
                    {isAssistant ? 'AutoDub AI' : 'You'}
                  </div>
                  <div className={`chat-bubble max-w-[85%] ${isAssistant ? 'chat-bubble-primary bg-primary/10 text-base-content border border-primary/20' : 'chat-bubble-secondary text-secondary-content'} text-sm leading-relaxed`}>
                    {showTyping ? (
                      <span className="loading loading-dots loading-md"></span>
                    ) : (
                      <div className="prose prose-sm max-w-none prose-p:my-2 prose-pre:my-2 prose-pre:bg-base-300">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                        {isLastAssistant && (
                          <span className="inline-block w-1.5 h-4 bg-primary ml-1 align-text-bottom animate-pulse" />
                        )}
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

      {/* Input area */}
      {isConnected && (
        <div className="p-4 sm:p-6 bg-base-200/30 border-t border-base-content/10 shrink-0">
          <div className="max-w-4xl mx-auto relative flex items-end bg-base-100 rounded-xl border border-base-content/20 shadow-sm focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-all">
            <textarea
              ref={textareaRef}
              className="textarea w-full bg-transparent border-none focus:outline-none resize-none py-3 pl-4 pr-14 text-base leading-relaxed"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.placeholder')}
              rows={1}
              disabled={isStreaming}
              style={{ minHeight: '52px' }}
            />
            <button
              className="btn btn-primary btn-sm btn-square absolute right-2 bottom-2 z-10 rounded-lg"
              onClick={handleSend}
              disabled={isStreaming || !input.trim()}
              title={t('chat.send_title')}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ml-0.5">
                <path d="M2 9l14-7-7 14V9H2z" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default AIChat;
