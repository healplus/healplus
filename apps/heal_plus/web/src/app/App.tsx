import { Outlet, useLocation } from 'react-router';

import { AuthConfigError } from '../components/layout/AuthConfigError';
import { isSupabaseConfigured } from '../lib/supabase';

export function App() {
  const location = useLocation();
  const localAnalyzerMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';
  const standaloneAnalyzer = localAnalyzerMode && location.pathname === '/analyzer';
  const publicRoute = ['/', '/referencias', '/login', '/register', '/forgot-password'].includes(location.pathname);

  if (!isSupabaseConfigured && !standaloneAnalyzer && !publicRoute) return <AuthConfigError />;
  return <Outlet />;
}
