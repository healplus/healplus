import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AppShell } from '../../components/layout/AppShell';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ profile: null })
}));

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ setTheme: vi.fn() })
}));

vi.mock('../../components/layout/sidebar', () => ({
  Sidebar: () => <aside>Sidebar</aside>
}));

vi.mock('../../components/layout/Topbar', () => ({
  Topbar: () => <header>Topbar</header>
}));

describe('AppShell navigation context', () => {
  it('announces page title and moves focus after route navigation', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/patients']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route
              path="/patients"
              element={<Link to="/patients/synthetic-patient-1">Abrir registro</Link>}
            />
            <Route path="/patients/:patientId" element={<h1>Registro sintético</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Abrir registro' })).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Abrir registro' }));

    expect(await screen.findByRole('heading', { name: 'Registro sintético' })).toBeInTheDocument();
    const main = screen.getByRole('main');
    await waitFor(() => expect(main).toHaveFocus());
    expect(main.className).toContain('overflow-y-auto');
    expect(main.className).toContain('safe-area-inset-bottom');
    expect(document.title).toBe('Registro atual | Heal+');
  });
});
