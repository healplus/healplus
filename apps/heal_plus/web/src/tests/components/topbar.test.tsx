import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { Topbar } from '../../components/layout/Topbar';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({
    user: { email: 'pedro@example.com' },
    profile: { displayName: 'Pedro Tescaro' }
  })
}));

describe('Topbar', () => {
  it('mantém o cabeçalho móvel fixo e sem busca duplicada', async () => {
    const user = userEvent.setup();
    const onMenuClick = vi.fn();

    render(
      <MemoryRouter>
        <Topbar onMenuClick={onMenuClick} />
      </MemoryRouter>
    );

    const header = screen.getByRole('banner', { name: 'Cabeçalho móvel' });
    expect(header.className).toContain('fixed');
    expect(header.className).toContain('top-0');
    expect(header.className).toContain('safe-area-inset-top');
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Abrir sidebar' }));
    expect(onMenuClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'Notificações' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Perfil profissional' })).toBeInTheDocument();
  });
});
