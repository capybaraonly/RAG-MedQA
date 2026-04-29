import { RagMedQAAvatar } from '@/components/RAG-MedQA-avatar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useChangeLanguage } from '@/hooks/logic-hooks';
import { useFetchUserInfo } from '@/hooks/use-user-setting-request';
import { cn } from '@/lib/utils';
import { Routes } from '@/routes';
import { LucideChevronDown } from 'lucide-react';
import React from 'react';
import { Link, useLocation } from 'react-router';
import GlobalNavbar from './global-navbar';
import ThemeButton from './theme-button';

import { supportedLanguages } from '@/locales/config';

export function Header({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  const { pathname } = useLocation();

  const changeLanguage = useChangeLanguage();

  const {
    data: { language = 'en', avatar, nickname },
  } = useFetchUserInfo();

  const currentLanguage = supportedLanguages.find((x) => x.code === language);

  // const langItems = LanguageList.map((x) => ({
  //   key: x,
  //   label: <span>{LanguageMap[x as keyof typeof LanguageMap]}</span>,
  // }));

  return (
    <header
      key="app-navbar"
      className={cn(
        'w-full grid grid-cols-[1fr_auto_1fr] grid-rows-1 items-center gap-8',
        className,
      )}
      {...props}
    >
      <div className="inline-flex items-center">
        <Link
          to={Routes.Root}
          aria-current={pathname === Routes.Root ? 'page' : undefined}
        >
          <img src={'/logo.svg'} alt="RAG-MedQA logo" className="size-10" />
        </Link>
      </div>

      <GlobalNavbar />

      <div
        className="flex items-center justify-end gap-4 text-text-badge"
        data-testid="auth-status"
      >
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button className="flex items-center gap-1" variant="ghost">
              {currentLanguage?.displayName}
              <LucideChevronDown className="size-[1em]" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent>
            {supportedLanguages.map((x) => (
              <DropdownMenuItem
                key={x.code}
                onClick={() => changeLanguage(x.code)}
              >
                {x.displayName}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <ThemeButton />

        <Link
          to={Routes.UserSetting}
          className="relative ms-3"
          data-testid="settings-entrypoint"
        >
          <RagMedQAAvatar
            name={nickname}
            avatar={avatar}
            isPerson
            className="size-8"
          />
          {/* Temporarily hidden */}
          {/* <Badge className="h-5 w-8 absolute font-normal p-0 justify-center -right-8 -top-2 text-bg-base bg-gradient-to-l from-[#42D7E7] to-[#478AF5]">
            Pro
          </Badge> */}
        </Link>
      </div>
    </header>
  );
}
