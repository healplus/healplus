import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginPage } from '../../features/auth/LoginPage';
import { RegisterPage } from '../../features/auth/RegisterPage';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: null, profile: null, loading: false })
}));

const themeMocks = vi.hoisted(() => ({ toggleTheme: vi.fn() }));

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: themeMocks.toggleTheme })
}));

const serviceMocks = vi.hoisted(() => ({
  loginWithEmail: vi.fn(),
  registerWithEmail: vi.fn(),
  resetPassword: vi.fn(),
  signInWithEmail: vi.fn(),
  signUpWithEmail: vi.fn(),
  signInWithGoogle: vi.fn(),
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
  signInWithGoogle: serviceMocks.signInWithGoogle
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
    expect(screen.getByRole('button', { name: /microsoft.*em breve/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /ativar modo claro/i })).toBeInTheDocument();
  });

  it('renderiza RegisterPage', () => {
    render(<RegisterPage />, { wrapper: MemoryRouter });
    expect(screen.getByRole('button', { name: /criar conta/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/nome profissional/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /github.*em breve/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /microsoft.*em breve/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /ativar modo claro/i })).toBeInTheDocument();
  });

  it('permite alternar o tema nas páginas de autenticação', async () => {
    const user = userEvent.setup();
    render(<LoginPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /ativar modo claro/i }));

    expect(themeMocks.toggleTheme).toHaveBeenCalledOnce();
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
    serviceMocks.signInWithEmail.mockRejectedValueOnce({ message: 'invalid_credentials' });
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

  it('chama provedor Google', async () => {
    const user = userEvent.setup();
    render(<LoginPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /google/i }));

    expect(serviceMocks.signInWithGoogle).toHaveBeenCalled();
  });
});
