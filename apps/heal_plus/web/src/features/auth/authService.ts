import { supabase } from '../../lib/supabase';
import type { UserProfile } from '../../lib/types';
import type { LoginFormValues, RegisterFormValues } from './authSchema';
import { clearSensitiveSessionState } from './sessionLifecycle';

const LOGOUT_NOTICE_STORAGE_KEY = 'healplus-logout-notice';
const REMOTE_LOGOUT_ERROR =
  'A sessão local foi encerrada, mas não foi possível confirmar a invalidação no servidor. Revogue o acesso da conta no provedor antes de usar um dispositivo compartilhado.';

export class LogoutError extends Error {
  constructor(
    message: string,
    readonly localSessionClosed: boolean
  ) {
    super(message);
    this.name = 'LogoutError';
  }
}

function clinicalApiBaseUrl(): string | null {
  const configuredUrl = import.meta.env.VITE_CLINICAL_API_URL?.trim();
  if (configuredUrl) return configuredUrl.replace(/\/+$/, '');
  return import.meta.env.DEV ? '/api/clinical' : null;
}

function saveLogoutNotice(message: string): void {
  try {
    window.sessionStorage.setItem(LOGOUT_NOTICE_STORAGE_KEY, message);
  } catch {
    // A falha em persistir o aviso não deve restaurar uma sessão já encerrada.
  }
}

export function consumeLogoutNotice(): string | null {
  try {
    const message = window.sessionStorage.getItem(LOGOUT_NOTICE_STORAGE_KEY);
    window.sessionStorage.removeItem(LOGOUT_NOTICE_STORAGE_KEY);
    return message;
  } catch {
    return null;
  }
}

const defaultSettings: UserProfile['settings'] = {
  theme: 'light',
  notificationsEnabled: true,
  emailNotificationsEnabled: true,
  agendaRemindersEnabled: true,
  hideEmailPreview: false,
  showProfilePhoto: true
};

export function friendlyAuthError(error: unknown) {
  if (typeof error === 'object' && error && 'message' in error) {
    const message = String((error as { message: string }).message).toLowerCase();

    if (message.includes('invalid login credentials') || message.includes('invalid_credentials'))
      return 'E-mail ou senha incorretos.';
    if (message.includes('email not confirmed'))
      return 'Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada.';
    if (message.includes('user already registered') || message.includes('already been registered'))
      return 'Não foi possível criar a conta com os dados informados.';
    if (message.includes('weak_password') || message.includes('at least'))
      return 'Use uma senha mais forte.';
    if (message.includes('rate_limit') || message.includes('too many'))
      return 'Muitas tentativas. Aguarde alguns minutos.';
    if (message.includes('network') || message.includes('fetch'))
      return 'Falha de rede. Verifique sua conexão.';
    if (message.includes('popup') || message.includes('cancelled'))
      return 'Login cancelado antes da conclusão.';
  }
  return 'Não foi possível concluir a autenticação. Tente novamente.';
}

export async function ensureUserProfile(
  userId: string,
  extras: Partial<UserProfile> = {}
) {
  const { data: profileSnap, error: fetchError } = await supabase
    .from('users')
    .select('*')
    .eq('uid', userId)
    .maybeSingle();

  if (fetchError) throw new Error(fetchError.message);

  const { data: { user: authUser } } = await supabase.auth.getUser();

  const baseProfile = {
    uid: userId,
    display_name: extras.displayName || authUser?.user_metadata?.full_name || authUser?.email?.split('@')[0] || 'Profissional',
    email: extras.email || authUser?.email || '',
    photo_url: extras.photoURL ?? authUser?.user_metadata?.avatar_url ?? null,
    provider_ids: authUser?.app_metadata?.providers ?? [],
    role: 'professional',
    settings: extras.settings || defaultSettings
  };

  if (!profileSnap) {
    const { error: insertError } = await supabase
      .from('users')
      .insert({
        ...baseProfile,
        professional_area: extras.professionalArea || '',
        clinic_name: extras.clinicName || '',
        phone: extras.phone || '',
        onboarding_completed: extras.onboardingCompleted ?? false
      });
    if (insertError) throw new Error(insertError.message);
    return;
  }

  const { error: updateError } = await supabase
    .from('users')
    .update({
      display_name: baseProfile.display_name,
      email: baseProfile.email,
      photo_url: baseProfile.photo_url,
      provider_ids: baseProfile.provider_ids,
      updated_at: new Date().toISOString()
    })
    .eq('uid', userId);

  if (updateError) throw new Error(updateError.message);
}

