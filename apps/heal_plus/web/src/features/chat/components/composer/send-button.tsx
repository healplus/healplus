import { ArrowUp, StopCircle, Loader2 } from 'lucide-react';

interface SendButtonProps {
  isSubmitting: boolean;
  isGenerating: boolean;
  disabled: boolean;
  onSend: () => void;
  onStop?: () => void;
}

export function SendButton({
  isSubmitting,
  isGenerating,
  disabled,
  onSend,
  onStop
}: SendButtonProps) {
  if (isGenerating && onStop) {
    return (
      <button
        type="button"
        onClick={onStop}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-600 text-white shadow-md transition-all hover:bg-red-700 active:scale-95"
        title="Interromper geração"
        aria-label="Interromper geração"
      >
        <StopCircle size={18} />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onSend}
      disabled={disabled || isSubmitting}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow-md shadow-blue-600/20 transition-all active:scale-95 ${
        disabled || isSubmitting
          ? 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none dark:bg-slate-800 dark:text-slate-600'
          : 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500'
      }`}
      title="Enviar mensagem (Enter)"
      aria-label="Enviar mensagem"
    >
      {isSubmitting ? (
        <Loader2 size={18} className="animate-spin" />
      ) : (
        <ArrowUp size={18} strokeWidth={2.5} />
      )}
    </button>
  );
}
