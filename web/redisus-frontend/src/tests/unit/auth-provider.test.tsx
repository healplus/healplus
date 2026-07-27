import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AI_CREDENTIAL_STORAGE_PREFIX,
  CHAT_HISTORY_STORAGE_PREFIX
} from '../../features/auth/sessionLifecycle';

const firebaseState = vi.hoisted(() => ({
  configured: false,
  listener: null as null | ((user: any) => void),
  errorListener: null as null | (() => void),
  onIdTokenChanged: vi.fn()
}));

const supabaseMocks = vi.hoisted(() => ({
  removeAllChannels: vi.fn().mockResolvedValue([]),
  removeChannel: vi.fn().mockResolvedValue('ok'),
  from: vi.fn(),
  channel: vi.fn()
}));

const ensureUserProfile = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock('firebase/auth', () => ({
  onIdTokenChanged: firebaseState.onIdTokenChanged
}));

vi.mock('../../lib/firebase', () => ({
  auth: {},
  get isFirebaseConfigured() {
    return firebaseState.configured;
  }
}));

vi.mock('../../lib/supabase', () => ({
  supabase: supabaseMocks
}));

vi.mock('../../features/auth/authService', () => ({
  ensureUserProfile
}));

import { AuthProvider, useAuth } from '../../app/providers/AuthProvider';

function AuthProbe() {
  const { loading, user } = useAuth();
  return <span>{loading ? 'carregando' : user?.uid ?? 'pronto'}</span>;
}

function firebaseUser(uid: string) {
  return {
    uid,
    displayName: `User ${uid}`,
    email: `${uid}@example.test`,
    photoURL: null,
    providerData: []
  };
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    supabaseMocks.removeAllChannels.mockResolvedValue([]);
    localStorage.clear();
    sessionStorage.clear();
    firebaseState.configured = false;
    firebaseState.listener = null;
    firebaseState.errorListener = null;
    firebaseState.onIdTokenChanged.mockImplementation((_auth, listener, onError) => {
      firebaseState.listener = listener;
      firebaseState.errorListener = onError;
      return vi.fn();
    });

    const maybeSingle = vi.fn().mockResolvedValue({ data: null, error: null });
    supabaseMocks.from.mockReturnValue({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({ maybeSingle }))
      }))
    });
    const channel = {
      on: vi.fn(),
      subscribe: vi.fn()
    };
    channel.on.mockReturnValue(channel);
    channel.subscribe.mockReturnValue(channel);
    supabaseMocks.channel.mockReturnValue(channel);
  });

  it('libera as rotas públicas sem iniciar o listener remoto quando não configurado', async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('pronto')).toBeInTheDocument();
    expect(firebaseState.onIdTokenChanged).not.toHaveBeenCalled();
  });

  it('restaura uma sessão válida e sincroniza o perfil', async () => {
    firebaseState.configured = true;
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    await act(async () => {
      firebaseState.listener?.(firebaseUser('user-a'));
    });

    expect(await screen.findByText('user-a')).toBeInTheDocument();
    expect(ensureUserProfile).toHaveBeenCalledWith(expect.objectContaining({ uid: 'user-a' }));
    expect(supabaseMocks.from).toHaveBeenCalledWith('users');
  });

  it('limpa dados clínicos e credenciais antes de trocar de usuário', async () => {
    firebaseState.configured = true;
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'chave-a');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'historico-a');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'legado-a');

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    await act(async () => {
      firebaseState.listener?.(firebaseUser('user-a'));
    });
    expect(await screen.findByText('user-a')).toBeInTheDocument();

    await act(async () => {
      firebaseState.listener?.(firebaseUser('user-b'));
    });

    expect(await screen.findByText('user-b')).toBeInTheDocument();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(supabaseMocks.removeAllChannels).toHaveBeenCalled();
  });

  it('serializa a limpeza e nunca publica uma identidade obsoleta durante trocas rápidas', async () => {
    firebaseState.configured = true;
    const releaseCleanup: Array<() => void> = [];
    supabaseMocks.removeAllChannels.mockImplementation(
      () => new Promise<never[]>((resolve) => releaseCleanup.push(() => resolve([])))
    );

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    act(() => {
      firebaseState.listener?.(firebaseUser('user-a'));
    });
    await waitFor(() => expect(releaseCleanup).toHaveLength(1));

    act(() => {
      firebaseState.listener?.(firebaseUser('user-b'));
    });
    expect(screen.getByText('carregando')).toBeInTheDocument();
    expect(screen.queryByText('user-a')).not.toBeInTheDocument();
    expect(screen.queryByText('user-b')).not.toBeInTheDocument();

    await act(async () => {
      releaseCleanup[0]();
    });
    await waitFor(() => expect(releaseCleanup).toHaveLength(2));
    expect(screen.getByText('carregando')).toBeInTheDocument();
    expect(screen.queryByText('user-a')).not.toBeInTheDocument();

    await act(async () => {
      releaseCleanup[1]();
    });
    expect(await screen.findByText('user-b')).toBeInTheDocument();
    expect(ensureUserProfile).toHaveBeenCalledTimes(1);
    expect(ensureUserProfile).toHaveBeenCalledWith(
      expect.objectContaining({ uid: 'user-b' })
    );
  });

  it('limpa a sessão sensível quando a autenticação expira ou é revogada', async () => {
    firebaseState.configured = true;
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'chave-a');

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    await act(async () => {
      firebaseState.listener?.(firebaseUser('user-a'));
    });
    await act(async () => {
      firebaseState.errorListener?.();
    });

    expect(await screen.findByText('pronto')).toBeInTheDocument();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
  });
});
