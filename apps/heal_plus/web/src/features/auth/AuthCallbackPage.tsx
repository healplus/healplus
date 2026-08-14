import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { supabase } from '../../lib/supabase';
import { ensureUserProfile } from './authService';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { Loader } from '../../components/ui/Loader';

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Supabase client automatically picks up the code/hash from the URL
        // and exchanges it for a session when the page loads.
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) throw sessionError;

        if (session?.user) {
          await ensureUserProfile(session.user.id).catch(() => undefined);
          navigate('/dashboard', { replace: true });
        } else {
          // Session may not be ready yet; wait for the auth state change.
          const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event, newSession) => {
              if (event === 'SIGNED_IN' && newSession?.user) {
                subscription.unsubscribe();
                await ensureUserProfile(newSession.user.id).catch(() => undefined);
                navigate('/dashboard', { replace: true });
              }
            }
          );

          // Timeout fallback
          setTimeout(() => {
            subscription.unsubscribe();
            setError('Tempo esgotado ao processar autenticação. Tente novamente.');
          }, 10_000);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Falha ao processar autenticação. Tente novamente.'
        );
      }
    };

    void handleCallback();
  }, [navigate]);

  if (error) {
    return (
      <AuthLayout title="Erro de autenticação" subtitle="Não foi possível concluir o login.">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-950/30">
          <p className="text-sm font-medium text-red-800 dark:text-red-300">{error}</p>
        </div>
        <a
          href="/login"
          className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-heal-blue hover:text-heal-blueDark transition-colors"
        >
          Voltar para o login
        </a>
      </AuthLayout>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-heal-softBlue text-slate-950 dark:bg-[#111111] dark:text-white">
      <Loader />
    </main>
  );
}
