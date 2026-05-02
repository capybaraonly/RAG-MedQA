import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router';

const spinner = (
  <div className="fixed inset-0 flex items-center justify-center bg-qh-cream">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-qh-green border-t-transparent" />
  </div>
);

const lazy_ = (importer: () => Promise<{ default: React.ComponentType }>) => {
  const C = lazy(importer);
  return () => (
    <Suspense fallback={spinner}>
      <C />
    </Suspense>
  );
};

const LandingPage = lazy_(() => import('@/pages/landing'));
const LoginPage = lazy_(() => import('@/pages/login'));
const RegisterPage = lazy_(() => import('@/pages/register'));
const ChatPage = lazy_(() => import('@/pages/chat'));
const ProfilePage = lazy_(() => import('@/pages/profile'));

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!localStorage.getItem('qh_token')) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export const routers = createBrowserRouter(
  [
    { path: '/', element: <LandingPage /> },
    { path: '/login', element: <LoginPage /> },
    { path: '/register', element: <RegisterPage /> },
    {
      path: '/chat',
      element: (
        <RequireAuth>
          <ChatPage />
        </RequireAuth>
      ),
    },
    {
      path: '/profile',
      element: (
        <RequireAuth>
          <ProfilePage />
        </RequireAuth>
      ),
    },
    { path: '*', element: <Navigate to="/" replace /> },
  ],
  { basename: import.meta.env.VITE_BASE_URL || '/' },
);
