import { ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Modal } from '../../../../components/ui/Modal';
import { getAiProviderDefinition, type AiProviderConfig } from '../../aiProvider';
import { aiTransmissionDestination } from '../../externalTransmission';

interface ExternalTransmissionDialogProps {
  attachmentCount: number;
  config: AiProviderConfig;
  historyMessageCount: number;
  onCancel: () => void;
  onConfirm: (includeConversationHistory: boolean) => void;
  open: boolean;
}

export function ExternalTransmissionDialog({
  attachmentCount,
  config,
  historyMessageCount,
  onCancel,
  onConfirm,
  open
}: ExternalTransmissionDialogProps) {
  const [includeHistory, setIncludeHistory] = useState(false);
  const provider = getAiProviderDefinition(config.provider);

  useEffect(() => {
    if (open) setIncludeHistory(false);
  }, [open, config.provider, config.model]);

  return (
    <Modal open={open} onClose={onCancel} title="Compartilhar dados com a IA?" size="md">
      <div className="space-y-5">
        <div className="flex items-start gap-3 rounded-2xl bg-heal-softBlue/70 p-4 dark:bg-blue-950/20">
          <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-heal-blue" />
          <div className="text-sm">
            <p className="font-bold text-heal-ink dark:text-white">Envio único para {provider.label}</p>
            <p className="mt-1 break-all text-xs text-heal-muted dark:text-zinc-400">
              Destino: {aiTransmissionDestination(config)}
            </p>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">
              Finalidade: gerar apoio à decisão clínica para esta conversa. A resposta exige validação profissional.
            </p>
          </div>
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-bold text-heal-ink dark:text-white">Dados que serão enviados</legend>
          <label className="flex items-start gap-3 rounded-xl border border-heal-line p-3 dark:border-zinc-700">
            <input checked disabled className="mt-0.5 h-4 w-4" type="checkbox" />
            <span>
              <span className="block text-sm font-semibold text-heal-ink dark:text-white">Mensagem atual</span>
              <span className="block text-xs text-heal-muted dark:text-zinc-400">Somente o texto digitado.</span>
            </span>
          </label>

          {historyMessageCount > 0 ? (
            <label className="flex items-start gap-3 rounded-xl border border-heal-line p-3 dark:border-zinc-700">
              <input
                checked={includeHistory}
                className="mt-0.5 h-4 w-4 accent-heal-blue"
                onChange={event => setIncludeHistory(event.target.checked)}
                type="checkbox"
              />
              <span>
                <span className="block text-sm font-semibold text-heal-ink dark:text-white">
                  Histórico recente ({Math.min(historyMessageCount, 6)} mensagens)
                </span>
                <span className="block text-xs text-heal-muted dark:text-zinc-400">
                  Opcional. Inclui apenas texto desta conversa.
                </span>
              </span>
            </label>
          ) : null}
        </fieldset>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
          Identidade e contexto do paciente não serão enviados. {attachmentCount > 0
            ? `${attachmentCount} anexo(s) permanecerão somente neste navegador.`
            : 'Nenhum anexo será enviado.'}
        </div>

        <p className="text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
          Esta autorização vale somente para este envio. Cancelar mantém a mensagem e os anexos para edição local.
        </p>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            className="rounded-xl border border-heal-line px-4 py-2.5 text-sm font-bold text-heal-ink hover:bg-heal-canvas dark:border-zinc-700 dark:text-white dark:hover:bg-zinc-800"
            onClick={onCancel}
            type="button"
          >
            Manter sem enviar
          </button>
          <button
            className="rounded-xl bg-heal-blue px-4 py-2.5 text-sm font-bold text-slate-950 hover:bg-heal-blue/90"
            onClick={() => onConfirm(includeHistory)}
            type="button"
          >
            Autorizar e enviar uma vez
          </button>
        </div>
      </div>
    </Modal>
  );
}
