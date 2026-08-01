import { useState, useMemo } from 'react';
import { User, X, UserCheck } from 'lucide-react';
import type { AIMode, ChatAttachment, PatientContext } from '../../types';
import { AutoResizeTextarea } from './auto-resize-textarea';
import { AIModeSelector } from './ai-mode-selector';
import { SearchToggle } from './search-toggle';
import { VoiceRecorder } from './voice-recorder';
import { AttachmentButton } from './attachment-button';
import { AttachmentPreview } from './attachment-preview';
import { SendButton } from './send-button';

interface AIComposerProps {
  value: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  mode: AIMode;
  onSelectMode: (mode: AIMode) => void;
  internalSearchEnabled: boolean;
  externalSearchEnabled: boolean;
  onToggleInternalSearch: () => void;
  onToggleExternalSearch: () => void;
  attachments: ChatAttachment[];
  onAddAttachment: (att: ChatAttachment) => void;
  onRemoveAttachment: (id: string) => void;
  patientContext?: PatientContext;
  onRemovePatientContext?: () => void;
  onOpenPatientSelector: () => void;
  isSubmitting?: boolean;
  isGenerating?: boolean;
  onStopGeneration?: () => void;
}

export function AIComposer({
  value,
  onChange,
  onSubmit,
  mode,
  onSelectMode,
  internalSearchEnabled,
  externalSearchEnabled,
  onToggleInternalSearch,
  onToggleExternalSearch,
  attachments,
  onAddAttachment,
  onRemoveAttachment,
  patientContext,
  onRemovePatientContext,
  onOpenPatientSelector,
  isSubmitting = false,
  isGenerating = false,
  onStopGeneration
}: AIComposerProps) {
  const [isFocused, setIsFocused] = useState(false);

  const placeholderText = useMemo(() => {
    if (attachments.some((a) => a.type === 'image')) {
      return 'Pergunte sobre as imagens e avaliações selecionadas...';
    }
    if (patientContext) {
      return `Pergunte sobre o histórico de ${patientContext.displayName}...`;
    }
    return 'Pergunte sobre pacientes, avaliações ou evolução clínica...';
  }, [attachments, patientContext]);

  const handleVoiceTranscript = (text: string) => {
    if (text) {
      onChange(value ? `${value} ${text}` : text);
    }
  };

  const isSendDisabled = !value.trim() && attachments.length === 0;

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-4">
      {/* External Search Anonymization Warning Banner */}
      {externalSearchEnabled && (
        <div className="mb-2 flex items-center justify-between rounded-xl bg-blue-50 px-3 py-1.5 text-xs text-blue-800 dark:bg-blue-950/60 dark:text-blue-200 border border-blue-200/80 dark:border-blue-900/60 animate-in fade-in">
          <span>
            <strong>Pesquisa Web Ativada:</strong> Os dados do paciente serão anonimizados antes da consulta a fontes externas.
          </span>
        </div>
      )}

      {/* Patient Context Chip above composer */}
      {patientContext && (
        <div className="mb-2 flex items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50/90 px-3 py-1 text-xs font-semibold text-blue-800 shadow-sm dark:border-blue-900/60 dark:bg-blue-950/80 dark:text-blue-200">
            <UserCheck size={14} className="text-blue-600 dark:text-blue-400" />
            <span>Contexto: <strong>{patientContext.displayName}</strong></span>
            {patientContext.maskedIdentifier && (
              <span className="font-mono text-[10px] text-blue-600 dark:text-blue-400">
                ({patientContext.maskedIdentifier})
              </span>
            )}
            {onRemovePatientContext && (
              <button
                type="button"
                onClick={onRemovePatientContext}
                className="ml-1 rounded-md p-0.5 text-blue-600 hover:bg-blue-200/60 dark:hover:bg-blue-900"
                title="Remover contexto do paciente"
                aria-label="Remover contexto do paciente"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Integrated Composer Box combining KokonutUI elements */}
      <div
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        className={`relative rounded-2xl border bg-white p-3 shadow-lg transition-all duration-200 dark:bg-slate-900 ${
          isFocused
            ? 'border-blue-500 ring-4 ring-blue-500/10 shadow-blue-500/5 dark:border-blue-500'
            : 'border-slate-200 dark:border-slate-800'
        }`}
      >
        {/* Attachments Preview Row */}
        <AttachmentPreview attachments={attachments} onRemoveAttachment={onRemoveAttachment} />

        {/* Auto-expanding Input Area */}
        <AutoResizeTextarea
          value={value}
          onChange={onChange}
          onSubmit={onSubmit}
          placeholder={placeholderText}
          disabled={isSubmitting || isGenerating}
          minRows={1}
          maxRows={6}
        />

        {/* Integrated Toolbar Footer */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 dark:border-slate-800/80">
          {/* Left Controls Group */}
          <div className="flex flex-wrap items-center gap-1.5">
            <AttachmentButton
              onAddAttachment={onAddAttachment}
              onOpenPatientSelector={onOpenPatientSelector}
              disabled={isSubmitting || isGenerating}
            />

            <AIModeSelector currentMode={mode} onSelectMode={onSelectMode} />

            <SearchToggle
              internalSearchEnabled={internalSearchEnabled}
              externalSearchEnabled={externalSearchEnabled}
              onToggleInternal={onToggleInternalSearch}
              onToggleExternal={onToggleExternalSearch}
            />
          </div>

          {/* Right Controls Group */}
          <div className="flex items-center gap-1.5">
            <VoiceRecorder
              onTranscriptComplete={handleVoiceTranscript}
              disabled={isSubmitting || isGenerating}
            />

            <SendButton
              isSubmitting={isSubmitting}
              isGenerating={isGenerating}
              disabled={isSendDisabled}
              onSend={onSubmit}
              onStop={onStopGeneration}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
