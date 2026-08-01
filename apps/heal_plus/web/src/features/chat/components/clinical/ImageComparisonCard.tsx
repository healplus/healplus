import { useState } from 'react';
import { ArrowLeftRight, Eye, ShieldCheck } from 'lucide-react';
import type { ImageComparisonCardData } from '../../types';

interface ImageComparisonCardProps {
  data: ImageComparisonCardData;
}

export function ImageComparisonCard({ data }: ImageComparisonCardProps) {
  const [sliderPos, setSliderPos] = useState(50);
  const [isSliderActive, setIsSliderActive] = useState(false);

  return (
    <div className="my-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 dark:border-slate-800">
        <h4 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 flex items-center gap-2">
          <ArrowLeftRight size={14} /> Comparativo Visual das Avaliações
        </h4>
        <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
          Arrastador interativo
        </span>
      </div>

      <div className="mt-3 relative h-56 sm:h-64 w-full overflow-hidden rounded-xl bg-slate-950 select-none">
        {/* Previous Image */}
        <img
          src={data.previousImageUrl}
          alt={`Avaliação anterior (${data.previousDate})`}
          className="absolute inset-0 h-full w-full object-cover"
        />

        {/* Current Image overlay with clip-path */}
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ clipPath: `polygon(${sliderPos}% 0, 100% 0, 100% 100%, ${sliderPos}% 100%)` }}
        >
          <img
            src={data.currentImageUrl}
            alt={`Avaliação atual (${data.currentDate})`}
            className="absolute inset-0 h-full w-full object-cover"
          />
        </div>

        {/* Split Divider line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_10px_rgba(0,0,0,0.5)] cursor-ew-resize z-10"
          style={{ left: `${sliderPos}%` }}
        >
          <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg">
            <ArrowLeftRight size={14} />
          </div>
        </div>

        {/* Range Slider Overlay */}
        <input
          type="range"
          min="0"
          max="100"
          value={sliderPos}
          onChange={(e) => setSliderPos(Number(e.target.value))}
          aria-label="Controle deslizante de comparação de imagens"
          className="absolute inset-0 opacity-0 cursor-ew-resize w-full h-full z-20"
        />

        {/* Date Labels */}
        <div className="absolute top-3 left-3 rounded-lg bg-black/70 px-2.5 py-1 text-[11px] font-bold text-white backdrop-blur-md">
          Anterior: {data.previousDate}
        </div>
        <div className="absolute top-3 right-3 rounded-lg bg-blue-600/90 px-2.5 py-1 text-[11px] font-bold text-white backdrop-blur-md">
          Atual: {data.currentDate}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-600 dark:text-slate-300">
        <p className="font-medium">{data.metricsSummary}</p>
        <span className="shrink-0 flex items-center gap-1 text-[11px] text-slate-400">
          <ShieldCheck size={13} className="text-blue-500" /> Imagem clínica autorizada
        </span>
      </div>
    </div>
  );
}
