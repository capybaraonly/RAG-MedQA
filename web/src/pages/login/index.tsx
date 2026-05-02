import { login } from '@/services/api';
import { useState } from 'react';
import { useNavigate } from 'react-router';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError('');
    try {
      const res = await login(email, password);
      if (res.code === 0 && res.data) {
        localStorage.setItem('qh_token', res.data.access_token);
        localStorage.setItem(
          'qh_user',
          JSON.stringify({
            nickname: res.data.nickname,
            email: res.data.email,
            avatar: res.data.avatar ?? '',
          }),
        );
        navigate('/chat');
      } else {
        setError(res.message || '邮箱或密码错误');
      }
    } catch {
      setError('网络异常，请稍后重试');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-qh-cream flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo area */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-qh-green mb-4 shadow-md">
            <span className="text-white text-2xl font-bold">岐</span>
          </div>
          <h1 className="text-2xl font-bold text-qh-ink tracking-wide">
            岐黄问诊
          </h1>
          <p className="text-qh-brown text-sm mt-1">AI 辅助医疗问答平台</p>
        </div>

        {/* Form card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl shadow-sm border border-qh-border p-8 space-y-5"
        >
          <div>
            <label className="block text-sm font-medium text-qh-ink mb-1.5">
              邮箱
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱"
              autoComplete="email"
              className="w-full px-4 py-2.5 rounded-xl border border-qh-border bg-qh-cream/50 text-qh-ink placeholder-qh-brown/60 focus:outline-none focus:ring-2 focus:ring-qh-green/40 focus:border-qh-green transition text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-qh-ink mb-1.5">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              autoComplete="current-password"
              className="w-full px-4 py-2.5 rounded-xl border border-qh-border bg-qh-cream/50 text-qh-ink placeholder-qh-brown/60 focus:outline-none focus:ring-2 focus:ring-qh-green/40 focus:border-qh-green transition text-sm"
            />
          </div>

          {error && <p className="text-red-500 text-sm text-center">{error}</p>}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full py-2.5 rounded-xl bg-qh-green text-white font-medium text-sm hover:bg-qh-green-dark disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? '登录中…' : '登录'}
          </button>
        </form>

        <p className="text-center text-sm text-qh-brown mt-5">
          还没有账号？{' '}
          <button
            onClick={() => navigate('/register')}
            className="text-qh-green font-medium hover:underline"
          >
            免费注册
          </button>
        </p>

        <p className="text-center text-xs text-qh-brown/60 mt-4">
          本平台仅供健康参考，不构成医疗建议，请咨询专业医生
        </p>
      </div>
    </div>
  );
}
