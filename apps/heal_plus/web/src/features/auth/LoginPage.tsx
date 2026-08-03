import { Eye, EyeOff, Github, Mail } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import {
  AUTH_FIELD_CLASS,
  AuthProviderButton,
  AuthShowcaseLayout
} from '../../components/layout/AuthShowcaseLayout';
import { GoogleIcon, MicrosoftIcon } from '../../components/ui/auth-provider-icons';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  consumeLogoutNotice,
  friendlyAuthError,
  resetPassword,
  signInWithEmail,
  signInWithGoogle
} from './authService';

export function LoginPage() {
  const { user } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(() => consumeLogoutNotice());
  const [resetSent, setResetSent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    setError(current => current ?? consumeLogoutNotice());
  }, []);

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setResetSent(false);
    setLoading(true);

    try {
      await signInWithEmail(email, password);
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setGoogleLoading(true);

    try {
      await signInWithGoogle();
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleResetPassword = async () => {
    setError(null);
    setResetSent(false);

    if (!email.trim()) {
      setError('Informe seu e-mail profissional para recuperar a senha.');
      return;
    }

    try {
      await resetPassword(email.trim());
      setResetSent(true);
    } catch (err) {
      setError(friendlyAuthError(err));
    }
  };

  const busy = loading || googleLoading;

  return (
    <AuthShowcaseLayout
      title="Acesse sua conta"
      subtitle="Continue sua jornada clínica no Heal+"
      variant="login"
    >
      <div className="mt-12 grid grid-cols-3 gap-2.5">
        <AuthProviderButton
          icon={<GoogleIcon />}
          loading={googleLoading}
          onClick={handleGoogleSignIn}
        >
          Google
        </AuthProviderButton>
        <AuthProviderButton icon={<Github className="h-4 w-4" aria-hidden="true" />} disabled>
          GitHub
        </AuthProviderButton>
        <AuthProviderButton icon={<MicrosoftIcon />} disabled>
          Microsoft
        </AuthProviderButton>
      </div>

      <div className="relative my-7">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200 dark:border-white/[0.08]" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-4 text-[10px] font-bold uppercase tracking-wide text-cyan-700 dark:bg-[#111111] dark:text-[#73a8d8]">
            ou continue com e-mail
          </span>
        </div>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <Input
          id="login-email"
          label="E-mail profissional"
          type="email"
          autoComplete="email"
          value={email}
          onChange={event => setEmail(event.target.value)}
          placeholder="nome@instituicao.org"
          icon={<Mail className="h-4 w-4" />}
          className={AUTH_FIELD_CLASS}
          required
          disabled={busy}
        />

        <Input
          id="login-password"
          label="Senha"
          type={showPassword ? 'text' : 'password'}
          autoComplete="current-password"
          value={password}
          onChange={event => setPassword(event.target.value)}
          placeholder="Digite sua senha"
          endAdornment={
            <button
              type="button"
              onClick={() => setShowPassword(show => !show)}
              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              className="rounded-md p-1 text-slate-500 transition-colors hover:text-slate-950 dark:hover:text-white"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          className={AUTH_FIELD_CLASS}
          required
          disabled={busy}
        />

        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleResetPassword}
            disabled={busy}
            className="text-xs font-bold text-cyan-700 transition-colors hover:text-[#0A4D68] disabled:opacity-50 dark:text-[#73baf7] dark:hover:text-white"
          >
            Esqueceu a senha?
          </button>
        </div>

        {error ? (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {resetSent ? (
          <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-800 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200">
            Enviamos as instruções de recuperação para o e-mail informado.
          </div>
        ) : null}

        <Button
          type="submit"
          size="lg"
          className="w-full !h-12 !rounded-lg !bg-[#0A4D68] !text-sm !font-extrabold !text-white hover:!bg-[#083D54] dark:!bg-slate-100 dark:!text-slate-950 dark:hover:!bg-white"
          isLoading={loading}
          disabled={busy}
        >
          Entrar
        </Button>
      </form>

      <p className="mt-8 text-center text-xs font-medium text-slate-600 dark:text-[#a7b8d5]">
        Ainda não tem uma conta?{' '}
        <Link to="/register" className="font-extrabold text-[#0A4D68] hover:underline dark:text-white">
          Criar conta
        </Link>
      </p>
      <p className="mt-4 text-center text-[11px] leading-5 text-slate-500">
        Use apenas sua conta profissional. Não compartilhe credenciais nem informações clínicas fora do ambiente autorizado.
      </p>
    </AuthShowcaseLayout>
  );
}
