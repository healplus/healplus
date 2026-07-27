import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginPage } from '../../features/auth/LoginPage';
import { RegisterPage } from '../../features/auth/RegisterPage';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: null, profile: null, loading: false })
}));

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() })
}));

const serviceMocks = vi.hoisted(() => ({
  loginWithEmail: vi.fn(),
  registerWithEmail: vi.fn(),
  resetPassword: vi.fn(),
  signInWithEmail: vi.fn(),
  signUpWithEmail: vi.fn(),
  signInWithGoogle: vi.fn(),
  signInWithMicrosoft: vi.fn(),
  signInWithApple: vi.fn(),
  consumeLogoutNotice: vi.fn()
}));

vi.mock('../../features/auth/authService', () => ({
  friendlyAuthError: () => 'Erro amigavel',
  consumeLogoutNotice: serviceMocks.consumeLogoutNotice,
  loginWithEmail: serviceMocks.loginWithEmail,
  registerWithEmail: serviceMocks.registerWithEmail,
  resetPassword: serviceMocks.resetPassword,
  signInWithEmail: serviceMocks.signInWithEmail,
  signUpWithEmail: serviceMocks.signUpWithEmail,
  signInWithGoogle: serviceMocks.signInWithGoogle,
  signInWithMicrosoft: serviceMocks.signInWithMicrosoft,
  signInWithApple: serviceMocks.signInWithApple
}));

describe('paginas de autenticacao', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    serviceMocks.consumeLogoutNotice.mockReturnValue(null);
  });

  it('renderiza LoginPage', () => {
    render(<LoginPage />, { wrapper: MemoryRouter });
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument();
  });

  it('renderiza RegisterPage', () => {
    render(<RegisterPage />, { wrapper: MemoryRouter });
    expect(screen.getByRole('button', { name: /cadastrar/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/nome profissional/i)).toBeInTheDocument();
  });

  it('envia login com e-mail para o servico correto', async () => {
    const user = userEvent.setup();
    const { container } = render(<LoginPage />, { wrapper: MemoryRouter });
    const passwordInput = container.querySelector('input[type="password"]');

    await user.type(screen.getByLabelText(/e-mail/i), 'dra@heal.plus');
    if (passwordInput) await user.type(passwordInput, '123456');
    await user.click(screen.getByRole('button', { name: /^entrar$/i }));

    await waitFor(() => expect(serviceMocks.signInWithEmail).toHaveBeenCalledWith('dra@heal.plus', '123456'));
  });

  it('mostra erro genérico quando o login é inválido', async () => {
    serviceMocks.signInWithEmail.mockRejectedValueOnce({ code: 'auth/user-not-found' });
    const user = userEvent.setup();
    const { container } = render(<LoginPage />, { wrapper: MemoryRouter });
    const passwordInput = container.querySelector('input[type="password"]');

    await user.type(screen.getByLabelText(/e-mail/i), 'inexistente@heal.plus');
    if (passwordInput) await user.type(passwordInput, '123456');
    await user.click(screen.getByRole('button', { name: /^entrar$/i }));

    expect((await screen.findAllByText('Erro amigavel')).length).toBeGreaterThan(0);
  });

  it('mostra uma falha de revogação após o encerramento local', async () => {
    serviceMocks.consumeLogoutNotice.mockReturnValueOnce(
      'Sessão local encerrada; revogue o acesso no provedor.'
    );

    render(<LoginPage />, { wrapper: MemoryRouter });

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Sessão local encerrada; revogue o acesso no provedor.'
    );
  });

  it('chama provedores sociais', async () => {
    const user = userEvent.setup();
    render(<LoginPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /google/i }));

    expect(serviceMocks.signInWithGoogle).toHaveBeenCalled();
  });
});
