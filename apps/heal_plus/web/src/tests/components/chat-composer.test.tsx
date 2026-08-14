import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AIComposer } from '../../features/chat/components/composer/ai-composer';

describe('AIComposer', () => {
  it('mantém contexto, controles e envio acessíveis no layout responsivo', async () => {
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
      <AIComposer
        value="Revisar evolução"
        onChange={onChange}
        onSubmit={onSubmit}
        mode="assistant"
        onSelectMode={vi.fn()}
        internalSearchEnabled
        externalSearchEnabled
        onToggleInternalSearch={vi.fn()}
        onToggleExternalSearch={vi.fn()}
        attachments={[]}
        onAddAttachment={vi.fn()}
        onRemoveAttachment={vi.fn()}
        patientContext={{
          id: 'synthetic-patient-1',
          displayName: 'Paciente sintético com nome extenso',
          maskedIdentifier: 'PAC-001'
        }}
        onRemovePatientContext={vi.fn()}
        onOpenPatientSelector={vi.fn()}
      />
    );

    expect(container.firstElementChild).toHaveClass('min-w-0', 'px-3', 'sm:px-4');
    expect(screen.getByText(/Pesquisa Web Ativada/i)).toBeInTheDocument();
    expect(
      screen.getByText((_content, element) =>
        Boolean(
          element?.classList.contains('truncate') &&
          element.textContent?.includes('Paciente sintético com nome extenso')
        )
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Mensagem para o assistente' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Anexar arquivos' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Gravar áudio' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
