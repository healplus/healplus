import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { AuthCallbackPage } from '../../features/auth/AuthCallbackPage';

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(() => new Promise(() => undefined)),
      onAuthStateChange: vi.fn()
    }
  }
}));

vi.mock('../../features/auth/authService', () => ({
  ensureUserProfile: vi.fn()
}));

describe('callback de autenticação', () => {
  it('exibe somente o loader durante o processamento', () => {
    const { container } = render(<AuthCallbackPage />, { wrapper: MemoryRouter });

    expect(screen.getByRole('status', { name: /processando autenticação/i })).toBeInTheDocument();
    expect(screen.getByText(/aguarde enquanto preparamos seu acesso/i)).toBeInTheDocument();
    expect(screen.queryByText(/portal clínico seguro/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/contexto clínico para uma evolução/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /voltar para o início/i })).not.toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass('min-h-screen', 'bg-heal-softBlue');
  });
});
