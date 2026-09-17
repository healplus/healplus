import { Calendar, FileText, UserCheck, Activity } from 'lucide-react';
import type { PatientSummaryCardData } from '../../types';

interface PatientSummaryCardProps {
  data: PatientSummaryCardData;
  onSelect?: () => void;
}

export function PatientSummaryCard({ data, onSelect }: PatientSummaryCardProps) {
  return (
    <div className="my-3 rounded-2xl border border-blue-100 bg-gradient-to-br from-white to-blue-50/40 p-4.5 shadow-sm dark:border-blue-900/40 dark:from-slate-900 dark:to-blue-950/20">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20 dark:bg-blue-500">
            {data.name.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h4 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              {data.name}
              {data.maskedIdentifier && (
                <span className="rounded-md bg-blue-100/80 px-2 py-0.5 text-[11px] font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300 font-mono">
                  {data.maskedIdentifier}
                </span>
              )}
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 flex items-center gap-2">
              <span>{data.age ? `${data.age} anos` : 'Idade não informada'}</span>
              <span>•</span>
              <span className="inline-flex items-center gap-1 font-medium text-blue-600 dark:text-blue-400">
                <Activity size={12} /> {data.status}
              </span>
            </p>
          </div>
        </div>

        {onSelect && (
          <button
            type="button"
            onClick={onSelect}
            className="rounded-xl border border-blue-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-600 transition-all hover:bg-blue-50 dark:border-blue-800 dark:bg-slate-800 dark:text-blue-300 dark:hover:bg-slate-700"
          >
            Focar paciente
          </button>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-blue-100/80 pt-3 dark:border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <Calendar size={14} className="text-blue-500" />
          <span>Última consulta: <strong>{data.lastAppointment ?? 'Recente'}</strong></span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <FileText size={14} className="text-blue-500" />
          <span>Avaliações registradas: <strong>{data.evaluationsCount}</strong></span>
        </div>
      </div>
    </div>
  );
}
