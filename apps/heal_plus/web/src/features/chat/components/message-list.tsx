import { useEffect, useRef } from 'react';
import type { ChatMessage, PatientContext, ProcessingStage } from '../types';
import { UserMessage } from './user-message';
import { AssistantMessage } from './assistant-message';
import { ChatEmptyState } from './chat-empty-state';
import { AIProcessingStatus } from './loading/ai-processing-status';

interface MessageListProps {
  messages: ChatMessage[];
  stage: ProcessingStage;
  onCancelProcessing?: () => void;
  onSelectSuggestion: (text: string) => void;
  patientContext?: PatientContext;
  onOpenPatientSelector: () => void;
  onEditUserMessage?: (id: string, newText: string) => void;
  onRegenerateLastResponse?: () => void;
  onFeedbackMessage?: (id: string, type: 'positive' | 'negative') => void;
}

export function MessageList({
  messages,
  stage,
  onCancelProcessing,
  onSelectSuggestion,
  patientContext,
  onOpenPatientSelector,
  onEditUserMessage,
  onRegenerateLastResponse,
  onFeedbackMessage
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [messages, stage]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto px-4">
        <ChatEmptyState
          onSelectSuggestion={onSelectSuggestion}
          patientContext={patientContext}
          onOpenPatientSelector={onOpenPatientSelector}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-4xl space-y-4">
        {messages.map((msg, index) => {
          if (msg.role === 'user') {
            return (
              <UserMessage
                key={msg.id}
                message={msg}
                onEditMessage={onEditUserMessage}
              />
            );
          }

          const isLastAssistantMsg =
            msg.role === 'assistant' && index === messages.length - 1;

          return (
            <AssistantMessage
              key={msg.id}
              message={msg}
              onRegenerate={isLastAssistantMsg ? onRegenerateLastResponse : undefined}
              onFeedback={onFeedbackMessage ? (type) => onFeedbackMessage(msg.id, type) : undefined}
            />
          );
        })}

        {/* KokonutUI AI Text Loading Processing Stage */}
        <AIProcessingStatus stage={stage} onCancel={onCancelProcessing} />

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
