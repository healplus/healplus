import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const firebaseMocks = vi.hoisted(() => {
  class Provider {
    setCustomParameters = vi.fn();
    addScope = vi.fn();
  }

  return {
    auth: { currentUser: null as null | { uid: string; getIdToken: () => Promise<string> } },
    createUserWithEmailAndPassword: vi.fn(),
    sendPasswordResetEmail: vi.fn(),
    signInWithEmailAndPassword: vi.fn(),
    signInWithPopup: vi.fn(),
    signInWithRedirect: vi.fn(),
    signOut: vi.fn(),
    updateProfile: vi.fn(),
    GoogleAuthProvider: Provider,
    OAuthProvider: Provider
  };
});

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn()
}));

vi.mock('firebase/auth', () => ({
  createUserWithEmailAndPassword: firebaseMocks.createUserWithEmailAndPassword,
  GoogleAuthProvider: firebaseMocks.GoogleAuthProvider,
  OAuthProvider: firebaseMocks.OAuthProvider,
  sendPasswordResetEmail: firebaseMocks.sendPasswordResetEmail,
  signInWithEmailAndPassword: firebaseMocks.signInWithEmailAndPassword,
  signInWithPopup: firebaseMocks.signInWithPopup,
  signInWithRedirect: firebaseMocks.signInWithRedirect,
  signOut: firebaseMocks.signOut,
  updateProfile: firebaseMocks.updateProfile
}));

vi.mock('../../lib/firebase', () => ({
  auth: firebaseMocks.auth
}));

vi.mock('../../lib/supabase', () => ({
  supabase: {
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

function user(uid = 'user-a') {
  return {
    uid,
    displayName: 'Profissional',
    email: 'profissional@example.test',
    photoURL: null,
    providerData: [],
    getIdToken: vi.fn().mockResolvedValue('firebase-id-token')
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
    firebaseMocks.auth.currentUser = null;

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
    const authenticatedUser = user();
    firebaseMocks.signInWithEmailAndPassword.mockResolvedValue({
      user: authenticatedUser
    });

    await expect(
      signInWithEmail('profissional@example.test', 'senha-valida')
    ).resolves.toBe(authenticatedUser);

    expect(firebaseMocks.signInWithEmailAndPassword).toHaveBeenCalledWith(
      firebaseMocks.auth,
      'profissional@example.test',
      'senha-valida'
    );
    expect(supabaseMocks.from).toHaveBeenCalledWith('users');
  });

  it('recusa login inválido sem consultar dados de perfil', async () => {
    firebaseMocks.signInWithEmailAndPassword.mockRejectedValue({
      code: 'auth/invalid-credential'
    });

    await expect(
      signInWithEmail('profissional@example.test', 'senha-incorreta')
    ).rejects.toMatchObject({ code: 'auth/invalid-credential' });
    expect(supabaseMocks.from).not.toHaveBeenCalled();
  });

  it('não revela se o e-mail de recuperação existe', async () => {
    firebaseMocks.sendPasswordResetEmail.mockRejectedValue({
      code: 'auth/user-not-found'
    });

    await expect(resetPassword('nao-existe@example.test')).resolves.toBeUndefined();
  });

  it('revoga no servidor, limpa dados sensíveis e encerra a sessão local', async () => {
    const authenticatedUser = user();
    firebaseMocks.auth.currentUser = authenticatedUser;
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'segredo');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'historico');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'legado');
    const fetchMock = vi.fn().mockImplementation(async () => {
      expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
      expect(firebaseMocks.signOut).toHaveBeenCalledWith(firebaseMocks.auth);
      return { ok: true, status: 204 };
    });
    vi.stubGlobal('fetch', fetchMock);

    await logout();

    expect(fetchMock).toHaveBeenCalledWith('/api/clinical/auth/logout', {
      method: 'POST',
      headers: { Authorization: 'Bearer firebase-id-token' },
      credentials: 'same-origin'
    });
    expect(firebaseMocks.signOut).toHaveBeenCalledWith(firebaseMocks.auth);
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
  });

  it('mantém a limpeza local quando a revogação remota falha', async () => {
    firebaseMocks.auth.currentUser = user();
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'segredo');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    await expect(logout()).rejects.toMatchObject({
      localSessionClosed: true
    });

    expect(firebaseMocks.signOut).toHaveBeenCalledWith(firebaseMocks.auth);
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(consumeLogoutNotice()).toContain('não foi possível confirmar');
  });

  it.each([200, 401, 503])(
    'não aceita status %s como confirmação de revogação',
    async status => {
      firebaseMocks.auth.currentUser = user();
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: status < 400, status }));

      await expect(logout()).rejects.toBeInstanceOf(LogoutError);
      expect(consumeLogoutNotice()).toContain('não foi possível confirmar');
    }
  );

  it('usa a URL clínica configurada em produção e exige resposta 204', async () => {
    firebaseMocks.auth.currentUser = user();
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
    firebaseMocks.auth.currentUser = user();
    firebaseMocks.signOut.mockRejectedValueOnce(new Error('local persistence unavailable'));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 204 }));

    await expect(logout()).rejects.toMatchObject({
      localSessionClosed: false
    });
    expect(consumeLogoutNotice()).toBeNull();
  });
});
