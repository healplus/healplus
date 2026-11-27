import { ChevronLeft, ChevronRight, Maximize, Minimize, Moon, Sun, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';

import { useTheme } from '../../app/providers/ThemeProvider';
import { disclaimer } from './slideContent';
import { slides } from './slides';

const SWIPE_THRESHOLD_PX = 60;

function indexFromHash(hash: string) {
  const id = decodeURIComponent(hash.replace(/^#/, ''));
  const index = slides.findIndex(slide => slide.id === id);
  return index >= 0 ? index : 0;
}

function isTypingTarget(target: EventTarget | null) {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
}

export function PresentationPage() {
  const { theme, toggleTheme } = useTheme();
  const [index, setIndex] = useState(() => indexFromHash(window.location.hash));
  const [isFullscreen, setIsFullscreen] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const slide = slides[index];
  const isFirst = index === 0;
  const isLast = index === slides.length - 1;

  const goTo = useCallback((next: number) => {
    setIndex(Math.min(Math.max(next, 0), slides.length - 1));
  }, []);

  // O hash permite retomar a apresentação no mesmo slide após recarregar a página.
  useEffect(() => {
    window.history.replaceState(null, '', `#${slide.id}`);
    document.title = `${slide.label} · Apresentação Heal+`;
  }, [slide]);

  useEffect(() => {
    const onHashChange = () => setIndex(indexFromHash(window.location.hash));
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const onFullscreenChange =() => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen?.();
    } else {
      void document.documentElement.requestFullscreen?.().catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || isTypingTarget(event.target)) return;
      // Botões e links focados tratam Espaço/Enter por conta própria.
      const focusedControl = event.target instanceof HTMLElement && event.target.closest('button, a');

      switch (event.key) {
        case 'ArrowRight':
        case 'PageDown':
          event.preventDefault();
          goTo(index + 1);
          break;
        case ' ':
          if (focusedControl) return;
          event.preventDefault();
          goTo(index + 1);
          break;
        case 'ArrowLeft':
        case 'PageUp':
          event.preventDefault();
          goTo(index - 1);
          break;
        case 'Home':
          event.preventDefault();
          goTo(0);
          break;
        case 'End':
          event.preventDefault();
          goTo(slides.length - 1);
          break;
        case 'f':
        case 'F':
          toggleFullscreen();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [goTo, index, toggleFullscreen]);

  const onTouchStart = (event: React.TouchEvent) => {
    touchStartX.current = event.touches[0]?.clientX ?? null;
  };

  const onTouchEnd = (event: React.TouchEvent) => {
    const start = touchStartX.current;
    const end = event.changedTouches[0]?.clientX;
    touchStartX.current = null;
    if (start === null || end === undefined) return;
    const delta = end - start;
    if (Math.abs(delta) < SWIPE_THRESHOLD_PX) return;
    goTo(delta < 0 ? index + 1 : index - 1);
  };

  const controlClass =
    'inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 transition-colors hover:border-heal-blue/50 hover:text-heal-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heal-blue disabled:cursor-not-allowed disabled:opacity-40 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-200';

  return (
    <div
      className="flex h-dvh flex-col overflow-hidden bg-white text-slate-950 dark:bg-[#111111] dark:text-white"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <header className="flex shrink-0 items-center justify-between gap-4 px-5 py-4 md:px-10">
        <div className="flex items-center gap-3">
          <img src="/images/Logo_final_modobranco.png" alt="Heal+" className="h-8 w-auto object-contain md:h-9" />
          <span className="hidden border-l border-slate-300 pl-3 text-xs font-bold uppercase tracking-[0.18em] text-slate-500 dark:border-white/15 dark:text-slate-400 sm:inline">
            Conecta CPS
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={toggleTheme} className={controlClass} aria-label={theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}>
            {theme === 'dark' ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={toggleFullscreen}
            className={controlClass}
            aria-label={isFullscreen ? 'Sair da tela cheia' : 'Abrir em tela cheia'}
            aria-pressed={isFullscreen}
          >
            {isFullscreen ? <Minimize className="h-5 w-5" aria-hidden="true" /> : <Maximize className="h-5 w-5" aria-hidden="true" />}
          </button>
          <Link to="/" className={controlClass} aria-label="Encerrar apresentação e voltar ao início">
            <X className="h-5 w-5" aria-hidden="true" />
          </Link>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-6 md:px-10 lg:px-16" aria-roledescription="apresentação" aria-label="Apresentação Heal+">
        <section
          key={slide.id}
          aria-roledescription="slide"
          aria-label={`${index + 1} de ${slides.length}: ${slide.label}`}
          className="mx-auto my-auto w-full max-w-7xl motion-safe:animate-fade-in"
        >
          {slide.render()}
        </section>
      </main>

      <footer className="shrink-0 border-t border-slate-200 px-5 py-4 dark:border-white/10 md:px-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">{disclaimer}</p>
          <nav aria-label="Navegação entre slides" className="flex items-center justify-between gap-3 md:justify-end">
            <button type="button" onClick={() => goTo(index - 1)} disabled={isFirst} className={controlClass} aria-label="Slide anterior">
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
            <ol className="flex items-center gap-1.5">
              {slides.map((item, itemIndex) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => goTo(itemIndex)}
                    aria-label={`Ir para o slide ${itemIndex + 1}: ${item.label}`}
                    aria-current={itemIndex === index ? 'step' : undefined}
                    className="flex h-6 items-center px-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heal-blue"
                  >
                    <span
                      className={`block h-2 rounded-full transition-all ${
                        itemIndex === index ? 'w-7 bg-heal-blue' : 'w-2 bg-slate-300 hover:bg-heal-blue/60 dark:bg-white/20'
                      }`}
                    />
                  </button>
                </li>
              ))}
            </ol>
            <span className="min-w-[3.5rem] text-center text-sm font-bold tabular-nums text-slate-500 dark:text-slate-400" aria-live="polite">
              {index + 1}/{slides.length}
            </span>
            <button type="button" onClick={() => goTo(index + 1)} disabled={isLast} className={controlClass} aria-label="Próximo slide">
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </nav>
        </div>
      </footer>
    </div>
  );
}
