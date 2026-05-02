import {
  DIALOG_ID,
  GUEST_LIMIT,
  GUEST_TOKEN,
  type Message,
} from '@/services/api';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';

const EXAMPLE_QUESTIONS = [
  '高血压患者平时饮食要注意什么？',
  '感冒发烧有哪些常见的处理方法？',
  '糖尿病和哪些并发症有关？',
  '失眠多梦该如何调理？',
];

const GUEST_COUNT_KEY = 'qh_guest_count';
const GUEST_SESSION_KEY = 'qh_guest_session';

function getGuestCount(): number {
  return parseInt(localStorage.getItem(GUEST_COUNT_KEY) || '0', 10);
}
function incGuestCount() {
  localStorage.setItem(GUEST_COUNT_KEY, String(getGuestCount() + 1));
}

function BotAvatar() {
  return (
    <div className="w-8 h-8 rounded-full bg-qh-gold/20 border border-qh-gold/30 flex items-center justify-center text-qh-gold text-sm font-bold shrink-0">
      岐
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="w-8 h-8 rounded-full bg-qh-green flex items-center justify-center text-white text-sm font-bold shrink-0">
      您
    </div>
  );
}

function PaywallModal({
  onRegister,
  onLogin,
  onClose,
}: {
  onRegister: () => void;
  onLogin: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl shadow-xl p-8 mx-4 max-w-sm w-full text-center"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-14 h-14 rounded-2xl bg-qh-green flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4">
          岐
        </div>
        <h2 className="text-xl font-bold text-qh-ink mb-2">继续使用需要注册</h2>
        <p className="text-sm text-qh-brown mb-6 leading-relaxed">
          您已体验 {GUEST_LIMIT} 次免费问答。
          <br />
          注册账号即可无限使用，并保存历史对话。
        </p>
        <button
          onClick={onRegister}
          className="w-full py-3 rounded-xl bg-qh-green text-white font-semibold text-sm hover:bg-qh-green-dark transition mb-3"
        >
          免费注册
        </button>
        <button
          onClick={onLogin}
          className="w-full py-3 rounded-xl border border-qh-border text-qh-ink font-medium text-sm hover:bg-qh-cream transition"
        >
          已有账号，去登录
        </button>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();

  // If already logged in, skip to chat
  useEffect(() => {
    if (localStorage.getItem('qh_token')) navigate('/chat', { replace: true });
  }, [navigate]);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() =>
    localStorage.getItem(GUEST_SESSION_KEY),
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasMessages = messages.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  async function getOrCreateSession(): Promise<string | null> {
    if (sessionId) return sessionId;
    // Create session using guest token
    const res = await fetch(`/api/v1/chats/${DIALOG_ID}/sessions`, {
      method: 'POST',
      headers: {
        Authorization: GUEST_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: '游客对话' }),
    });
    const data = await res.json();
    if (data.code === 0) {
      const id = data.data.id as string;
      setSessionId(id);
      localStorage.setItem(GUEST_SESSION_KEY, id);
      return id;
    }
    return null;
  }

  async function sendMessage(text: string) {
    if (!text.trim() || streaming) return;

    if (getGuestCount() >= GUEST_LIMIT) {
      setShowPaywall(true);
      return;
    }

    const question = text.trim();
    setInput('');

    const sid = await getOrCreateSession();
    if (!sid) return;

    const userMsg: Message = {
      role: 'user',
      content: question,
      id: Date.now().toString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);

    const botMsg: Message = { role: 'assistant', content: '', id: 'streaming' };
    setMessages((prev) => [...prev, botMsg]);

    incGuestCount();

    let fullAnswer = '';
    try {
      const res = await fetch('/api/v1/chats/ask', {
        method: 'POST',
        headers: {
          Authorization: GUEST_TOKEN,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          dialog_id: DIALOG_ID,
          session_id: sid,
          stream: true,
        }),
      });

      if (!res.ok || !res.body) throw new Error('request failed');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const raw = trimmed.slice(5).trim();
          if (!raw) continue;
          try {
            const parsed = JSON.parse(raw);
            if (parsed.data === true) {
              reader.cancel();
              break;
            }
            if (parsed.code !== 0) {
              reader.cancel();
              break;
            }
            fullAnswer = (parsed.data as { answer: string }).answer ?? '';
            setMessages((prev) =>
              prev.map((m) =>
                m.id === 'streaming' ? { ...m, content: fullAnswer } : m,
              ),
            );
          } catch {
            /* skip malformed */
          }
        }
      }
    } finally {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === 'streaming' ? { ...m, id: Date.now().toString() } : m,
        ),
      );
      setStreaming(false);

      // Show paywall after completing the last free question
      if (getGuestCount() >= GUEST_LIMIT) {
        setTimeout(() => setShowPaywall(true), 800);
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-qh-cream">
      {/* Header */}
      <header className="bg-white border-b border-qh-border px-5 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-qh-green flex items-center justify-center text-white font-bold text-sm">
            岐
          </div>
          <span className="font-bold text-qh-ink text-sm">岐黄问诊</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/login')}
            className="px-4 py-1.5 text-sm text-qh-ink hover:text-qh-green transition font-medium"
          >
            登录
          </button>
          <button
            onClick={() => navigate('/register')}
            className="px-4 py-1.5 text-sm bg-qh-green text-white rounded-lg hover:bg-qh-green-dark transition font-medium"
          >
            注册
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col min-h-0">
        {!hasMessages ? (
          /* Welcome */
          <div className="flex-1 flex flex-col items-center justify-center px-6 pb-10">
            <div className="w-16 h-16 rounded-2xl bg-qh-green flex items-center justify-center text-white text-3xl font-bold mb-5 shadow-md">
              岐
            </div>
            <h2 className="text-2xl font-bold text-qh-ink mb-1">岐黄问诊</h2>
            <p className="text-qh-brown text-sm mb-2">
              AI 辅助医疗问答 · 有问必答
            </p>
            <p className="text-qh-brown/60 text-xs mb-8">
              免费体验 {GUEST_LIMIT} 次问答，
              <button
                onClick={() => navigate('/register')}
                className="text-qh-green underline underline-offset-2"
              >
                注册
              </button>{' '}
              后无限使用
            </p>
            <div className="grid grid-cols-2 gap-3 w-full max-w-xl">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="text-left px-4 py-3 rounded-xl bg-white border border-qh-border text-sm text-qh-ink hover:border-qh-green/40 hover:bg-qh-green-light transition shadow-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 max-w-3xl mx-auto w-full">
            {messages.map((m, i) => {
              const isUser = m.role === 'user';
              return (
                <div
                  key={m.id ?? i}
                  className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start`}
                >
                  {isUser ? <UserAvatar /> : <BotAvatar />}
                  <div
                    className={`max-w-[72%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                      isUser
                        ? 'bg-qh-green text-white rounded-tr-sm'
                        : 'bg-white text-qh-ink border border-qh-border-light rounded-tl-sm shadow-sm'
                    }`}
                  >
                    {m.content}
                    {streaming && i === messages.length - 1 && !isUser && (
                      <span className="inline-block w-1 h-4 ml-0.5 bg-current opacity-70 animate-[caret-blink_1s_ease-out_infinite]" />
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}

        {/* Input */}
        <div className="px-4 pb-4 pt-2 shrink-0">
          <div className="max-w-3xl mx-auto">
            {/* Remaining count badge */}
            {hasMessages && getGuestCount() < GUEST_LIMIT && (
              <p className="text-center text-xs text-qh-brown/60 mb-2">
                还剩{' '}
                <span className="font-semibold text-qh-green">
                  {GUEST_LIMIT - getGuestCount()}
                </span>{' '}
                次免费问答 ·{' '}
                <button
                  onClick={() => navigate('/register')}
                  className="text-qh-green underline underline-offset-2"
                >
                  注册无限使用
                </button>
              </p>
            )}
            <div className="flex items-end gap-2 bg-white border border-qh-border rounded-2xl px-4 py-3 shadow-sm focus-within:border-qh-green/50 focus-within:ring-2 focus-within:ring-qh-green/10 transition">
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入问题，Enter 发送，Shift+Enter 换行"
                disabled={streaming}
                className="flex-1 resize-none bg-transparent text-sm text-qh-ink placeholder-qh-brown/50 outline-none min-h-[24px] max-h-[160px] leading-6"
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={!input.trim() || streaming}
                className="shrink-0 w-8 h-8 rounded-xl bg-qh-green text-white flex items-center justify-center hover:bg-qh-green-dark disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                {streaming ? (
                  <svg
                    className="w-4 h-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 12h14M12 5l7 7-7 7"
                    />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-center text-[11px] text-qh-brown/50 mt-2">
              本平台仅供健康参考，不构成医疗建议，请咨询专业医生
            </p>
          </div>
        </div>
      </main>

      {showPaywall && (
        <PaywallModal
          onRegister={() => navigate('/register')}
          onLogin={() => navigate('/login')}
          onClose={() => setShowPaywall(false)}
        />
      )}
    </div>
  );
}
