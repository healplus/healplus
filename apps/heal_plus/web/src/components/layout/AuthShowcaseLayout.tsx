import { ArrowLeft, Loader2, Moon, ShieldCheck, Sun } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { useTheme } from '../../app/providers/ThemeProvider';
import bgGlassUrl from '../../assets/brand/bg-glass-3.png';

interface AuthShowcaseLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  variant?: 'login' | 'register';
}

interface AuthProviderButtonProps {
  children: string;
  icon: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
}

export const AUTH_FIELD_CLASS =
  '[&_label]:mb-2 [&_label]:text-[13px] [&_label]:font-medium [&_label]:text-slate-800 [&_input]:h-[49px] [&_input]:rounded-md [&_input]:border-slate-200 [&_input]:bg-white [&_input]:text-slate-950 [&_input]:placeholder:text-slate-400 hover:[&_input]:border-slate-300 focus-within:[&_input]:border-[#469cff] dark:[&_label]:text-white dark:[&_input]:border-white/[0.06] dark:[&_input]:bg-[#1a1a1a] dark:[&_input]:text-white dark:[&_input]:placeholder:text-[#9db0cf] dark:hover:[&_input]:border-white/10';

export function AuthProviderButton({
  children,
  icon,
  disabled,
  loading,
  onClick
}: AuthProviderButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      title={disabled ? `${children}: em breve` : undefined}
      className="inline-flex h-9 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-200 bg-slate-50 px-1.5 text-[9px] font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45 dark:border-white/[0.06] dark:bg-[#1a1a1a] dark:text-white/85 dark:hover:border-white/15 dark:hover:bg-[#202020] sm:gap-2 sm:px-2 sm:text-[10px]"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : icon}
      <span>{children}</span>
      {disabled ? <span className="sr-only">— em breve</span> : null}
    </button>
  );
}

export function AuthShowcaseLayout({
  title,
  subtitle,
  children,
  variant = 'register'
}: AuthShowcaseLayoutProps) {
  const isLogin = variant === 'login';
  const { theme, toggleTheme } = useTheme();

  return (
    <main className="min-h-svh bg-white font-sans text-slate-950 antialiased transition-colors dark:bg-[#111111] dark:text-white">
      <div className="grid min-h-svh w-full lg:grid-cols-[53%_47%]">
        <aside
          className="relative m-3 mr-0 hidden min-h-[calc(100svh-24px)] overflow-hidden rounded-xl bg-cover bg-center lg:flex lg:items-center lg:justify-center"
          style={{ backgroundImage: `url(${bgGlassUrl})` }}
          aria-label="Apresentação do Heal+"
        >
          <div className="relative z-10 flex w-full -translate-y-[1.5%] flex-col items-center px-10 text-center">
            <Link
              to="/"
              aria-label="Heal+ — voltar ao início"
              className="rounded-lg transition-transform motion-safe:hover:scale-[1.02]"
            >
              <img
                src="/images/Logo_final_modobranco.png"
                alt="Heal+"
                className="h-[62px] w-auto object-contain"
              />
            </Link>
            <h2 className="mt-8 max-w-[560px] font-headline text-[32px] font-semibold leading-[1.14] tracking-[-0.045em] text-white [text-shadow:0_2px_9px_rgba(0,0,0,0.25)] xl:text-[36px]">
              Cuidado inteligente.<br />Evolução visível.
            </h2>
            <p className="mt-7 max-w-xl text-[17px] font-medium tracking-[-0.025em] text-white/85 [text-shadow:0_2px_9px_rgba(0,0,0,0.25)]">
              Acompanhe cada etapa com contexto clínico, evidência e segurança.
            </p>
          </div>
          <div className="absolute bottom-6 left-1/2 z-10 inline-flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full border border-white/15 bg-black/25 px-4 py-2 text-xs font-bold text-blue-50 backdrop-blur-md">
            <ShieldCheck className="h-4 w-4 text-[#52c7f5]" aria-hidden="true" />
            Ambiente profissional do ecossistema REDI-SUS
          </div>
        </aside>

        <section
          className={`relative flex min-h-svh min-w-0 items-start justify-center bg-[radial-gradient(circle_at_50%_0%,rgba(65,182,230,0.10),transparent_32%),#ffffff] px-8 transition-colors dark:bg-[radial-gradient(circle_at_50%_0%,rgba(0,120,255,0.12),transparent_32%),#111111] sm:px-12 lg:bg-white lg:px-[clamp(3rem,5.4vw,4rem)] dark:lg:bg-[#111111] ${
            isLogin ? 'py-10 lg:pb-8 lg:pt-[11vh]' : 'py-8 lg:py-[8vh]'
          }`}
        >
          <Link
            to="/"
            className="absolute left-5 top-4 hidden items-center gap-2 rounded-lg px-2 py-2 text-xs font-bold text-slate-500 transition-colors hover:text-slate-950 dark:hover:text-white lg:inline-flex"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Início
          </Link>

          <button
            type="button"
            onClick={toggleTheme}
            className="absolute right-5 top-4 inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100 hover:text-[#0A4D68] dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-[#6cd6ff]"
            aria-label={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
            title={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
          >
            {theme === 'dark' ? <Sun className="h-[17px] w-[17px]" /> : <Moon className="h-[17px] w-[17px]" />}
          </button>

          <div className="w-full max-w-[466px]">
            <Link
              to="/"
              aria-label="Heal+ — voltar ao início"
              className={`inline-flex lg:hidden ${isLogin ? 'mb-10' : 'mb-8'}`}
            >
              <img
                src="/images/Logo_final_modobranco.png"
                alt="Heal+"
                className="h-[38px] w-auto object-contain"
              />
            </Link>

            <div className="text-center">
              <h1 className="font-headline text-[28px] font-semibold leading-tight tracking-[-0.045em] text-slate-950 dark:text-white">
                {title}
              </h1>
              <p className="mt-3 text-[15px] text-[#9cb6df]">{subtitle}</p>
            </div>

            {children}
          </div>
        </section>
      </div>
    </main>
  );
}
