import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const supabaseMocks = vi.hoisted(() => {
  const auth = {
    signInWithPassword: vi.fn(),
    signUp: vi.fn(),
    signOut: vi.fn(),
    getSession: vi.fn(),
    getUser: vi.fn(),
    resetPasswordForEmail: vi.fn(),
    signInWithOAuth: vi.fn()
  };

  const from = vi.fn();

  return { auth, from };
});

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: supabaseMocks.auth,
    from: supabaseMocks.from
  }
}));

import {
  consumeLogoutNotice,
  logout,
  LogoutError,
  resetPassword,
  signInWithEmail
} from '../../features/auth/authService';
import {
  AI_CREDENTIAL_STORAGE_PREFIX,
  CHAT_HISTORY_STORAGE_PREFIX
} from '../../features/auth/sessionLifecycle';

function supabaseUser(id = 'user-a') {
  return {
    id,
    email: 'profissional@example.test',
    user_metadata: { full_name: 'Profissional' },
    app_metadata: { providers: ['email'] }
  };
}

describe('serviço de autenticação', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    vi.stubEnv('VITE_CLINICAL_API_URL', '');

    supabaseMocks.auth.getUser.mockResolvedValue({
      data: { user: supabaseUser() }
    });

    const maybeSingle = vi.fn().mockResolvedValue({
      data: { uid: 'user-a' },
      error: null
    });
    const selectEq = vi.fn(() => ({ maybeSingle }));
    const select = vi.fn(() => ({ eq: selectEq }));
    const updateEq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn(() => ({ eq: updateEq }));
    supabaseMocks.from.mockReturnValue({ select, update });
  });

  it('conclui login válido e sincroniza o perfil', async () => {
    const authenticatedUser = supabaseUser();
    supabaseMocks.auth.signInWithPassword.mockResolvedValue({
      data: { user: authenticatedUser, session: {} },
      error: null
    });

    const result = await signInWithEmail('profissional@example.test', 'senha-valida');

    expect(result).toEqual(authenticatedUser);
    expect(supabaseMocks.auth.signInWithPassword).toHaveBeenCalledWith({
      email: 'profissional@example.test',
      password: 'senha-valida'
    });
    expect(supabaseMocks.from).toHaveBeenCalledWith('users');
  });

  it('recusa login inválido sem consultar dados de perfil', async () => {
    supabaseMocks.auth.signInWithPassword.mockResolvedValue({
      data: { user: null, session: null },
      error: { message: 'Invalid login credentials' }
    });

    await expect(
      signInWithEmail('profissional@example.test', 'senha-incorreta')
    ).rejects.toMatchObject({ message: 'Invalid login credentials' });
    expect(supabaseMocks.from).not.toHaveBeenCalled();
  });

  it('não revela se o e-mail de recuperação existe', async () => {
    supabaseMocks.auth.resetPasswordForEmail.mockResolvedValue({
      error: { message: 'User not found' }
    });

    await expect(resetPassword('nao-existe@example.test')).resolves.toBeUndefined();
  });

  it('revoga no servidor, limpa dados sensíveis e encerra a sessão local', async () => {
    supabaseMocks.auth.getSession.mockResolvedValue({
      data: { session: { access_token: 'supabase-token' } }
    });
    supabaseMocks.auth.signOut.mockResolvedValue({ error: null });

    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'segredo');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'historico');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'legado');

    const fetchMock = vi.fn().mockImplementation(async () => {
      expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
      expect(supabaseMocks.auth.signOut).not.toHaveBeenCalled();
      return { ok: true, status: 204 };
    });
    vi.stubGlobal('fetch', fetchMock);

    await logout();

    expect(fetchMock).toHaveBeenCalledWith('/api/clinical/auth/logout', {
      method: 'POST',
      headers: { Authorization: 'Bearer supabase-token' },
      credentials: 'same-origin'
    });
    expect(supabaseMocks.auth.signOut).toHaveBeenCalled();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
  });

  it('mantém a limpeza local quando a revogação remota falha', async () => {
    supabaseMocks.auth.getSession.mockResolvedValue({
      data: { session: { access_token: 'supabase-token' } }
    });
    supabaseMocks.auth.signOut.mockResolvedValue({ error: null });

    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'segredo');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    await expect(logout()).rejects.toMatchObject({
      localSessionClosed: true
    });

    expect(supabaseMocks.auth.signOut).toHaveBeenCalled();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(consumeLogoutNotice()).toContain('não foi possível confirmar');
  });

  it.each([200, 401, 503])(
    'não aceita status %s como confirmação de revogação',
    async status => {
      supabaseMocks.auth.getSession.mockResolvedValue({
        data: { session: { access_token: 'supabase-token' } }
      });
      supabaseMocks.auth.signOut.mockResolvedValue({ error: null });

      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: status < 400, status }));

      await expect(logout()).rejects.toBeInstanceOf(LogoutError);
      expect(consumeLogoutNotice()).toContain('não foi possível confirmar');
    }
  );

  it('usa a URL clínica configurada em produção e exige resposta 204', async () => {
    supabaseMocks.auth.getSession.mockResolvedValue({
      data: { session: { access_token: 'supabase-token' } }
    });
    supabaseMocks.auth.signOut.mockResolvedValue({ error: null });

    vi.stubEnv('VITE_CLINICAL_API_URL', 'https://api.example.test/api/v1/');
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal('fetch', fetchMock);

    await logout();

    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/auth/logout',
      expect.any(Object)
    );
  });

  it('mantém a pessoa na sessão quando o sign-out local falha', async () => {
    supabaseMocks.auth.getSession.mockResolvedValue({
      data: { session: { access_token: 'supabase-token' } }
    });
    supabaseMocks.auth.signOut.mockRejectedValueOnce(new Error('local persistence unavailable'));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 204 }));

    await expect(logout()).rejects.toMatchObject({
      localSessionClosed: false
    });
    expect(consumeLogoutNotice()).toBeNull();
  });
});
