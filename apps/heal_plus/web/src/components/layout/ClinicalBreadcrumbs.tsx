import { ChevronRight } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

function routeBreadcrumbs(pathname: string): BreadcrumbItem[] {
  if (pathname === '/dashboard') return [{ label: 'Dashboard' }];
  if (pathname === '/patients') return [{ label: 'Pacientes' }];
  if (/^\/patients\/[^/]+$/.test(pathname)) {
    return [{ label: 'Pacientes', to: '/patients' }, { label: 'Registro atual' }];
  }
  if (pathname === '/evaluations/new') {
    return [
      { label: 'Pacientes', to: '/patients' },
      { label: 'Nova avaliação' }
    ];
  }
  if (pathname === '/agenda') return [{ label: 'Agenda' }];
  if (pathname === '/reports') return [{ label: 'Relatórios' }];
  if (pathname === '/reports/compare') {
    return [{ label: 'Relatórios', to: '/reports' }, { label: 'Comparar evolução' }];
  }
  if (pathname === '/profile') return [{ label: 'Perfil' }];
  if (pathname === '/profile/edit') {
    return [{ label: 'Perfil', to: '/profile' }, { label: 'Editar' }];
  }
  if (pathname === '/settings') return [{ label: 'Configurações' }];
  if (pathname === '/notifications') return [{ label: 'Notificações' }];
  if (pathname === '/privacy') return [{ label: 'Privacidade' }];
  if (pathname === '/about') return [{ label: 'Sobre' }];
  return [{ label: 'Área clínica' }];
}

export function currentClinicalRouteLabel(pathname: string): string {
  return routeBreadcrumbs(pathname).at(-1)?.label ?? 'Área clínica';
}

export function ClinicalBreadcrumbs() {
  const { pathname } = useLocation();
  const items = routeBreadcrumbs(pathname);

  return (
    <nav
      aria-label="Navegação estrutural"
      className="border-b border-heal-line bg-heal-canvas/80 px-4 py-2 text-xs text-heal-muted dark:border-zinc-800 dark:bg-zinc-950/70 dark:text-zinc-400 sm:px-6"
    >
      <ol className="mx-auto flex w-full max-w-[1440px] items-center gap-1.5">
        {items.map((item, index) => (
          <li className="flex min-w-0 items-center gap-1.5" key={`${item.label}-${index}`}>
            {index > 0 ? <ChevronRight aria-hidden="true" className="h-3 w-3 shrink-0" /> : null}
            {item.to ? (
              <Link className="truncate font-semibold hover:text-heal-blue" to={item.to}>
                {item.label}
              </Link>
            ) : (
              <span aria-current="page" className="truncate font-bold text-heal-ink dark:text-white">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
