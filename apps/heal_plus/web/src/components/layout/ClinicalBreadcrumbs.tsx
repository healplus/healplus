import { useLocation } from 'react-router';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

function routeBreadcrumbs(pathname: string): BreadcrumbItem[] {
  if (pathname === '/dashboard') return [{ label: 'Dashboard' }];
  if (pathname === '/chat') return [{ label: 'Assistente' }];
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
  // Breadcrumb navigation bar is disabled globally per user request
  return null;
}
