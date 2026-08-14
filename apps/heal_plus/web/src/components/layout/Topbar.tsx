import { Bell, Menu } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { UserAvatar } from '../profile/UserAvatar';

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { user, profile } = useAuth();
  const displayName = profile?.displayName || user?.displayName || user?.email || '';
  const photoURL = profile?.photoURL || user?.photoURL;

  return (
    <header
      aria-label="Cabeçalho móvel"
      className="fixed inset-x-0 top-0 z-40 flex min-h-16 shrink-0 items-center gap-3 border-b border-heal-line bg-white/95 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] shadow-sm backdrop-blur-xl sm:px-6 lg:hidden dark:border-zinc-800 dark:bg-zinc-950/95"
    >
      <button
        type="button"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-heal-ink transition-colors hover:bg-slate-100 dark:text-white dark:hover:bg-zinc-800"
        onClick={onMenuClick}
      >
        <span className="sr-only">Abrir sidebar</span>
        <Menu className="h-6 w-6" strokeWidth={1.8} aria-hidden="true" />
      </button>

      <span className="min-w-0 flex-1" aria-hidden="true" />

      <Link
        to="/notifications"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-heal-ink transition-colors hover:bg-slate-100 dark:text-white dark:hover:bg-zinc-800"
      >
        <span className="sr-only">Notificações</span>
        <Bell className="h-[22px] w-[22px]" strokeWidth={1.8} aria-hidden="true" />
      </Link>

      <Link to="/profile" aria-label="Perfil profissional" className="shrink-0 rounded-full">
        <UserAvatar
          name={displayName}
          src={photoURL}
          imageClassName="h-10 w-10 rounded-full bg-heal-canvas object-cover ring-2 ring-heal-line/50 transition-all hover:ring-heal-blue/30"
          fallbackClassName="flex h-10 w-10 items-center justify-center rounded-full bg-heal-softBlue text-sm font-bold text-heal-blue ring-2 ring-heal-blue/10 transition-all hover:ring-heal-blue/30 dark:bg-blue-950/40"
        />
      </Link>
    </header>
  );
}
