import { useState } from 'react';
import { Copy, Check, RotateCw, ThumbsUp, ThumbsDown } from 'lucide-react';

interface MessageActionsProps {
  content: string;
  onRegenerate?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
  initialFeedback?: 'positive' | 'negative' | null;
}

export function MessageActions({
  content,
  onRegenerate,
  onFeedback,
  initialFeedback = null
}: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(initialFeedback);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedbackClick = (type: 'positive' | 'negative') => {
    const nextState = feedback === type ? null : type;
    setFeedback(nextState);
    if (onFeedback && nextState) {
      onFeedback(nextState);
    }
  };

  return (
    <div className="mt-2.5 flex items-center gap-1 opacity-90 transition-opacity hover:opacity-100">
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        title="Copiar resposta"
      >
        {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
        <span>{copied ? 'Copiado' : 'Copiar'}</span>
      </button>

      {onRegenerate && (
        <button
          type="button"
          onClick={onRegenerate}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          title="Regenerar resposta"
        >
          <RotateCw size={13} />
          <span>Regenerar</span>
        </button>
      )}

      <div className="ml-2 flex items-center gap-0.5 border-l border-slate-200 pl-2 dark:border-slate-800">
        <button
          type="button"
          onClick={() => handleFeedbackClick('positive')}
          className={`rounded-lg p-1 text-xs transition-colors ${
            feedback === 'positive'
              ? 'bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400 font-bold'
              : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800'
          }`}
          title="Resposta útil"
        >
          <ThumbsUp size={13} />
        </button>
        <button
          type="button"
          onClick={() => handleFeedbackClick('negative')}
          className={`rounded-lg p-1 text-xs transition-colors ${
            feedback === 'negative'
              ? 'bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400 font-bold'
              : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800'
          }`}
          title="Resposta precisa de ajustes"
        >
          <ThumbsDown size={13} />
        </button>
      </div>
    </div>
  );
}
