import { register } from '@/services/api';
import { useState } from 'react';
import { useNavigate } from 'react-router';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [nickname, setNickname] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!nickname || !email || !password || !confirmPassword) return;
    if (password !== confirmPassword) {
      setError('两次密码不一致');
      return;
    }
    if (password.length < 8) {
      setError('密码至少 8 位');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await register(email, nickname, password);
      if (res.code === 0 && res.data) {
        localStorage.setItem('qh_token', res._jwt ?? res.data.access_token);
        localStorage.setItem(
          'qh_user',
          JSON.stringify({
            nickname: res.data.nickname,
            email: res.data.email,
            avatar: res.data.avatar ?? '',
          }),
        );
        localStorage.removeItem('qh_guest_count');
        localStorage.removeItem('qh_guest_session');
        navigate('/chat');
      } else {
        setError(res.message || '注册失败，请重试');
      }
    } catch {
      setError('网络异常，请稍后重试');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-brand-gray flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <img
            src="/logo.svg"
            className="w-20 h-20 drop-shadow-md mx-auto mb-4"
            alt="logo"
          />
          <h1 className="text-2xl font-bold text-brand-ink tracking-wide">
            注册账号
          </h1>
          <p className="text-brand-muted text-sm mt-2">
            注册后无限使用，保存历史对话
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl shadow-sm border border-brand-border p-8 space-y-4"
        >
          {[
            {
              label: '昵称',
              type: 'text',
              value: nickname,
              set: setNickname,
              placeholder: '请输入昵称',
              autocomplete: 'nickname',
              extra: { maxLength: 30 },
            },
            {
              label: '邮箱',
              type: 'email',
              value: email,
              set: setEmail,
              placeholder: '请输入邮箱',
              autocomplete: 'email',
            },
            {
              label: '密码',
              type: 'password',
              value: password,
              set: setPassword,
              placeholder: '至少 8 位',
              autocomplete: 'new-password',
            },
            {
              label: '确认密码',
              type: 'password',
              value: confirmPassword,
              set: setConfirmPassword,
              placeholder: '再次输入密码',
              autocomplete: 'new-password',
            },
          ].map(
            ({ label, type, value, set, placeholder, autocomplete, extra }) => (
              <div key={label}>
                <label className="block text-sm font-medium text-brand-ink mb-1.5">
                  {label}
                </label>
                <input
                  type={type}
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={placeholder}
                  autoComplete={autocomplete}
                  {...extra}
                  className="w-full px-4 py-3 rounded-xl border border-brand-border bg-brand-gray/50 text-brand-ink placeholder-brand-muted/60 focus:outline-none focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue transition text-sm"
                />
              </div>
            ),
          )}

          {error && <p className="text-red-500 text-sm text-center">{error}</p>}

          <button
            type="submit"
            disabled={
              loading || !nickname || !email || !password || !confirmPassword
            }
            className="w-full py-3 rounded-xl bg-brand-blue text-white font-medium text-sm hover:bg-brand-blue-dark disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? '注册中…' : '注册'}
          </button>
        </form>

        <p className="text-center text-sm text-brand-muted mt-5">
          已有账号？{' '}
          <button
            onClick={() => navigate('/login')}
            className="text-brand-blue font-medium hover:underline"
          >
            去登录
          </button>
        </p>

        <p className="text-center text-xs text-brand-muted/60 mt-4">
          本平台仅供健康参考，不构成医疗建议，请咨询专业医生
        </p>
      </div>
    </div>
  );
}
