import { useState } from 'react';
import { Copy, Check, FileDown, Edit3, BookmarkCheck } from 'lucide-react';
import type { ReportDraftCardData } from '../../types';

interface ReportDraftCardProps {
  data: ReportDraftCardData;
  onSaveAsDraft?: (content: string) => void;
}

export function ReportDraftCard({ data, onSaveAsDraft }: ReportDraftCardProps) {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(data.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSave = () => {
    onSaveAsDraft?.(data.content);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="my-3 rounded-2xl border border-blue-200/90 bg-gradient-to-b from-blue-50/50 to-white p-4 shadow-sm dark:border-blue-900/60 dark:from-slate-900 dark:to-slate-950">
      <div className="flex items-center justify-between border-b border-blue-100 pb-3 dark:border-slate-800">
        <h4 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 flex items-center gap-2">
          <Edit3 size={14} /> {data.title || 'Rascunho de Relatório Clínico'}
        </h4>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-xl border border-blue-200 bg-white px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 dark:border-blue-800 dark:bg-slate-800 dark:text-blue-300"
          >
            {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
            <span>{copied ? 'Copiado' : 'Copiar'}</span>
          </button>

          {onSaveAsDraft && (
            <button
              type="button"
              onClick={handleSave}
              className="inline-flex items-center gap-1 rounded-xl bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-700 shadow-sm"
            >
              {saved ? <BookmarkCheck size={13} /> : <FileDown size={13} />}
              <span>{saved ? 'Salvo' : 'Salvar Rascunho'}</span>
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-slate-100 bg-white p-3.5 text-xs text-slate-800 leading-relaxed font-sans dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200">
        <pre className="whitespace-pre-wrap font-sans">{data.content}</pre>
      </div>
    </div>
  );
}
