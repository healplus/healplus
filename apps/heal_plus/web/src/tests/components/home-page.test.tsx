import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import HomePage from '../../features/home/HomePage';

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() })
}));

describe('landing page', () => {
  it('transforma o header em uma barra compacta após a rolagem', () => {
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 0 });
    render(<HomePage />, { wrapper: MemoryRouter });
    const navigation = screen.getByRole('navigation', { name: /navegação principal/i });

    expect(navigation).toHaveClass('max-w-[1536px]');

    Object.defineProperty(window, 'scrollY', { configurable: true, value: 100 });
    fireEvent.scroll(window);

    expect(navigation).toHaveClass('max-w-6xl', 'rounded-[18px]');
  });

  it('mantém fundos uniformes nos modos claro e escuro', () => {
    const { container } = render(<HomePage />, { wrapper: MemoryRouter });
    const sections = container.querySelectorAll('main > section');

    expect(sections.length).toBeGreaterThan(0);
    sections.forEach(section => {
      expect(section).toHaveClass('bg-white');
      expect(section).toHaveClass('dark:bg-[#111111]');
    });
  });

  it('apresenta a proposta clínica e o acesso principal', () => {
    render(<HomePage />, { wrapper: MemoryRouter });

    expect(screen.getByRole('heading', { name: /cuidado inteligente.*evolução visível/i })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /acessar área clínica/i })[0]).toHaveAttribute('href', '/login');
    expect(screen.getByText(/fluxo clínico centralizado/i)).toBeInTheDocument();
    expect(screen.getByText(/nunca como diagnóstico definitivo/i)).toBeInTheDocument();
    expect(screen.getByText('REDI-SUS CLUSTER')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /pesquisa aplicada conectada ao ecossistema de saúde digital/i })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'RNP' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Centro Paula Souza' })).toBeInTheDocument();
  });

  it('permite alternar o conteúdo para inglês', async () => {
    const user = userEvent.setup();
    render(<HomePage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /mudar idioma para inglês/i }));

    expect(screen.getByRole('heading', { name: /smart care.*visible evolution/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /change language to portuguese/i })).toBeInTheDocument();
  });

  it('oferece idioma e entrada no menu móvel', async () => {
    const user = userEvent.setup();
    render(<HomePage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /abrir menu/i }));

    expect(screen.getAllByRole('button', { name: /mudar idioma para inglês/i })).toHaveLength(2);
    expect(screen.getAllByRole('link', { name: /^entrar$/i }).at(-1)).toHaveAttribute('href', '/login');
  });
});
