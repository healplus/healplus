import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SettingsPage } from '../../features/settings/SettingsPage';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice', email: 'alice@example.com', displayName: 'Alice Liddell' },
  profile: {
    displayName: 'Alice Liddell',
    email: 'alice@example.com',
    professionalArea: 'Enfermagem',
    clinicName: 'Fatec Itaquera',
    phone: '',
    role: 'professional' as const,
    settings: {
      theme: 'light' as const,
      notificationsEnabled: true,
      emailNotificationsEnabled: true,
      agendaRemindersEnabled: true,
      hideEmailPreview: false,
      showProfilePhoto: true
    }
  },
  setTheme: vi.fn()
}));

const profileServiceMocks = vi.hoisted(() => ({
  updateSettings: vi.fn().mockResolvedValue(undefined),
  updateProfileData: vi.fn().mockResolvedValue(undefined),
  uploadProfilePhoto: vi.fn().mockResolvedValue('https://example.test/avatar.png')
}));

const authServiceMocks = vi.hoisted(() => {
  class LogoutError extends Error {
    constructor(
      message: string,
      readonly localSessionClosed: boolean
    ) {
      super(message);
    }
  }

  return {
    logout: vi.fn().mockResolvedValue(undefined),
    LogoutError
  };
});

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: mocks.profile, loading: false })
}));

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light', setTheme: mocks.setTheme })
}));

vi.mock('../../features/profile/profileService', async importOriginal => {
  const actual = await importOriginal<typeof import('../../features/profile/profileService')>();
  return {
    ...actual,
    updateSettings: profileServiceMocks.updateSettings,
    updateProfileData: profileServiceMocks.updateProfileData,
    uploadProfilePhoto: profileServiceMocks.uploadProfilePhoto
  };
});

vi.mock('../../features/auth/authService', () => authServiceMocks);

function notificationsToggle() {
  const row = screen.getByText('Notificações gerais').closest('div');
  expect(row).not.toBeNull();
  return within(row as HTMLElement).getByRole('button');
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    profileServiceMocks.updateSettings.mockResolvedValue(undefined);
  });

  it('atualiza preferências rápidas de forma otimista', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /Preferências rápidas/i }));
    const toggle = notificationsToggle();
    expect(toggle).toHaveTextContent('LIGADO');

    await user.click(toggle);

    expect(toggle).toHaveTextContent('DESLIGADO');
    expect(profileServiceMocks.updateSettings).toHaveBeenCalledWith('alice', {
      notificationsEnabled: false
    });
  });

  it('restaura a preferência anterior quando a persistência falha', async () => {
    profileServiceMocks.updateSettings.mockRejectedValueOnce(
      new Error('Não foi possível salvar esta preferência.')
    );
    const user = userEvent.setup();
    render(<SettingsPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /Preferências rápidas/i }));
    await user.click(notificationsToggle());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível salvar esta preferência.'
    );
    await waitFor(() => expect(notificationsToggle()).toHaveTextContent('LIGADO'));
  });

  it('renderiza ações da conta no formato compacto', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /Ações da conta/i }));

    expect(
      screen.getByText(/sessões abertas em todos os dispositivos vinculados/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Encerrar todas as sessões/i })).toBeInTheDocument();
    expect(screen.queryByText(/Sair da Conta \(Logout\)/i)).not.toBeInTheDocument();
  });
});
