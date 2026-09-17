import { useState, useEffect } from 'react';
import { Loader2, StopCircle, Sparkles } from 'lucide-react';
import type { ProcessingStage } from '../../types';

interface AIProcessingStatusProps {
  stage: ProcessingStage;
  onCancel?: () => void;
}

const STAGE_MESSAGES: Record<ProcessingStage, string[]> = {
  idle: [],
  uploading: ['Enviando anexos e arquivos clínicos...', 'Validando arquivos autorizados...'],
  'retrieving-context': ['Consultando o contexto autorizado...', 'Localizando avaliações e histórico no Heal+...'],
  analyzing: ['Analisando informações clínicas...', 'Avaliando dados teciduais e métricas de ROI...'],
  comparing: ['Comparando registros de evolução...', 'Processando métricas entre consultas...'],
  generating: ['Organizando os resultados...', 'Estruturando o parecer clínico assistido...'],
  streaming: ['Preparando a resposta...'],
  completed: [],
  cancelled: ['Operação interrompida pelo usuário.'],
  error: ['Falha no processamento.']
};

export function AIProcessingStatus({ stage, onCancel }: AIProcessingStatusProps) {
  const messages = STAGE_MESSAGES[stage] || STAGE_MESSAGES['analyzing'];
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    if (messages.length <= 1) return;
    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % messages.length);
    }, 2400);
    return () => clearInterval(interval);
  }, [messages]);

  if (stage === 'idle' || stage === 'completed') return null;

  const currentText = messages[msgIndex] || 'Processando solicitação clínica...';

  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className="my-4 flex min-h-[68px] items-center justify-between rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 via-white to-blue-50/50 p-3.5 shadow-sm motion-safe:animate-in motion-safe:fade-in dark:border-blue-900/50 dark:from-slate-900 dark:via-blue-950/30 dark:to-slate-900"
      role="status"
    >
      <div className="flex items-center gap-3">
        <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-600/30 dark:bg-blue-500">
          <Sparkles aria-hidden="true" size={16} className="motion-safe:animate-spin" style={{ animationDuration: '3s' }} />
        </div>

        <div className="flex flex-col">
          <span className="text-xs font-bold text-blue-900 dark:text-blue-200 flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 motion-safe:animate-ping"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
            </span>
            Assistente Heal+
          </span>
          <p className="mt-0.5 text-xs font-medium text-slate-600 motion-safe:animate-pulse dark:text-slate-300">
            {currentText}
          </p>
        </div>
      </div>

      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition-colors hover:bg-red-50 hover:text-red-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-red-950 dark:hover:text-red-400"
        >
          <StopCircle size={14} />
          <span>Cancelar</span>
        </button>
      )}
    </div>
  );
}
