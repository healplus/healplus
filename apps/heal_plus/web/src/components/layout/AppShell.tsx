import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import type { ThemePreference } from '../../lib/types';
import { Sidebar } from './sidebar';
import { Topbar } from './Topbar';
import { currentClinicalRouteLabel } from './ClinicalBreadcrumbs';

export interface AppShellContext {
  isSidebarCollapsed: boolean;
  setIsSidebarCollapsed: (collapsed: boolean | ((prev: boolean) => boolean)) => void;
  onToggleSidebar: () => void;
}

export function AppShell() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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
    <div className="h-screen w-full overflow-hidden bg-white dark:bg-[#0c0c0e] text-heal-ink dark:text-zinc-200 antialiased flex flex-col md:flex-row">
      {!isSidebarCollapsed && (
        <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      )}

      <div
        className={`flex-1 flex flex-col min-w-0 h-full overflow-hidden transition-[padding] duration-300 ${
          isSidebarCollapsed ? '' : 'lg:pl-[280px]'
        }`}
      >
        <div className={`lg:hidden shrink-0 ${isSidebarCollapsed ? 'hidden' : ''}`}>
          <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
        </div>

        <p aria-live="polite" className="sr-only">
          Página atual: {currentClinicalRouteLabel(pathname)}
        </p>
        <main
          className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden outline-none"
          ref={mainRef}
          tabIndex={-1}
        >
          <Outlet
            context={{
              isSidebarCollapsed,
              setIsSidebarCollapsed,
              onToggleSidebar: () => setIsSidebarCollapsed((prev) => !prev)
            }}
          />
        </main>
      </div>
    </div>
  );
}