export async function signInWithEmail(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  await ensureUserProfile(data.user.id);
  return data.user;
}

export async function signUpWithEmail(name: string, email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: name } }
  });
  if (error) throw error;
  if (!data.user) throw new Error('Cadastro efetuado, mas a conta requer confirmação de e-mail.');
  await ensureUserProfile(data.user.id, { displayName: name, email, onboardingCompleted: false });
  return data.user;
}

export async function signInWithGoogle() {
  const redirectTo = `${window.location.origin}/auth/callback`;
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo,
      queryParams: { prompt: 'select_account' }
    }
  });
  if (error) throw error;
  // The browser will redirect to Google. No return value needed.
}

export async function resetPassword(email: string): Promise<void> {
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/login`
  });
  // Do not reveal whether the email exists.
  if (error && !error.message.toLowerCase().includes('rate_limit')) {
    // Swallow user-not-found style errors for security.
    return;
  }
  if (error) throw error;
}

export async function logout(): Promise<void> {
  let token: string | null = null;
  let invalidationFailed = false;
  let localSignOutFailed = false;
  const apiBaseUrl = clinicalApiBaseUrl();

  // Remove clinical state and BYOK credentials before any network round-trip.
  clearSensitiveSessionState();

  try {
    const { data: { session } } = await supabase.auth.getSession();
    token = session?.access_token ?? null;
  } catch {
    invalidationFailed = true;
  }

  if (token && apiBaseUrl) {
    try {
      const response = await fetch(`${apiBaseUrl}/auth/logout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        },
        credentials: 'same-origin'
      });
      invalidationFailed = response.status !== 204;
    } catch {
      invalidationFailed = true;
    }
  }

  try {
    const result = await supabase.auth.signOut();
    if (result?.error) localSignOutFailed = true;
  } catch {
    localSignOutFailed = true;
  }

  if (localSignOutFailed) {
    throw new LogoutError(
      'Não foi possível encerrar a sessão neste dispositivo. Verifique sua conexão e tente novamente.',
      false
    );
  }

  if (invalidationFailed) {
    saveLogoutNotice(REMOTE_LOGOUT_ERROR);
    throw new LogoutError(REMOTE_LOGOUT_ERROR, true);
  }
}

export async function updateUserProfile(uid: string, values: Partial<UserProfile>) {
  const { data: existingProfile, error: fetchError } = await supabase
    .from('users')
    .select('uid')
    .eq('uid', uid)
    .maybeSingle();

  if (fetchError) throw new Error(fetchError.message);

  if (!existingProfile) {
    // Older deployed schemas can reject a partial upsert because required
    // profile columns have no compatible defaults.
    await ensureUserProfile(uid, values);
  }

  const payload: Record<string, any> = {
    updated_at: new Date().toISOString()
  };
  if ('displayName' in values) payload.display_name = values.displayName;
  if ('email' in values) payload.email = values.email;
  if ('photoURL' in values) payload.photo_url = values.photoURL;
  if ('providerIds' in values) payload.provider_ids = values.providerIds;
  if ('role' in values) payload.role = values.role;
  if ('settings' in values) payload.settings = values.settings;
  if ('professionalArea' in values) payload.professional_area = values.professionalArea;
  if ('clinicName' in values) payload.clinic_name = values.clinicName;
  if ('phone' in values) payload.phone = values.phone;
  if ('onboardingCompleted' in values) payload.onboarding_completed = values.onboardingCompleted;

  const { error } = await supabase
    .from('users')
    .update(payload)
    .eq('uid', uid);

  if (error) throw new Error(error.message);
}

export const loginWithEmail = (values: LoginFormValues) => signInWithEmail(values.email, values.password);
export const registerWithEmail = (values: RegisterFormValues) => signUpWithEmail(values.displayName, values.email, values.password);
