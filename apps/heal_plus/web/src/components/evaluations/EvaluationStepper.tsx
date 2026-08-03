import { Check } from 'lucide-react';

interface EvaluationStepperProps {
  steps: string[];
  currentStep: number;
}

export function EvaluationStepper({ steps, currentStep }: EvaluationStepperProps) {
  return (
    <nav aria-label="Progresso da avaliação clínica">
      <p aria-live="polite" className="sr-only" role="status">
        Etapa {currentStep + 1} de {steps.length}: {steps[currentStep]}
      </p>
      <ol className="grid gap-2 rounded-card border border-heal-line bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 md:grid-cols-4">
        {steps.map((step, index) => {
          const active = index === currentStep;
          const done = index < currentStep;
          return (
            <li
              aria-current={active ? 'step' : undefined}
              key={step}
              className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-bold motion-safe:transition ${
                active
                  ? 'bg-heal-softBlue text-cyan-800 dark:text-cyan-200'
                  : done
                    ? 'bg-heal-tealSoft text-emerald-800 dark:text-emerald-200'
                    : 'text-heal-muted dark:text-zinc-400'
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs ${
                  done ? 'bg-emerald-700 text-white' : active ? 'bg-cyan-700 text-white' : 'bg-slate-100 text-slate-500'
                }`}
              >
                {done ? <Check className="h-4 w-4" /> : index + 1}
              </span>
              <span className="truncate">{step}</span>
              <span className="sr-only">{done ? ', concluída' : active ? ', atual' : ', não iniciada'}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
