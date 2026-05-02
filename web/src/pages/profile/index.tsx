import {
  changePassword,
  getStoredUser,
  logout,
  updateNickname,
} from '@/services/api';
import { useState } from 'react';
import { useNavigate } from 'react-router';

export default function ProfilePage() {
  const navigate = useNavigate();
  const user = getStoredUser();

  const [nickname, setNickname] = useState(user?.nickname || '');
  const [nicknameMsg, setNicknameMsg] = useState('');
  const [savingNickname, setSavingNickname] = useState(false);

  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [pwdMsg, setPwdMsg] = useState('');
  const [savingPwd, setSavingPwd] = useState(false);

  const initial = (user?.nickname || user?.email || '?')[0].toUpperCase();

  async function handleNickname(e: React.FormEvent) {
    e.preventDefault();
    if (!nickname.trim()) return;
    setSavingNickname(true);
    setNicknameMsg('');
    const ok = await updateNickname(nickname.trim());
    if (ok) {
      const stored = getStoredUser();
      if (stored) {
        localStorage.setItem(
          'qh_user',
          JSON.stringify({ ...stored, nickname: nickname.trim() }),
        );
      }
      setNicknameMsg('保存成功');
    } else {
      setNicknameMsg('保存失败，请重试');
    }
    setSavingNickname(false);
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault();
    if (!oldPwd || !newPwd || !confirmPwd) return;
    if (newPwd !== confirmPwd) {
      setPwdMsg('两次密码不一致');
      return;
    }
    if (newPwd.length < 8) {
      setPwdMsg('新密码至少 8 位');
      return;
    }
    setSavingPwd(true);
    setPwdMsg('');
    const { ok, message } = await changePassword(oldPwd, newPwd);
    setPwdMsg(ok ? '密码修改成功' : message || '修改失败');
    if (ok) {
      setOldPwd('');
      setNewPwd('');
      setConfirmPwd('');
    }
    setSavingPwd(false);
  }

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-qh-cream">
      {/* Header */}
      <header className="bg-white border-b border-qh-border px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate('/chat')}
          className="flex items-center gap-1.5 text-sm text-qh-brown hover:text-qh-ink transition"
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
          返回
        </button>
        <h1 className="text-base font-semibold text-qh-ink">个人信息</h1>
      </header>

      <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
        {/* Avatar */}
        <div className="bg-white rounded-2xl border border-qh-border p-6 flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-qh-green flex items-center justify-center text-white text-2xl font-bold shrink-0">
            {initial}
          </div>
          <div>
            <div className="font-semibold text-qh-ink text-base">
              {user?.nickname || '—'}
            </div>
            <div className="text-sm text-qh-brown mt-0.5">{user?.email}</div>
          </div>
        </div>

        {/* Nickname */}
        <form
          onSubmit={handleNickname}
          className="bg-white rounded-2xl border border-qh-border p-6 space-y-4"
        >
          <h2 className="font-semibold text-qh-ink text-sm">修改昵称</h2>
          <input
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder="请输入昵称"
            maxLength={30}
            className="w-full px-4 py-2.5 rounded-xl border border-qh-border bg-qh-cream/50 text-qh-ink text-sm focus:outline-none focus:ring-2 focus:ring-qh-green/40 focus:border-qh-green transition"
          />
          {nicknameMsg && (
            <p
              className={`text-xs ${nicknameMsg.includes('成功') ? 'text-qh-green' : 'text-red-500'}`}
            >
              {nicknameMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={savingNickname || !nickname.trim()}
            className="px-5 py-2 rounded-xl bg-qh-green text-white text-sm font-medium hover:bg-qh-green-dark disabled:opacity-50 transition"
          >
            {savingNickname ? '保存中…' : '保存'}
          </button>
        </form>

        {/* Change password */}
        <form
          onSubmit={handlePassword}
          className="bg-white rounded-2xl border border-qh-border p-6 space-y-4"
        >
          <h2 className="font-semibold text-qh-ink text-sm">修改密码</h2>
          {[
            {
              label: '当前密码',
              value: oldPwd,
              set: setOldPwd,
              placeholder: '请输入当前密码',
            },
            {
              label: '新密码',
              value: newPwd,
              set: setNewPwd,
              placeholder: '至少 8 位',
            },
            {
              label: '确认新密码',
              value: confirmPwd,
              set: setConfirmPwd,
              placeholder: '再次输入新密码',
            },
          ].map(({ label, value, set, placeholder }) => (
            <div key={label}>
              <label className="block text-xs text-qh-brown mb-1">
                {label}
              </label>
              <input
                type="password"
                value={value}
                onChange={(e) => set(e.target.value)}
                placeholder={placeholder}
                className="w-full px-4 py-2.5 rounded-xl border border-qh-border bg-qh-cream/50 text-qh-ink text-sm focus:outline-none focus:ring-2 focus:ring-qh-green/40 focus:border-qh-green transition"
              />
            </div>
          ))}
          {pwdMsg && (
            <p
              className={`text-xs ${pwdMsg.includes('成功') ? 'text-qh-green' : 'text-red-500'}`}
            >
              {pwdMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={savingPwd || !oldPwd || !newPwd || !confirmPwd}
            className="px-5 py-2 rounded-xl bg-qh-green text-white text-sm font-medium hover:bg-qh-green-dark disabled:opacity-50 transition"
          >
            {savingPwd ? '修改中…' : '修改密码'}
          </button>
        </form>

        {/* Logout */}
        <div className="bg-white rounded-2xl border border-qh-border p-6">
          <button
            onClick={handleLogout}
            className="px-5 py-2 rounded-xl border border-red-200 text-red-500 text-sm font-medium hover:bg-red-50 transition"
          >
            退出登录
          </button>
        </div>
      </div>
    </div>
  );
}
