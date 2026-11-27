import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PresentationPage } from '../../features/presentation/PresentationPage';
import { slides } from '../../features/presentation/slides';

vi.mock('../../app/providers/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() })
}));

function renderPresentation() {
  return render(<PresentationPage />, { wrapper: MemoryRouter });
}

function currentSlide() {
  return screen.getByRole('region', { name: new RegExp(`de ${slides.length}:`) });
}

describe('PresentationPage', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/apresentacao');
  });

  it('abre na capa com o título do projeto e o aviso de protótipo', () => {
    renderPresentation();

    expect(currentSlide()).toHaveAccessibleName(`1 de ${slides.length}: Heal+`);
    expect(screen.getByRole('heading', { level: 1, name: /acompanhamento de feridas crônicas/i })).toBeInTheDocument();
    expect(screen.getByText(/não substitui a avaliação profissional/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Slide anterior' })).toBeDisabled();
  });

  it('navega pelo teclado e pelos controles', async () => {
    const user = userEvent.setup();
    renderPresentation();

    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(currentSlide()).toHaveAccessibleName(`2 de ${slides.length}: O desafio`);
    expect(window.location.hash).toBe('#desafio');

    fireEvent.keyDown(window, { key: 'End' });
    expect(currentSlide()).toHaveAccessibleName(`${slides.length} de ${slides.length}: Equipe`);
    expect(screen.getByRole('button', { name: 'Próximo slide' })).toBeDisabled();

    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(currentSlide()).toHaveAccessibleName(`${slides.length - 1} de ${slides.length}: Parcerias`);

    await user.click(screen.getByRole('button', { name: /ir para o slide 5: IA como apoio/i }));
    expect(currentSlide()).toHaveAccessibleName(`5 de ${slides.length}: IA como apoio`);
    expect(screen.getByRole('button', { name: /ir para o slide 5/i })).toHaveAttribute('aria-current', 'step');
  });

  it('apresenta a IA como apoio experimental com revisão humana', () => {
    window.history.replaceState(null, '', '/apresentacao#ia');
    renderPresentation();

    expect(screen.getByText(/ainda precisa de ajustes e validação clínica/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Revisão humana' })).toBeInTheDocument();
  });

  it('retoma o slide indicado na URL e ignora identificadores desconhecidos', () => {
    window.history.replaceState(null, '', '/apresentacao#trajetoria');
    const { unmount } = renderPresentation();
    expect(currentSlide()).toHaveAccessibleName(`6 de ${slides.length}: Nossa trajetória`);
    expect(screen.getByText(/chamada pública da RNP/i)).toBeInTheDocument();
    unmount();

    window.history.replaceState(null, '', '/apresentacao#inexistente');
    renderPresentation();
    expect(currentSlide()).toHaveAccessibleName(`1 de ${slides.length}: Heal+`);
  });
});
