import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EvaluationForm } from '../../features/evaluations/EvaluationForm';

describe('EvaluationForm', () => {
  it('renderiza fluxo clinico TIMERS estruturado', async () => {
    const user = userEvent.setup();
    render(
      <EvaluationForm
        patients={[{ id: 'p1', name: 'Tania Silva', phone: '11999999999', email: '', birthDate: '1985-05-12', notes: '', archived: false }]}
        onSubmit={vi.fn()}
      />
    );
    await user.selectOptions(screen.getByLabelText(/paciente/i), 'p1');
    await user.click(screen.getByRole('button', { name: /continuar/i }));

    expect(await screen.findByText(/T - Tecido/i)).toBeInTheDocument();
    expect(screen.getByText(/I - Infec[cç][aã]o e Inflam[aã]ç[aã]o/i)).toBeInTheDocument();
    expect(screen.getByText(/M - Umidade/i)).toBeInTheDocument();
    expect(screen.getByText(/E - Bordas/i)).toBeInTheDocument();
    expect(screen.getByText(/R - Reparo/i)).toBeInTheDocument();
    expect(screen.getByText(/S - Fatores Sociais/i)).toBeInTheDocument();
  });

  it('anuncia a etapa atual e move o foco para o primeiro campo inválido', async () => {
    const user = userEvent.setup();
    render(
      <EvaluationForm
        patients={[{ id: 'p1', name: 'Tania Silva', phone: '', email: '', birthDate: '1985-05-12', notes: '', archived: false }]}
        onSubmit={vi.fn()}
      />
    );

    const progress = screen.getByRole('navigation', { name: /progresso da avaliação clínica/i });
    expect(within(progress).getByText('Paciente').closest('li')).toHaveAttribute('aria-current', 'step');

    await user.click(screen.getByRole('button', { name: /continuar/i }));
    expect(await screen.findByText(/revise os campos obrigatórios/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(/paciente/i)).toHaveFocus());

    await user.selectOptions(screen.getByLabelText(/paciente/i), 'p1');
    await user.click(screen.getByRole('button', { name: /continuar/i }));
    const heading = await screen.findByRole('heading', { name: /etapa 2 de 4/i });
    expect(heading).toHaveFocus();
    const currentStep = progress.querySelector('li[aria-current="step"]');
    expect(currentStep).toHaveTextContent(/clínica/i);

    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}');
    expect(await screen.findByRole('heading', { name: /etapa 1 de 4/i })).toHaveFocus();
  });

  it('exige revisão profissional e evita salvamento duplicado', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <EvaluationForm
        patients={[{ id: 'p1', name: 'Tania Silva', phone: '', email: '', birthDate: '1985-05-12', notes: '', archived: false }]}
        onSubmit={onSubmit}
      />
    );

    await user.selectOptions(screen.getByLabelText(/paciente/i), 'p1');
    await user.click(screen.getByRole('button', { name: /continuar/i }));

    for (const label of [
      /localização$/i,
      /etiologia$/i,
      /quantidade$/i,
      /^tipo$/i,
      /características das bordas/i,
      /umidade da pele perilesional/i,
    ]) {
      const select = screen.getByLabelText(label) as HTMLSelectElement;
      await user.selectOptions(select, select.options[1]);
    }

    await user.click(screen.getByRole('button', { name: /continuar/i }));
    expect(await screen.findByText(/arraste imagens da ferida/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /continuar/i }));

    const saveButton = await screen.findByRole('button', { name: /salvar avaliação/i });
    await user.click(saveButton);
    const confirmation = screen.getByRole('checkbox', { name: /confirmo que revisei/i });
    expect(await screen.findByText(/confirme a revisão profissional/i)).toBeInTheDocument();
    await waitFor(() => expect(confirmation).toHaveFocus());
    expect(onSubmit).not.toHaveBeenCalled();

    await user.click(confirmation);
    await user.dblClick(saveButton);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
    expect(await screen.findByRole('button', { name: /avaliação salva/i })).toBeDisabled();
  });
});
