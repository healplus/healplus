import { render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({
  user: null as null | { uid: string },
  profile: null as null | { onboardingCompleted?: boolean },
  loading: false
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => authState
}));

describe('ProtectedRoute', () => {
  it('não exibe conteúdo protegido enquanto a sessão é validada', async () => {
    authState.user = { uid: 'alice' };
    authState.profile = { onboardingCompleted: true };
    authState.loading = true;
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>Conteúdo clínico sensível</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText(/Validando sess/i)).toBeInTheDocument();
    expect(screen.queryByText('Conteúdo clínico sensível')).not.toBeInTheDocument();
    authState.loading = false;
  });

  it('bloqueia usuario nao autenticado', async () => {
    authState.user = null;
    authState.profile = null;
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>Dashboard privado</div>} />
          </Route>
          <Route path="/login" element={<div>Tela de login</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Tela de login')).toBeInTheDocument();
  });

  it('redireciona primeiro acesso para onboarding', async () => {
    authState.user = { uid: 'alice' };
    authState.profile = { onboardingCompleted: false };
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>Dashboard privado</div>} />
            <Route path="/onboarding" element={<div>Onboarding</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Onboarding')).toBeInTheDocument();
  });

  it('remonta a área protegida para descartar estado em memória na troca de usuário', async () => {
    authState.user = { uid: 'alice' };
    authState.profile = { onboardingCompleted: true };
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    function ClinicalStateProbe() {
      const [ownerAtMount] = useState(authState.user?.uid);
      return <div>Estado de {ownerAtMount}</div>;
    }

    const renderRoutes = () => (
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<ClinicalStateProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
    const { rerender } = render(renderRoutes());
    expect(screen.getByText('Estado de alice')).toBeInTheDocument();

    authState.user = { uid: 'bob' };
    rerender(renderRoutes());

    expect(screen.getByText('Estado de bob')).toBeInTheDocument();
  });
});
