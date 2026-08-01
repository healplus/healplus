import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AI_CREDENTIAL_STORAGE_PREFIX,
  CHAT_HISTORY_STORAGE_PREFIX
} from '../../features/auth/sessionLifecycle';

const supabaseState = vi.hoisted(() => ({
  configured: false,
  authListener: null as null | ((event: string, session: any) => void),
  unsubscribe: vi.fn()
}));

const supabaseMocks = vi.hoisted(() => ({
  removeAllChannels: vi.fn().mockResolvedValue([]),
  removeChannel: vi.fn().mockResolvedValue('ok'),
  from: vi.fn(),
  channel: vi.fn(),
  auth: {
    getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    onAuthStateChange: vi.fn()
  }
}));

const ensureUserProfile = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock('../../lib/supabase', () => ({
  supabase: supabaseMocks,
  get isSupabaseConfigured() {
    return supabaseState.configured;
  }
}));

vi.mock('../../features/auth/authService', () => ({
  ensureUserProfile
}));

import { AuthProvider, useAuth } from '../../app/providers/AuthProvider';

function AuthProbe() {
  const { loading, user } = useAuth();
  return <span>{loading ? 'carregando' : user?.id ?? 'pronto'}</span>;
}

function supabaseUser(id: string) {
  return {
    id,
    email: `${id}@example.test`,
    user_metadata: { full_name: `User ${id}` },
    app_metadata: { providers: ['email'] }
  };
}

function sessionWith(userId: string) {
  return { user: supabaseUser(userId), access_token: 'token' };
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    supabaseMocks.removeAllChannels.mockResolvedValue([]);
    localStorage.clear();
    sessionStorage.clear();
    supabaseState.configured = false;
    supabaseState.authListener = null;
    supabaseState.unsubscribe.mockReset();

    supabaseMocks.auth.getSession.mockResolvedValue({ data: { session: null } });
    supabaseMocks.auth.onAuthStateChange.mockImplementation((callback: any) => {
      supabaseState.authListener = callback;
      return { data: { subscription: { unsubscribe: supabaseState.unsubscribe } } };
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
    expect(supabaseMocks.auth.onAuthStateChange).not.toHaveBeenCalled();
  });

  it('restaura uma sessão válida e sincroniza o perfil', async () => {
    supabaseState.configured = true;
    supabaseMocks.auth.getSession.mockResolvedValue({
      data: { session: sessionWith('user-a') }
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('user-a')).toBeInTheDocument();
    expect(ensureUserProfile).toHaveBeenCalledWith('user-a');
  });

  it('limpa dados clínicos e credenciais antes de trocar de usuário', async () => {
    supabaseState.configured = true;
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'chave-a');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'historico-a');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'legado-a');

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('pronto')).toBeInTheDocument();

    await act(async () => {
      supabaseState.authListener?.('SIGNED_IN', sessionWith('user-a'));
    });
    expect(await screen.findByText('user-a')).toBeInTheDocument();

    await act(async () => {
      supabaseState.authListener?.('SIGNED_IN', sessionWith('user-b'));
    });

    expect(await screen.findByText('user-b')).toBeInTheDocument();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(supabaseMocks.removeAllChannels).toHaveBeenCalled();
  });

  it('serializa a limpeza e nunca publica uma identidade obsoleta durante trocas rápidas', async () => {
    supabaseState.configured = true;
    const releaseCleanup: Array<() => void> = [];
    supabaseMocks.removeAllChannels.mockImplementation(
      () => new Promise<never[]>((resolve) => releaseCleanup.push(() => resolve([])))
    );

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('pronto')).toBeInTheDocument();

    act(() => {
      supabaseState.authListener?.('SIGNED_IN', sessionWith('user-a'));
    });
    await waitFor(() => expect(releaseCleanup).toHaveLength(1));

    act(() => {
      supabaseState.authListener?.('SIGNED_IN', sessionWith('user-b'));
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
    expect(ensureUserProfile).toHaveBeenCalledWith('user-b');
  });

  it('limpa a sessão sensível quando a autenticação expira ou é revogada', async () => {
    supabaseState.configured = true;
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'chave-a');

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('pronto')).toBeInTheDocument();

    await act(async () => {
      supabaseState.authListener?.('SIGNED_IN', sessionWith('user-a'));
    });
    expect(await screen.findByText('user-a')).toBeInTheDocument();

    await act(async () => {
      supabaseState.authListener?.('SIGNED_OUT', null);
    });

    expect(await screen.findByText('pronto')).toBeInTheDocument();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
  });
});
