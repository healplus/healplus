import { Sparkles, ShieldCheck, ExternalLink, AlertTriangle } from 'lucide-react';
import type { ChatMessage } from '../types';
import { MarkdownRenderer } from '../../../components/ui/MarkdownRenderer';
import { PatientSummaryCard } from './clinical/PatientSummaryCard';
import { WoundEvolutionCard } from './clinical/WoundEvolutionCard';
import { ImageComparisonCard } from './clinical/ImageComparisonCard';
import { ReportDraftCard } from './clinical/ReportDraftCard';
import { MessageActions } from './message-actions';

interface AssistantMessageProps {
  message: ChatMessage;
  onRegenerate?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
}

export function AssistantMessage({
  message,
  onRegenerate,
  onFeedback
}: AssistantMessageProps) {
  return (
    <div className="my-6 flex items-start gap-3.5 max-w-full animate-in fade-in slide-in-from-bottom-2">
      {/* Heal+ Assistant Avatar Icon */}
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-md shadow-blue-600/20 dark:bg-blue-500">
        <Sparkles size={18} />
      </div>

      <div className="flex-1 min-w-0">
        {/* Header Title & Timestamp */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-bold text-slate-900 dark:text-white">
            Assistente Heal+
          </span>
          {message.model && (
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {message.model}
            </span>
          )}
          <span className="text-[10px] text-slate-400 ml-auto">
            {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
          </span>
        </div>

        {/* Error Container if any */}
        {message.error && (
          <div className="my-2 rounded-2xl border border-red-200 bg-red-50/90 p-3.5 text-xs text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200 flex items-start gap-2">
            <AlertTriangle size={16} className="shrink-0 text-red-600 mt-0.5" />
            <div>
              <p className="font-bold">Ocorreu um imprevisto na resposta</p>
              <p className="mt-0.5">{message.content}</p>
            </div>
          </div>
        )}

        {/* Structured Clinical Cards */}
        {message.clinicalData && (
          <div className="space-y-3 my-2">
            {message.clinicalData.patientSummary && (
              <PatientSummaryCard data={message.clinicalData.patientSummary} />
            )}
            {message.clinicalData.woundEvolution && (
              <WoundEvolutionCard data={message.clinicalData.woundEvolution} />
            )}
            {message.clinicalData.imageComparison && (
              <ImageComparisonCard data={message.clinicalData.imageComparison} />
            )}
            {message.clinicalData.reportDraft && (
              <ReportDraftCard data={message.clinicalData.reportDraft} />
            )}
          </div>
        )}

        {/* Markdown Content */}
        {!message.error && (
          <div className="prose prose-slate max-w-none text-sm text-slate-800 leading-relaxed dark:prose-invert dark:text-slate-200">
            <MarkdownRenderer text={message.content} />
          </div>
        )}

        {/* Sources Citation Block */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-800">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Fontes consultadas:
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              {message.sources.map((src, idx) => (
                <a
                  key={idx}
                  href={src.url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg bg-white px-2 py-1 text-xs text-blue-600 shadow-sm border border-slate-200/80 dark:bg-slate-900 dark:text-blue-400 dark:border-slate-700 hover:underline"
                >
                  <ExternalLink size={11} />
                  <span>{src.title}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Clinical Disclaimer Notice */}
        <div className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-blue-50/60 px-2.5 py-1 text-[11px] font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-100/60 dark:border-blue-900/40">
          <ShieldCheck size={13} className="text-blue-600 dark:text-blue-400" />
          <span>Apoio à decisão clínica. Conteúdo assistido — requer validação profissional.</span>
        </div>

        {/* Message Actions Toolbar */}
        <MessageActions
          content={message.content}
          onRegenerate={onRegenerate}
          onFeedback={onFeedback}
          initialFeedback={message.feedback}
        />
      </div>
    </div>
  );
}
