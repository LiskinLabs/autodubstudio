import { useState, useRef, useEffect, useCallback } from 'react';
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
  const { sendMessage, abort, isConnected, models, checkConnection } = useOllama();

  // Check connection on mount
  useEffect(() => {
    checkConnection().then(availableModels => {
      if (availableModels.length > 0) {
        setSelectedModel(availableModels[0]);
      }
    });
  }, [checkConnection]);

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

    await sendMessage({
      model: selectedModel,
      messages: newMessages,
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
    <div className="page" style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <div
        className="flex items-center justify-between"
        style={{
          padding: 'var(--space-3) var(--space-6)',
          borderBottom: '1px solid var(--border-subtle)',
          gap: 'var(--space-3)',
          flexShrink: 0,
        }}
      >
        <div className="flex items-center gap-3">
          <select
            className="form-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{ width: 200 }}
          >
            {models.length === 0 ? (
              <option value="">
                {isConnected ? t('chat.no_models') : t('chat.ollama_error')}
              </option>
            ) : (
              models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))
            )}
          </select>

          {isConnected !== null && (
            <div className="flex items-center gap-2">
              <span
                className="status-dot"
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: isConnected ? 'var(--success)' : 'var(--error)',
                  boxShadow: isConnected
                    ? '0 0 6px var(--success)'
                    : '0 0 6px var(--error)',
                }}
              />
              <span className="text-sm text-muted">
                {isConnected ? t('status.ollama') : t('status.ollama_off')}
              </span>
            </div>
          )}
        </div>

        <button className="btn btn-ghost" onClick={handleNewChat}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M3 8h10M8 3v10" />
          </svg>
          {t('chat.new_chat')}
        </button>
      </div>

      {/* Error callout */}
      {error && (
        <div className="callout callout-warning" style={{ margin: 'var(--space-4) var(--space-6) 0', marginBottom: 0 }}>
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Chat area */}
      <div className="chat-container" style={{ flex: 1, minHeight: 0 }}>
        {messages.length === 0 ? (
          /* Empty state */
          <div className="chat-empty">
            <div className="chat-empty-icon">🤖</div>
            <div className="chat-empty-title">{t('chat.empty.title')}</div>
            <div className="chat-empty-subtitle" style={{ maxWidth: 380, textAlign: 'center', lineHeight: 1.6 }}>
              {t('chat.empty.subtitle')}
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="chat-messages">
            {messages.map((msg, i) => {
              const isAssistant = msg.role === 'assistant';
              const isLastAssistant =
                isAssistant && i === messages.length - 1 && isStreaming;
              const showTyping = isLastAssistant && msg.content === '';

              return (
                <div key={i} className={`chat-message ${msg.role}`}>
                  <div className="chat-avatar">
                    {isAssistant ? (
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M8 1a2.5 2.5 0 0 0-2.5 2.5V5H4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1.5V3.5A2.5 2.5 0 0 0 8 1zM6.5 3.5a1.5 1.5 0 1 1 3 0V5h-3V3.5zM6 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm5 1a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm5 6a5 5 0 0 0-10 0h10z" />
                      </svg>
                    )}
                  </div>
                  <div className="chat-bubble">
                    {showTyping ? (
                      <div className="typing-indicator">
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                      </div>
                    ) : (
                      <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {msg.content}
                        {isLastAssistant && (
                          <span
                            style={{
                              display: 'inline-block',
                              width: 2,
                              height: '1em',
                              background: 'var(--accent)',
                              marginLeft: 2,
                              animation: 'typingBounce 1s infinite',
                              verticalAlign: 'text-bottom',
                            }}
                          />
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
      <div className="chat-input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.placeholder')}
          rows={1}
          disabled={isStreaming}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          title={t('chat.send_title')}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 9l14-7-7 14V9H2z" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default AIChat;
