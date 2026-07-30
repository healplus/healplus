import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import type { ThemePreference } from '../../lib/types';
import { Sidebar } from './sidebar';
import { Topbar } from './Topbar';
import { ClinicalBreadcrumbs, currentClinicalRouteLabel } from './ClinicalBreadcrumbs';

export function AppShell() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { profile } = useAuth();
  const { setTheme } = useTheme();
  const { pathname } = useLocation();
  const lastSyncedTheme = useRef<ThemePreference | null>(null);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const profileTheme = profile?.settings?.theme;
    if (!profileTheme || profileTheme === lastSyncedTheme.current) return;
    lastSyncedTheme.current = profileTheme;
    setTheme(profileTheme);
  }, [profile?.settings?.theme, setTheme]);

  useEffect(() => {
    const label = currentClinicalRouteLabel(pathname);
    document.title = `${label} | Heal+`;
    mainRef.current?.focus({ preventScroll: true });
  }, [pathname]);

  return (
    <div className="min-h-screen bg-white dark:bg-[#0c0c0e] text-heal-ink dark:text-zinc-200 antialiased flex flex-col md:flex-row">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />

      <div className="flex-1 flex flex-col lg:pl-[280px] min-w-0">
        <div className="lg:hidden">
          <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
        </div>

        <ClinicalBreadcrumbs />
        <p aria-live="polite" className="sr-only">
          Página atual: {currentClinicalRouteLabel(pathname)}
        </p>
        <main
          className="flex-grow flex flex-col min-w-0 outline-none"
          ref={mainRef}
          tabIndex={-1}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
