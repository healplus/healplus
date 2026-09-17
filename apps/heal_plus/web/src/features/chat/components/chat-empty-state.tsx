import { Sparkles, FileText, ArrowLeftRight, Activity, UserPlus, FileSpreadsheet } from 'lucide-react';
import type { PatientContext } from '../types';

interface ChatEmptyStateProps {
  onSelectSuggestion: (text: string) => void;
  patientContext?: PatientContext;
  onOpenPatientSelector: () => void;
}

export function ChatEmptyState({
  onSelectSuggestion,
  patientContext,
  onOpenPatientSelector
}: ChatEmptyStateProps) {
  const suggestions = [
    {
      title: 'Resumir histórico clínico',
      prompt: patientContext
        ? `Sintetize o histórico completo de acompanhamento e avaliações do paciente ${patientContext.displayName}.`
        : 'Sintetize o histórico de atendimento do paciente selecionado.',
      icon: FileText
    },
    {
      title: 'Comparar últimas avaliações',
      prompt: 'Compare visual e metricamente as duas últimas avaliações registradas da lesão.',
      icon: ArrowLeftRight
    },
    {
      title: 'Rascunho de relatório',
      prompt: 'Elabore um rascunho de relatório de evolução longitudinal para a última consulta.',
      icon: FileSpreadsheet
    },
    {
      title: 'Explorar variação da ferida',
      prompt: 'Explique a evolução da área, tecidos de granulação e esfacelo entre as consultas.',
      icon: Activity
    }
  ];

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center max-w-2xl mx-auto my-auto animate-in fade-in zoom-in-95">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-xl shadow-blue-600/30 mb-6">
        <Sparkles size={28} />
      </div>

      <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight sm:text-3xl font-headline">
        Como posso ajudar no cuidado de hoje?
      </h1>

      <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 max-w-lg leading-relaxed font-medium">
        Consulte informações, organize avaliações e acompanhe a evolução dos seus pacientes com apoio da IA do Heal+.
      </p>

      {/* Patient Selection Callout Banner when no patient selected */}
      {!patientContext && (
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-3 w-full rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50/60 p-4 text-left dark:border-blue-900/60 dark:from-slate-900 dark:to-blue-950/40">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-300">
              <UserPlus size={20} />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-white">
                Nenhum paciente focado
              </p>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                Selecione um paciente para utilizar informações do prontuário.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenPatientSelector}
            className="shrink-0 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-blue-700 shadow-md transition-all active:scale-95"
          >
            Selecionar paciente
          </button>
        </div>
      )}

      {/* Suggestion Cards Grid */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
        {suggestions.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.title}
              type="button"
              onClick={() => onSelectSuggestion(item.prompt)}
              className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-blue-300 hover:bg-blue-50/40 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-800 dark:hover:bg-slate-800/60 group"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors dark:bg-blue-950 dark:text-blue-400">
                <Icon size={18} />
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  {item.title}
                </h3>
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                  {item.prompt}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
