import { Base64 } from 'js-base64';
import JSEncrypt from 'jsencrypt';

const PUBLIC_KEY =
  '-----BEGIN PUBLIC KEY-----MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArq9XTUSeYr2+N1h3Afl/z8Dse/2yD0ZGrKwx+EEEcdsBLca9Ynmx3nIB5obmLlSfmskLpBo0UACBmB5rEjBp2Q2f3AG3Hjd4B+gNCG6BDaawuDlgANIhGnaTLrIqWrrcm4EMzJOnAOI1fgzJRsOOUEfaS318Eq9OVO3apEyCCt0lOQK6PuksduOjVxtltDav+guVAA068NrPYmRNabVKRNLJpL8w4D44sfth5RvZ3q9t+6RTArpEtc5sh5ChzvqPOzKGMXW83C95TxmXqpbK6olN4RevSfVjEAgCydH6HN6OhtOQEcnrU97r9H0iZOWwbw3pVrZiUkuRD1R56Wzs2wIDAQAB-----END PUBLIC KEY-----';

export const DIALOG_ID = 'da03725a463a11f1b76c2517003e8f20';
export const GUEST_TOKEN = 'e599ae72463f11f1b76c2517003e8f20';
export const GUEST_LIMIT = 3;

export function rsaEncrypt(password: string): string {
  const enc = new JSEncrypt();
  enc.setPublicKey(PUBLIC_KEY);
  return enc.encrypt(Base64.encode(password)) as string;
}

function getToken(): string {
  return localStorage.getItem('qh_token') ?? '';
}

function authHeaders(): Record<string, string> {
  return { Authorization: getToken(), 'Content-Type': 'application/json' };
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: authHeaders() });
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface LoginResult {
  code: number;
  message: string;
  data:
    | { access_token: string; nickname: string; email: string; avatar?: string }
    | false;
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResult> {
  return post<LoginResult>('/v1/user/login', {
    email,
    password: rsaEncrypt(password),
  });
}

export async function logout(): Promise<void> {
  await get('/v1/user/logout');
  localStorage.removeItem('qh_token');
  localStorage.removeItem('qh_user');
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export interface Session {
  id: string;
  name: string;
  dialog_id: string;
  message: Message[];
  update_time?: number;
  create_time?: number;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  id?: string;
  created_at?: number;
}

export interface SessionListResult {
  code: number;
  data: Session[];
}

export async function listSessions(): Promise<Session[]> {
  const res = await get<SessionListResult>(
    `/api/v1/chats/${DIALOG_ID}/sessions?page=1&page_size=100&orderby=update_time&desc=true`,
  );
  return res.code === 0 ? res.data : [];
}

export async function createSession(name = '新对话'): Promise<Session | null> {
  const res = await post<{ code: number; data: Session }>(
    `/api/v1/chats/${DIALOG_ID}/sessions`,
    { name },
  );
  return res.code === 0 ? res.data : null;
}

export async function renameSession(
  sessionId: string,
  name: string,
): Promise<void> {
  await put(`/api/v1/chats/${DIALOG_ID}/sessions/${sessionId}`, { name });
}

export async function getSession(sessionId: string): Promise<Session | null> {
  const res = await get<{ code: number; data: Session }>(
    `/api/v1/chats/${DIALOG_ID}/sessions/${sessionId}`,
  );
  return res.code === 0 ? res.data : null;
}

// ── Streaming ask ─────────────────────────────────────────────────────────────

export interface AskChunk {
  answer: string;
  session_id?: string;
  done: boolean;
}

export async function* askStream(
  question: string,
  sessionId: string,
  onSessionId?: (id: string) => void,
): AsyncGenerator<AskChunk> {
  const res = await fetch('/api/v1/chats/ask', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      question,
      dialog_id: DIALOG_ID,
      session_id: sessionId,
      stream: true,
    }),
  });

  if (!res.ok || !res.body) {
    yield { answer: '请求失败，请稍后重试。', done: true };
    return;
  }

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
        if (parsed.code !== 0) {
          yield { answer: parsed.message ?? '发生错误', done: true };
          return;
        }
        // final sentinel
        if (parsed.data === true) {
          yield { answer: '', done: true };
          return;
        }
        const chunk = parsed.data as { answer: string; session_id?: string };
        if (chunk.session_id && onSessionId) onSessionId(chunk.session_id);
        yield { answer: chunk.answer ?? '', done: false };
      } catch {
        // skip malformed lines
      }
    }
  }
}

// ── User ──────────────────────────────────────────────────────────────────────

export interface UserInfo {
  id: string;
  nickname: string;
  email: string;
  avatar?: string;
}

export function getStoredUser(): UserInfo | null {
  const raw = localStorage.getItem('qh_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function updateNickname(nickname: string): Promise<boolean> {
  const res = await put<{ code: number }>('/v1/user/setting', { nickname });
  return res.code === 0;
}

export async function register(
  email: string,
  nickname: string,
  password: string,
): Promise<LoginResult> {
  return post<LoginResult>('/v1/user/register', {
    email,
    nickname,
    password: rsaEncrypt(password),
  });
}

export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await post<{ code: number; message: string }>(
    '/v1/user/password',
    {
      old_password: rsaEncrypt(oldPassword),
      new_password: rsaEncrypt(newPassword),
    },
  );
  return { ok: res.code === 0, message: res.message };
}
