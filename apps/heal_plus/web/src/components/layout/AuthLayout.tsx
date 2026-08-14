import { ArrowLeft, Check, LockKeyhole, Moon, ShieldCheck, Stethoscope, Sun } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

import { useTheme } from '../../app/providers/ThemeProvider';
import { BorderBeam, MagicBackdrop } from '../ui/magic-surface';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
  eyebrow?: string;
}

const assurances = [
  {
    icon: LockKeyhole,
    title: 'Acesso protegido',
    text: 'Autenticação profissional e dados isolados por usuário.'
  },
  {
    icon: Stethoscope,
    title: 'Apoio, não diagnóstico',
    text: 'A análise complementa — e não substitui — a avaliação clínica.'
  },
  {
    icon: ShieldCheck,
    title: 'Privacidade por padrão',
    text: 'Informações sensíveis tratadas somente para a finalidade assistencial.'
  }
];

export function AuthLayout({ children, title, subtitle, eyebrow = 'Portal clínico seguro' }: AuthLayoutProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-slate-50 px-4 py-4 text-slate-950 transition-colors dark:bg-[#03060b] dark:text-white sm:px-6 sm:py-6 lg:px-8">
      <MagicBackdrop />

      <div className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col sm:min-h-[calc(100vh-3rem)]">
        <header className="flex items-center justify-between pb-5">
          <Link to="/" className="group inline-flex items-center gap-2 rounded-full px-2 py-2 text-sm font-bold text-slate-600 transition-colors hover:text-cyan-700 dark:text-slate-300 dark:hover:text-heal-blue">
            <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" aria-hidden="true" />
            Voltar para o início
          </Link>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white/70 text-slate-600 backdrop-blur transition-colors hover:border-heal-blue/50 hover:text-heal-blue dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </header>

        <section className="grid flex-1 overflow-hidden rounded-[2rem] border border-slate-200 bg-white/80 shadow-[0_32px_100px_rgba(2,132,199,0.14)] backdrop-blur-xl dark:border-white/10 dark:bg-[#080d15]/90 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="relative hidden overflow-hidden border-r border-slate-200 bg-slate-950 p-10 text-white dark:border-white/10 lg:flex lg:flex-col lg:justify-between">
            <MagicBackdrop className="opacity-70" />
            <div className="relative">
              <Link to="/" aria-label="Heal+ — início" className="inline-flex items-center gap-3">
                <img src="/images/Logo_final_modobranco.png" alt="Heal+" className="h-10 w-auto" />
                <span className="border-l border-white/15 pl-3 text-[10px] font-extrabold uppercase tracking-[0.2em] text-slate-400">REDI-SUS</span>
              </Link>
              <p className="mt-16 text-xs font-extrabold uppercase tracking-[0.22em] text-heal-blue">Cuidado inteligente</p>
              <h2 className="mt-4 max-w-md font-headline text-5xl font-extrabold leading-[1.08] tracking-[-0.045em]">
                Contexto clínico para uma evolução mais clara.
              </h2>
              <p className="mt-6 max-w-md text-base leading-8 text-slate-300">
                Registre, compare e documente o acompanhamento de feridas em uma jornada longitudinal preparada para a rotina profissional.
              </p>
            </div>

            <div className="relative mt-12 space-y-3">
              {assurances.map(item => (
                <div key={item.title} className="flex gap-4 rounded-2xl border border-white/10 bg-white/[0.055] p-4 backdrop-blur-sm">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-heal-blue/15 text-heal-blue"><item.icon className="h-5 w-5" /></span>
                  <div><p className="text-sm font-extrabold">{item.title}</p><p className="mt-1 text-xs leading-5 text-slate-400">{item.text}</p></div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-center p-5 sm:p-10 lg:p-12">
            <div className="w-full max-w-md">
              <div className="mb-8 text-center lg:text-left">
                <Link to="/" aria-label="Heal+ — início" className="mb-7 inline-flex items-center lg:hidden">
                  <img src={theme === 'dark' ? '/images/Logo_final_modobranco.png' : '/images/logo_final.png'} alt="Heal+" className="h-10 w-auto" />
                </Link>
                <div className="inline-flex items-center gap-2 rounded-full border border-heal-blue/25 bg-heal-blue/10 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.18em] text-cyan-800 dark:text-heal-blue">
                  <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  {eyebrow}
                </div>
                <h1 className="mt-5 font-headline text-4xl font-extrabold tracking-[-0.045em] text-slate-950 dark:text-white">{title}</h1>
                <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-400">{subtitle}</p>
              </div>

              <div className="magic-card auth-form relative rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-soft dark:border-white/10 dark:bg-white/[0.035] sm:p-7">
                <BorderBeam />
                <div className="relative">{children}</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
