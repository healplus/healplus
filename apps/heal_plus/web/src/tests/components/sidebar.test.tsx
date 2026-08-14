import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../../components/layout/sidebar';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice', email: 'alice@example.com' },
  profile: { displayName: 'Alice Liddell', clinicName: 'Fatec Itaquera', email: 'alice@example.com' }
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
    logout: vi.fn(),
    LogoutError
  };
});

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: mocks.profile, loading: false })
}));

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light' })
}));

vi.mock('../../features/auth/authService', () => authServiceMocks);

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza itens principais, instituicao e email', async () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Pacientes')).toBeInTheDocument();
    expect(screen.getByText(/Avalia[cç][oõ]es/i)).toBeInTheDocument();
    expect(screen.getByText('Agenda')).toBeInTheDocument();
    expect(screen.getByText(/Relat[oó]rios/i)).toBeInTheDocument();
    expect(screen.getByText('Assistente')).toBeInTheDocument();
    expect(screen.getByText('Perfil')).toBeInTheDocument();
    expect(screen.getByText('Fatec Itaquera')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('Alice Liddell')).toBeInTheDocument();

    // Clica em "Mais" para abrir o dropdown
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    expect(screen.getByText(/Comparar evolu[cç][aã]o/i)).toBeInTheDocument();
    expect(screen.getByText('HEAL Analyzer')).toBeInTheDocument();
    expect(screen.getByText(/Configura[cç][oõ]es/i)).toBeInTheDocument();
  });

  it('ativa apenas Relatórios na rota /reports', async () => {
    render(
      <MemoryRouter initialEntries={['/reports']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getAllByRole('link', { name: /Relat[oó]rios/i })[0];
    expect(reportsLink.className).toContain('font-black');

    // Abre o dropdown "Mais" para verificar "Comparar evolução"
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    const compareLink = screen.getByRole('menuitem', { name: /Comparar evolu[cç][aã]o/i });
    expect(compareLink.className).not.toContain('text-heal-blue');
  });

  it('ativa apenas Comparar evolução na rota /reports/compare', async () => {
    render(
      <MemoryRouter initialEntries={['/reports/compare']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getAllByRole('link', { name: /Relat[oó]rios/i })[0];
    expect(reportsLink.className).not.toContain('font-black');

    // Abre o dropdown "Mais" para verificar "Comparar evolução"
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    const compareLink = screen.getByRole('menuitem', { name: /Comparar evolu[cç][aã]o/i });
    expect(compareLink.className).toContain('text-heal-blue');
  });

  it('mantém no drawer móvel o assistente, perfil, comparação, Analyzer e configurações', () => {
    render(
      <MemoryRouter initialEntries={['/analyzer']}>
        <Sidebar isOpen setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const mobileMenu = screen.getByLabelText('Menu móvel');

    expect(within(mobileMenu).getByText('Assistente')).toBeInTheDocument();
    expect(within(mobileMenu).getByText('Perfil')).toBeInTheDocument();
    expect(within(mobileMenu).getByText(/Comparar evolu[cç][aã]o/i)).toBeInTheDocument();
    expect(within(mobileMenu).getByText('HEAL Analyzer')).toBeInTheDocument();
    expect(within(mobileMenu).getByText(/Configura[cç][oõ]es/i)).toBeInTheDocument();

    expect(within(mobileMenu).queryByText('Dashboard')).not.toBeInTheDocument();
    expect(within(mobileMenu).queryByText('Pacientes')).not.toBeInTheDocument();
    expect(within(mobileMenu).getByRole('link', { name: 'HEAL Analyzer' }).className).toContain('font-black');
  });

  it('mantém a área atual e mostra ação segura quando o logout local falha', async () => {
    authServiceMocks.logout.mockRejectedValueOnce(
      new authServiceMocks.LogoutError(
        'Não foi possível encerrar a sessão neste dispositivo. Tente novamente.',
        false
      )
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: /Alice Liddell/i }));
    expect(screen.getByRole('menuitem', { name: 'Meu Perfil' })).toBeInTheDocument();
    expect(screen.queryByText('Encerra sessões em todos os dispositivos')).not.toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: /Sair da Conta/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível encerrar a sessão neste dispositivo. Tente novamente.'
    );
  });
});
