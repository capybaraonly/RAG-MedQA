import { RagMedQAAvatar } from '@/components/RAG-MedQA-avatar';
import ThemeSwitch from '@/components/theme-switch';
import { Button } from '@/components/ui/button';
import { Domain } from '@/constants/common';
import { useLogout } from '@/hooks/use-login-request';
import {
  useFetchSystemVersion,
  useFetchUserInfo,
} from '@/hooks/use-user-setting-request';
import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { TFunction } from 'i18next';
import { LucideBox, LucideUser } from 'lucide-react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useHandleMenuClick } from './hooks';

const menuItems = (t: TFunction) => [
  {
    icon: <LucideBox className="size-[1em]" />,
    label: t('setting.model'),
    key: Routes.Model,
    'data-testid': 'settings-nav-model-providers',
  },
  {
    icon: <LucideUser className="size-[1em]" />,
    label: t('setting.profile'),
    key: Routes.Profile,
  },
];

export function SideBar() {
  const { data: userInfo } = useFetchUserInfo();
  const { handleMenuClick, active: activeItemKey } = useHandleMenuClick();
  const { version, fetchSystemVersion } = useFetchSystemVersion();
  const { t } = useTranslation();
  useEffect(() => {
    if (location.host !== Domain) {
      fetchSystemVersion();
    }
  }, [fetchSystemVersion]);
  const { logout } = useLogout();

  return (
    <aside className="w-[303px] bg-bg-base flex flex-col">
      <header>
        <h1 className="px-6 flex gap-2.5 items-center font-normal">
          <RagMedQAAvatar
            avatar={userInfo?.avatar}
            name={userInfo?.nickname}
            isPerson
          />

          <p className="text-sm text-text-primary">{userInfo?.email}</p>
        </h1>
      </header>

      <nav className="flex-1 overflow-auto mt-4 py-1">
        <ul className="px-6 flex flex-col gap-5">
          {menuItems(t).map((item) => {
            const { key, icon, label, ...rest } = item;

            return (
              <li key={key}>
                <Button
                  {...rest}
                  block
                  variant="ghost"
                  className={cn(
                    'justify-start gap-2.5 px-3 relative h-10 text-base',
                    activeItemKey === key && 'bg-bg-card text-text-primary',
                  )}
                  onClick={handleMenuClick(key)}
                >
                  <section className="flex items-center gap-2.5">
                    {icon}
                    <span>{label}</span>
                  </section>
                </Button>
              </li>
            );
          })}
        </ul>
      </nav>

      <footer className="p-6 mt-auto">
        <div className="flex items-center gap-2 mb-6 justify-between">
          <span className="text-xs text-accent-primary">{version}</span>

          <ThemeSwitch />
        </div>

        <Button block size="lg" variant="transparent" onClick={() => logout()}>
          {t('setting.logout')}
        </Button>
      </footer>
    </aside>
  );
}
