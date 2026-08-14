import { useState } from 'react';
import {
  Bot,
  Building2,
  CalendarDays,
  ClipboardList,
  FileBarChart,
  GitCompareArrows,
  LayoutDashboard,
  LogOut,
  MoreHorizontal,
  ScanSearch,
  Settings,
  User as UserIcon,
  Users,
  X
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { LogoutError, logout } from '../../features/auth/authService';
import { UserAvatar } from '../profile/UserAvatar';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isDesktopHidden?: boolean;
}

type RouteMatch = 'exact' | 'prefix';

interface NavItemConfig {
  to: string;
  label: string;
  icon: LucideIcon;
  match?: RouteMatch;
}

/* ──────────────────────────────────────────────
   Navigation items — flat list like DevDeck
   ────────────────────────────────────────────── */

const navItems: NavItemConfig[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, match: 'exact' },
  { to: '/patients', label: 'Pacientes', icon: Users, match: 'prefix' },
  { to: '/evaluations/new', label: 'Avaliações', icon: ClipboardList, match: 'exact' },
  { to: '/agenda', label: 'Agenda', icon: CalendarDays, match: 'exact' },
  { to: '/reports', label: 'Relatórios', icon: FileBarChart, match: 'exact' },
  { to: '/chat', label: 'Assistente', icon: Bot, match: 'exact' },
  { to: '/profile', label: 'Perfil', icon: UserIcon, match: 'prefix' }
];

/* Items inside the "Mais" dropdown */
const moreMenuItems: NavItemConfig[] = [
  { to: '/reports/compare', label: 'Comparar evolução', icon: GitCompareArrows, match: 'exact' },
  { to: '/analyzer', label: 'HEAL Analyzer', icon: ScanSearch, match: 'exact' },
  { to: '/settings', label: 'Configurações', icon: Settings, match: 'exact' }
];

const mobileDrawerItems: NavItemConfig[] = [
  ...navItems.slice(5),
  ...moreMenuItems
];

/* ──────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────── */

function normalizePath(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

function isRouteActive(pathname: string, item: NavItemConfig) {
  const current = normalizePath(pathname);
  const target = normalizePath(item.to);
  if ((item.match ?? 'exact') === 'prefix') {
    return current === target || current.startsWith(`${target}/`);
  }
  return current === target;
}

/* ──────────────────────────────────────────────
   NavLink — Twitter-style sidebar link
   ────────────────────────────────────────────── */

function NavLink({ item, onClick }: { item: NavItemConfig; onClick?: () => void }) {
  const { pathname } = useLocation();
  const active = isRouteActive(pathname, item);
  const Icon = item.icon;

  return (
    <Link
      to={item.to}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={`group flex items-center gap-3.5 py-2.5 px-3.5 rounded-xl text-sm font-semibold transition-all duration-200 border w-full cursor-pointer ${
        active
          ? 'bg-transparent text-heal-ink dark:text-white font-black border-transparent'
          : 'text-heal-muted border-transparent hover:bg-heal-surfaceHover dark:hover:bg-zinc-900 hover:text-heal-ink dark:hover:text-white dark:text-zinc-400'
      }`}
    >
      <div className="relative flex items-center justify-center w-5 h-5">
        <Icon
          className={`w-5 h-5 transition-transform group-hover:scale-105 duration-200 ${
            active
              ? 'text-heal-blue dark:text-blue-400'
              : 'text-heal-muted dark:text-zinc-400'
          }`}
        />
      </div>
      <span>{item.label}</span>
    </Link>
  );
}

/* ──────────────────────────────────────────────
   User Profile Widget (bottom of sidebar)
   ────────────────────────────────────────────── */

function UserProfileWidget({ onSignOut }: { onSignOut: () => void }) {
  const { user, profile } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const displayName = profile?.displayName || user?.displayName || user?.email || 'Usuário';
  const photoURL = profile?.photoURL || user?.photoURL;
  const email = profile?.email || user?.email || '';

  if (!user) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setDropdownOpen(!dropdownOpen)}
        aria-haspopup="menu"
        aria-expanded={dropdownOpen}
        className="group w-full flex items-center justify-between p-3 rounded-2xl border border-transparent hover:border-heal-line dark:hover:border-zinc-800 hover:bg-heal-surfaceHover/60 dark:hover:bg-zinc-900/60 transition-all duration-200 cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0 flex-grow">
          <UserAvatar
            name={displayName}
            src={photoURL}
            imageClassName="w-10 h-10 rounded-full object-cover border border-heal-line dark:border-zinc-700 shrink-0"
            fallbackClassName="w-10 h-10 rounded-full bg-heal-softBlue dark:bg-blue-950/40 text-heal-blue flex items-center justify-center text-sm font-bold border border-heal-blue/10 shrink-0"
          />
          <div className="text-left min-w-0 flex-grow">
            <p className="text-sm font-bold text-heal-ink dark:text-white truncate leading-tight">
              {displayName}
            </p>
            <p className="text-[11px] text-heal-muted dark:text-zinc-500 font-medium truncate leading-none mt-1" title={email}>
              {email}
            </p>
          </div>
        </div>
        <MoreHorizontal className="w-5 h-5 text-heal-muted dark:text-zinc-500 shrink-0 transition-colors duration-200 group-hover:text-heal-ink dark:group-hover:text-white" />
      </button>

      {/* Dropdown menu */}
      {dropdownOpen && (
        <>
          <button
            type="button"
            aria-label="Fechar menu da conta"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setDropdownOpen(false)}
          />
          <div
            role="menu"
            className="absolute bottom-full left-0 z-50 mb-3 w-[min(288px,calc(100vw-2rem))] overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white p-2.5 shadow-[0_18px_44px_rgba(15,23,42,0.18)] animate-slide-up dark:border-[#2f3336] dark:bg-[#16181c] dark:shadow-[0_18px_44px_rgba(0,0,0,0.45)]"
          >
            <Link
              to="/profile"
              role="menuitem"
              className="flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-[13.5px] font-extrabold text-slate-800 transition-colors hover:bg-slate-100 dark:text-[#e7e9ea] dark:hover:bg-white/[0.06]"
              onClick={() => setDropdownOpen(false)}
            >
              <UserIcon className="h-[21.5px] w-[21.5px] shrink-0" strokeWidth={2.1} />
              Meu Perfil
            </Link>
            <Link
              to="/settings"
              role="menuitem"
              className="flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-[13.5px] font-extrabold text-slate-800 transition-colors hover:bg-slate-100 dark:text-[#e7e9ea] dark:hover:bg-white/[0.06]"
              onClick={() => setDropdownOpen(false)}
            >
              <Settings className="h-[21.5px] w-[21.5px] shrink-0" strokeWidth={2.1} />
              Configurações
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setDropdownOpen(false);
                onSignOut();
              }}
              className="flex w-full items-center gap-3.5 rounded-2xl px-4 py-3.5 text-left text-[13.5px] font-extrabold text-red-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-[#ff4545] dark:hover:bg-red-500/10 cursor-pointer"
            >
              <LogOut className="h-[21.5px] w-[21.5px] shrink-0" strokeWidth={2.1} />
              <span>Sair da Conta</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────
   Desktop Sidebar Content
   ────────────────────────────────────────────── */

