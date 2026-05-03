import { TooltipProvider } from '@/components/ui/tooltip';
import {
  askStream,
  attachReferences,
  createSession,
  getStoredUser,
  listSessions,
  renameSession,
  type Message,
  type Session,
} from '@/services/api';
import { renderWithCitations } from '@/utils/citations';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';

const EXAMPLE_QUESTIONS = [
  '高血压患者平时饮食要注意什么？',
  '感冒发烧有哪些常见的处理方法？',
  '糖尿病和哪些并发症有关？',
  '失眠多梦该如何调理？',
];

function formatTime(ts?: number): string {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function UserAvatar({ nickname }: { nickname: string }) {
  const char = (nickname || '?')[0].toUpperCase();
  return (
    <div className="w-8 h-8 rounded-full bg-brand-blue flex items-center justify-center text-white text-sm font-bold shrink-0">
      {char}
    </div>
  );
}

function BotAvatar() {
  return <img src="/logo.svg" className="w-8 h-8" alt="logo" />;
}

function MessageBubble({
  msg,
  nickname,
  isStreaming,
}: {
  msg: Message;
  nickname: string;
  isStreaming?: boolean;
}) {
  const isUser = msg.role === 'user';
  return (
    <div
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start`}
    >
      {isUser ? <UserAvatar nickname={nickname} /> : <BotAvatar />}
      <div
        className={`max-w-[72%] px-5 py-3.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-brand-blue text-white rounded-tr-sm'
            : 'bg-white text-brand-ink border border-brand-border rounded-tl-sm shadow-sm'
        }`}
      >
        {isUser ? msg.content : renderWithCitations(msg.content, msg.reference)}
        {isStreaming && (
          <span className="inline-block w-1 h-4 ml-0.5 bg-current opacity-70 animate-[caret-blink_1s_ease-out_infinite]" />
        )}
      </div>
    </div>
  );
}

// ── SessionView — keyed on sessionId, remounts on switch ─────────────

function SessionView({
  session,
  nickname,
  onSessionCreated,
  onSessionUpdated,
}: {
  session: Session | null;
  nickname: string;
  onSessionCreated: () => void;
  onSessionUpdated: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>(() => {
    if (!session) return [];
    const msgs = attachReferences(session);
    return msgs.map((m, i) => ({
      ...m,
      id: m.id || `srv-${session.id}-${i}`,
    }));
  });
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // each send() call gets a unique id; only the latest call's updates are applied
  const sendIdRef = useRef('');

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  async function send(text: string, sid?: string) {
    const sessionId = sid ?? session?.id;
    if (!sessionId || !text.trim() || streaming) return;

    const question = text.trim();
    setInput('');

    const sendId = `${sessionId}-${Date.now()}`;
    sendIdRef.current = sendId;

    const userMsg: Message = {
      role: 'user',
      content: question,
      id: `u-${Date.now()}`,
    };
    setMessages((prev) =>
      sendIdRef.current !== sendId ? prev : [...prev, userMsg],
    );
    setStreaming(true);

    const botMsg: Message = {
      role: 'assistant',
      content: '',
      id: `s-${Date.now()}`,
    };
    setMessages((prev) =>
      sendIdRef.current !== sendId ? prev : [...prev, botMsg],
    );

    const streamId = botMsg.id;
    const controller = new AbortController();
    abortRef.current = controller;
    let aborted = false;
    let fullAnswer = '';

    try {
      for await (const chunk of askStream(
        question,
        sessionId,
        undefined,
        controller.signal,
      )) {
        if (aborted) return;
        if (sendIdRef.current !== sendId) {
          aborted = true;
          controller.abort();
          return;
        }
        if (chunk.done) {
          if (chunk.answer) fullAnswer = chunk.answer;
          if (sendIdRef.current !== sendId) return;
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== streamId) return m;
              const updated = { ...m, content: fullAnswer };
              if (chunk.reference) updated.reference = chunk.reference;
              return updated;
            }),
          );
          break;
        }
        fullAnswer += chunk.answer;
        if (sendIdRef.current !== sendId) return;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === streamId ? { ...m, content: fullAnswer } : m,
          ),
        );
      }
    } catch {
      aborted = true;
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }

    if (!aborted && sendIdRef.current === sendId) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === streamId ? { ...m, id: `a-${Date.now()}` } : m,
        ),
      );
      setStreaming(false);
      onSessionUpdated();
    } else {
      setStreaming(false);
    }
  }

  async function startNewChat(question: string) {
    const sessionName =
      question.slice(0, 20) + (question.length > 20 ? '…' : '');
    const newSession = await createSession(sessionName);
    if (!newSession) return;
    onSessionCreated();
    await send(question, newSession.id);
  }

  function handleSend() {
    if (!input.trim() || streaming) return;
    if (session) {
      send(input);
    } else {
      startNewChat(input);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const showWelcome = !session || messages.length === 0;

  return (
    <main className="flex-1 flex flex-col min-w-0">
      {showWelcome ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 pb-10">
          <img
            src="/logo.svg"
            className="w-20 h-20 drop-shadow-md mb-4"
            alt="logo"
          />
          <h2 className="text-2xl font-bold text-brand-ink mb-2">岐黄问诊</h2>
          <p className="text-brand-muted text-sm mb-10">
            有什么健康问题，尽管问我
          </p>
          <div className="grid grid-cols-2 gap-3 w-full max-w-xl">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => startNewChat(q)}
                className="text-left px-4 py-3 rounded-xl bg-white border border-brand-border text-sm text-brand-ink hover:border-brand-blue/40 hover:bg-brand-blue-light transition shadow-sm"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {messages.map((m, i) => (
            <MessageBubble
              key={m.id ?? i}
              msg={m}
              nickname={nickname}
              isStreaming={
                streaming && i === messages.length - 1 && m.role === 'assistant'
              }
            />
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      <div className="px-4 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-2 bg-white border border-brand-border rounded-2xl px-4 py-3 shadow-sm focus-within:border-brand-blue/50 focus-within:ring-2 focus-within:ring-brand-blue/10 transition">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，Enter 发送，Shift+Enter 换行"
              disabled={streaming}
              className="flex-1 resize-none bg-transparent text-sm text-brand-ink placeholder-brand-muted/50 outline-none min-h-[24px] max-h-[160px] leading-6 self-center"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || streaming}
              className="shrink-0 w-8 h-8 rounded-xl bg-brand-blue text-white flex items-center justify-center hover:bg-brand-blue-dark disabled:opacity-40 disabled:cursor-not-allowed transition"
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
          <p className="text-center text-xs text-brand-muted/50 mt-2">
            本平台仅供健康参考，不构成医疗建议，请咨询专业医生
          </p>
        </div>
      </div>
    </main>
  );
}

// ── ChatPage — outer shell (sidebar + keyed SessionView) ────────────

export default function ChatPage() {
  const navigate = useNavigate();
  const user = getStoredUser();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');

  useEffect(() => {
    if (!localStorage.getItem('qh_token')) navigate('/login');
  }, [navigate]);

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    const list = await listSessions();
    setSessions(list);
    setLoadingSessions(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const activeSession = activeId
    ? (sessions.find((s) => s.id === activeId) ?? null)
    : null;

  function handleSelectSession(s: Session) {
    setActiveId(s.id);
  }

  function handleNewChat() {
    setActiveId(null);
  }

  async function startRename(s: Session) {
    setRenamingId(s.id);
    setRenameVal(s.name);
  }

  async function commitRename(s: Session) {
    if (renameVal.trim() && renameVal !== s.name) {
      await renameSession(s.id, renameVal.trim());
      setSessions((prev) =>
        prev.map((x) => (x.id === s.id ? { ...x, name: renameVal.trim() } : x)),
      );
    }
    setRenamingId(null);
  }

  const nickname = user?.nickname || user?.email?.split('@')[0] || '用户';

  return (
    <TooltipProvider>
      <div className="flex h-screen bg-brand-gray overflow-hidden">
        {/* ── Sidebar ── */}
        <aside className="w-64 bg-white flex flex-col border-r border-brand-border shrink-0">
          <div className="px-4 pt-5 pb-4 border-b border-brand-border">
            <div className="flex items-center gap-2.5">
              <img src="/logo.svg" className="w-8 h-8" alt="logo" />
              <span className="font-bold text-brand-ink text-[20px]">
                岐黄问诊
              </span>
            </div>
          </div>

          <div className="px-3 pt-3 pb-2">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-brand-blue text-white text-sm font-medium hover:bg-brand-blue-dark transition"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              新对话
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
            {loadingSessions ? (
              <div className="text-center text-brand-muted/60 text-xs mt-6">
                加载中…
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center text-brand-muted/60 text-xs mt-6">
                暂无对话记录
              </div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => handleSelectSession(s)}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition ${
                    activeId === s.id
                      ? 'bg-brand-blue/10 border border-brand-blue/20'
                      : 'hover:bg-brand-gray/60'
                  }`}
                >
                  {renamingId === s.id ? (
                    <input
                      autoFocus
                      value={renameVal}
                      onChange={(e) => setRenameVal(e.target.value)}
                      onBlur={() => commitRename(s)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitRename(s);
                        if (e.key === 'Escape') setRenamingId(null);
                        e.stopPropagation();
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 text-xs bg-white border border-brand-border rounded px-1.5 py-0.5 text-brand-ink outline-none"
                    />
                  ) : (
                    <>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-brand-ink truncate">
                          {s.name}
                        </div>
                        <div className="text-xs text-brand-muted/60 mt-0.5">
                          {formatTime(s.update_time)}
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startRename(s);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-brand-border transition"
                      >
                        <svg
                          className="w-3 h-3 text-brand-muted"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-2.828 0L9 16v-3z"
                          />
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="px-3 py-3 border-t border-brand-border">
            <button
              onClick={() => navigate('/profile')}
              className="w-full flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-brand-gray/60 transition"
            >
              <UserAvatar nickname={nickname} />
              <div className="flex-1 text-left min-w-0">
                <div className="text-sm font-medium text-brand-ink truncate">
                  {nickname}
                </div>
                <div className="text-xs text-brand-muted/60 truncate">
                  {user?.email}
                </div>
              </div>
            </button>
          </div>
        </aside>

        {/* ── Session view — keyed on activeId for clean remount ── */}
        <SessionView
          key={activeId ?? '__new__'}
          session={activeSession}
          nickname={nickname}
          onSessionCreated={loadSessions}
          onSessionUpdated={loadSessions}
        />
      </div>
    </TooltipProvider>
  );
}
