import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Github, Mail, User as UserIcon } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useNavigate } from 'react-router';

import { useAuth } from '../../app/providers/AuthProvider';
import {
  AUTH_FIELD_CLASS,
  AuthProviderButton,
  AuthShowcaseLayout
} from '../../components/layout/AuthShowcaseLayout';
import { GoogleIcon, MicrosoftIcon } from '../../components/ui/auth-provider-icons';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { friendlyAuthError, registerWithEmail, signInWithGoogle } from './authService';
import { registerSchema, type RegisterFormValues } from './authSchema';

export function RegisterPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [socialLoading, setSocialLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { acceptedTerms: false }
  });

  if (user) return <Navigate to="/dashboard" replace />;

  const onSubmit = async (values: RegisterFormValues) => {
    setError('');
    try {
      await registerWithEmail(values);
      navigate('/onboarding');
    } catch (err) {
      setError(friendlyAuthError(err));
    }
  };

  const handleGoogle = async () => {
    setError('');
    setSocialLoading(true);
    try {
      await signInWithGoogle();
      navigate('/dashboard');
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setSocialLoading(false);
    }
  };

  const busy = isSubmitting || socialLoading;

  return (
    <AuthShowcaseLayout
      title="Crie sua conta"
      subtitle="Comece sua jornada clínica no Heal+"
      variant="register"
    >
      <div className="mt-8 grid grid-cols-3 gap-2.5">
        <AuthProviderButton icon={<GoogleIcon />} loading={socialLoading} onClick={handleGoogle}>
          Google
        </AuthProviderButton>
        <AuthProviderButton icon={<Github className="h-4 w-4" aria-hidden="true" />} disabled>
          GitHub
        </AuthProviderButton>
        <AuthProviderButton icon={<MicrosoftIcon />} disabled>
          Microsoft
        </AuthProviderButton>
      </div>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200 dark:border-white/[0.08]" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-4 text-[10px] font-bold uppercase tracking-wide text-heal-blue dark:bg-[#111111] dark:text-[#73a8d8]">
            ou continue com e-mail
          </span>
        </div>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <Input
          label="Nome profissional"
          placeholder="Seu nome"
          autoComplete="name"
          icon={<UserIcon className="h-4 w-4" />}
          error={errors.displayName?.message}
          className={AUTH_FIELD_CLASS}
          {...register('displayName')}
          disabled={busy}
        />

        <Input
          label="Endereço de e-mail"
          type="email"
          placeholder="voce@instituicao.org"
          autoComplete="email"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          className={AUTH_FIELD_CLASS}
          {...register('email')}
          disabled={busy}
        />

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Senha"
            type={showPassword ? 'text' : 'password'}
            placeholder="Mínimo 6 caracteres"
            autoComplete="new-password"
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
            error={errors.password?.message}
            className={AUTH_FIELD_CLASS}
            {...register('password')}
            disabled={busy}
          />

          <Input
            label="Confirmar senha"
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Repita a senha"
            autoComplete="new-password"
            endAdornment={
              <button
                type="button"
                onClick={() => setShowConfirmPassword(show => !show)}
                aria-label={showConfirmPassword ? 'Ocultar confirmação de senha' : 'Mostrar confirmação de senha'}
                className="rounded-md p-1 text-slate-500 transition-colors hover:text-slate-950 dark:hover:text-white"
              >
                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
            error={errors.confirmPassword?.message}
            className={AUTH_FIELD_CLASS}
            {...register('confirmPassword')}
            disabled={busy}
          />
        </div>

        <div className="flex items-start gap-2.5 pt-1 text-xs text-slate-600 dark:text-slate-400">
          <input
            type="checkbox"
            id="terms"
            className="mt-0.5 h-4 w-4 rounded border-slate-300 bg-white text-heal-blue focus:ring-heal-blue dark:border-white/15 dark:bg-[#191919]"
            disabled={busy}
            {...register('acceptedTerms')}
          />
          <label htmlFor="terms" className="leading-5">
            Concordo com os Termos de Uso e a{' '}
            <Link to="/privacy" className="font-bold text-heal-blue hover:underline dark:text-[#73baf7]">
              Política de Privacidade
            </Link>
            .
          </label>
        </div>
        {errors.acceptedTerms?.message ? (
          <p className="text-xs font-bold text-red-700 dark:text-red-400">{errors.acceptedTerms.message}</p>
        ) : null}

        {error ? (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200">
            {error}
          </div>
        ) : null}

        <Button
          type="submit"
          className="w-full !h-12 !rounded-lg !text-sm !font-extrabold"
          size="lg"
          isLoading={isSubmitting}
          disabled={busy}
        >
          Criar conta
        </Button>
      </form>

      <p className="mt-6 text-center text-xs font-medium text-slate-600 dark:text-[#73a8d8]">
        Já tem uma conta?{' '}
        <Link to="/login" className="font-extrabold text-heal-blue hover:underline dark:text-white">
          Entrar
        </Link>
      </p>
    </AuthShowcaseLayout>
  );
}