function MoreDropdown({ onNavigate }: { onNavigate?: () => void }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const active = moreMenuItems.some(item => isRouteActive(pathname, item));

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`group flex items-center gap-3.5 py-2.5 px-3.5 rounded-xl text-sm font-semibold transition-all duration-200 border w-full cursor-pointer ${
          active
            ? 'text-heal-ink dark:text-white font-black border-transparent'
            : 'text-heal-muted border-transparent hover:bg-heal-surfaceHover dark:hover:bg-zinc-900 hover:text-heal-ink dark:hover:text-white dark:text-zinc-400'
        }`}
      >
        <div className="relative flex items-center justify-center w-5 h-5">
          <MoreHorizontal className={`w-5 h-5 transition-transform group-hover:scale-105 duration-200 ${active ? 'text-heal-blue' : 'text-heal-muted dark:text-zinc-400'}`} />
        </div>
        <span>Mais</span>
      </button>

      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-label="Fechar menu Mais"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute left-0 top-full z-50 mt-3 w-[min(288px,calc(100vw-2rem))] overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white p-2.5 shadow-[0_18px_44px_rgba(15,23,42,0.18)] animate-slide-down dark:border-[#2f3336] dark:bg-[#16181c] dark:shadow-[0_18px_44px_rgba(0,0,0,0.45)]"
          >
            {moreMenuItems.map(item => {
              const Icon = item.icon;
              const itemActive = isRouteActive(pathname, item);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  role="menuitem"
                  className={`flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-[13.5px] font-extrabold transition-colors ${
                    itemActive
                      ? 'bg-heal-softBlue/55 text-heal-blue dark:bg-white/[0.06] dark:text-heal-blue'
                      : 'text-slate-800 hover:bg-slate-100 dark:text-[#e7e9ea] dark:hover:bg-white/[0.06]'
                  }`}
                  onClick={() => { setOpen(false); onNavigate?.(); }}
                >
                  <Icon className="h-[21.5px] w-[21.5px] shrink-0" strokeWidth={2.1} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function SidebarContent({
  onNavigate,
  variant = 'desktop'
}: {
  onNavigate?: () => void;
  variant?: 'desktop' | 'mobile';
}) {
  const { profile } = useAuth();
  const [logoutError, setLogoutError] = useState<string | null>(null);

  const handleSignOut = async () => {
    setLogoutError(null);
    try {
      await logout();
      window.location.href = '/login';
    } catch (error) {
      if (error instanceof LogoutError && error.localSessionClosed) {
        window.location.href = '/login';
        return;
      }
      setLogoutError(
        error instanceof Error
          ? error.message
          : 'Não foi possível encerrar a sessão. Tente novamente.'
      );
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col justify-between bg-white p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-[max(1.25rem,env(safe-area-inset-top))] select-none dark:bg-zinc-950 lg:pb-5 lg:pt-5">
      <div className="space-y-5">
        {/* Logo */}
        <Link to="/dashboard" className="flex items-center px-3 py-1 group w-fit mb-2">
          <img
            src="/images/Logo_final_modobranco.png"
            alt="Heal+"
            className="h-11 w-auto object-contain group-hover:scale-105 transition-transform duration-300"
          />
        </Link>

        {/* Navigation — flat list like DevDeck */}
        <nav className="flex flex-col gap-0.5">
          {(variant === 'mobile' ? mobileDrawerItems : navItems).map(item => (
            <NavLink key={item.to} item={item} onClick={onNavigate} />
          ))}
          {variant === 'desktop' ? <MoreDropdown onNavigate={onNavigate} /> : null}
        </nav>
      </div>

      {/* Footer: user profile widget and institution */}
      <div className="shrink-0 space-y-2.5">
        <hr className="border-heal-line dark:border-zinc-800 mb-2" />
        {profile?.clinicName && (
          <div className="flex items-center gap-3 px-3.5 py-2 text-sm font-semibold text-heal-muted dark:text-zinc-400">
            <Building2 className="w-5 h-5 text-heal-muted dark:text-zinc-400 shrink-0" />
            <span className="truncate" title={profile.clinicName}>{profile.clinicName}</span>
          </div>
        )}
        {logoutError && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300" role="alert">
            {logoutError}
          </p>
        )}
        <UserProfileWidget onSignOut={handleSignOut} />
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────
   Mobile Bottom Nav (Twitter-style)
   ────────────────────────────────────────────── */

const mobileNavItems = navItems.slice(0, 5); // Dashboard, Pacientes, Avaliações, Agenda, Relatórios

function MobileBottomNav() {
  const { pathname } = useLocation();

  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-40 flex min-h-[72px] items-center justify-around border-t border-heal-line bg-white/95 px-4 pb-[max(0.625rem,env(safe-area-inset-bottom))] pt-2.5 shadow-[0_-12px_30px_rgba(15,23,42,0.08)] backdrop-blur-md lg:hidden dark:border-zinc-800 dark:bg-zinc-950/95 dark:shadow-[0_-12px_30px_rgba(0,0,0,0.28)]"
    >
      {mobileNavItems.map(item => {
        const Icon = item.icon;
        const active = isRouteActive(pathname, item);

        return (
          <Link
            key={item.to}
            to={item.to}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
            className={`flex flex-col items-center justify-center p-1.5 transition-colors duration-150 ${
              active
                ? 'text-heal-blue font-black'
                : 'text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white'
            }`}
          >
            <div className="relative flex items-center justify-center">
              <Icon className={`w-[22px] h-[22px] ${active ? 'text-heal-blue' : ''}`} />
            </div>
          </Link>
        );
      })}
    </nav>
  );
}

/* ──────────────────────────────────────────────
   Sidebar Export (Desktop + Mobile)
   ────────────────────────────────────────────── */

export function Sidebar({ isOpen, setIsOpen, isDesktopHidden = false }: SidebarProps) {
  return (
    <>
      {/* Desktop sidebar — fixed, Twitter-style */}
      <aside className={`${isDesktopHidden ? 'lg:hidden' : 'lg:flex'} hidden h-screen w-[280px] flex-col border-r border-heal-line bg-white dark:border-zinc-800 dark:bg-zinc-950 lg:fixed lg:inset-y-0 lg:z-40`}>
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {isOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
            aria-label="Fechar menu"
            onClick={() => setIsOpen(false)}
          />
          <aside aria-label="Menu móvel" className="relative h-full w-[min(86vw,320px)] min-w-[280px] border-r border-heal-line dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-lg">
            <button
              type="button"
              className="absolute right-3 top-[max(0.75rem,env(safe-area-inset-top))] z-10 rounded-xl bg-white/80 p-2 text-heal-muted shadow-sm dark:bg-zinc-900"
              onClick={() => setIsOpen(false)}
              aria-label="Fechar sidebar"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setIsOpen(false)} variant="mobile" />
          </aside>
        </div>
      ) : null}

      {/* Mobile bottom navigation bar */}
      <MobileBottomNav />
    </>
  );
}
