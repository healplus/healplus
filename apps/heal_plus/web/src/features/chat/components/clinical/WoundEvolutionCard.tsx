import { AlertTriangle, TrendingDown, TrendingUp, Minus, ShieldAlert } from 'lucide-react';
import type { WoundEvolutionCardData } from '../../types';

interface WoundEvolutionCardProps {
  data: WoundEvolutionCardData;
}

export function WoundEvolutionCard({ data }: WoundEvolutionCardProps) {
  const isImproving = data.trend === 'improving';
  const isDeteriorating = data.trend === 'deteriorating';

  return (
    <div className="my-3 rounded-2xl border border-blue-200/80 bg-white p-4 shadow-sm dark:border-blue-900/50 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
        <h4 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
          Evolução Longitudinal da Lesão
        </h4>
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
          {data.initialDate} → {data.currentDate}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Dimensões</p>
          <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">{data.dimensions}</p>
        </div>

        <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Área Estimada</p>
          <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">{data.areaEstimate}</p>
        </div>

        <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Variação ROI</p>
          <p className={`mt-1 flex items-center gap-1 text-sm font-black ${
            isImproving ? 'text-emerald-600 dark:text-emerald-400' : isDeteriorating ? 'text-amber-600 dark:text-amber-400' : 'text-slate-700 dark:text-slate-300'
          }`}>
            {isImproving ? <TrendingDown size={16} /> : isDeteriorating ? <TrendingUp size={16} /> : <Minus size={16} />}
            {data.roiVariationPercentage > 0 ? `-${data.roiVariationPercentage}%` : `+${Math.abs(data.roiVariationPercentage)}%`}
          </p>
        </div>

        <div className="rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Health Score</p>
          <p className="mt-1 text-sm font-black text-blue-600 dark:text-blue-400">{data.healthScore}/100</p>
        </div>
      </div>

      {data.requiresReview && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200/60 dark:border-amber-900/40">
          <ShieldAlert size={16} className="shrink-0 text-amber-600" />
          <span>Sinalização técnica: alteração na proporção tecidual requer revisão presencial.</span>
        </div>
      )}
    </div>
  );
}
