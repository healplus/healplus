import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import type {
  ChatMessage,
  ChatSession,
  AIMode,
  ProcessingStage,
  ChatAttachment,
  PatientContext,
  StructuredClinicalData
} from '../types';
import { generateAiReply } from '../aiChatService';
import {
  loadAiProviderConfig,
  createDefaultAiProviderConfig,
  type AiProviderConfig
} from '../aiProvider';
import { buildClinicalAgentPrompt } from '../clinicalAgent';

const CHAT_STORAGE_KEY = 'healplus_ai_chat_sessions_v2';

export function useAiChat(userId = 'default-user', initialPatientContext?: PatientContext) {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    try {
      const stored = sessionStorage.getItem(CHAT_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored) as ChatSession[];
      }
    } catch {
      // ignore
    }
    return [];
  });

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [stage, setStage] = useState<ProcessingStage>('idle');
  const [composerValue, setComposerValue] = useState('');
  const [mode, setMode] = useState<AIMode>('assistant');
  const [internalSearchEnabled, setInternalSearchEnabled] = useState(true);
  const [externalSearchEnabled, setExternalSearchEnabled] = useState(false);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [patientContext, setPatientContext] = useState<PatientContext | undefined>(initialPatientContext);

  const [providerConfig, setProviderConfig] = useState<AiProviderConfig>(() => {
    return loadAiProviderConfig(userId) || createDefaultAiProviderConfig('google');
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      // ignore
    }
  }, [sessions]);

  // Create initial session if none exists
  useEffect(() => {
    if (sessions.length === 0) {
      const newSession: ChatSession = {
        id: `sess-${Date.now()}`,
        title: 'Nova conversa clínica',
        messages: [],
        createdAt: Date.now(),
        patientContext
      };
      setSessions([newSession]);
      setCurrentSessionId(newSession.id);
    } else if (!currentSessionId) {
      setCurrentSessionId(sessions[0].id);
    }
  }, []);

  const activeSession = useMemo(() => {
    return sessions.find((s) => s.id === currentSessionId) || sessions[0] || null;
  }, [sessions, currentSessionId]);

  const activeMessages = activeSession ? activeSession.messages : [];

  const updateActiveSession = useCallback(
    (updater: (session: ChatSession) => ChatSession) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === (currentSessionId || prev[0]?.id)) {
            return updater(s);
          }
          return s;
        })
      );
    },
    [currentSessionId]
  );

  const handleNewSession = useCallback(() => {
    const newSession: ChatSession = {
      id: `sess-${Date.now()}`,
      title: 'Nova conversa clínica',
      messages: [],
      createdAt: Date.now(),
      patientContext
    };
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setComposerValue('');
    setAttachments([]);
  }, [patientContext]);

  const handleRenameSession = useCallback((id: string, newTitle: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title: newTitle } : s))
    );
  }, []);

  const handlePinSession = useCallback((id: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, isPinned: !s.isPinned } : s))
    );
  }, []);

  const handleArchiveSession = useCallback((id: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, isArchived: true } : s))
    );
  }, []);

  const handleDeleteSession = useCallback(
    (id: string) => {
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (currentSessionId === id && next.length > 0) {
          setCurrentSessionId(next[0].id);
        }
        return next;
      });
    },
    [currentSessionId]
  );

  const handleClearCurrentMessages = useCallback(() => {
    updateActiveSession((s) => ({ ...s, messages: [] }));
  }, [updateActiveSession]);

  const handleCancelGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStage('cancelled');
    setTimeout(() => setStage('idle'), 1500);
  }, []);

  const handleSendMessage = useCallback(
    async (textOverride?: string) => {
      const textToSend = textOverride || composerValue;
      if (!textToSend.trim() && attachments.length === 0) return;

      const userMsgId = `usr-${Date.now()}`;
      const userMessage: ChatMessage = {
        id: userMsgId,
        role: 'user',
        content: textToSend.trim(),
        timestamp: Date.now(),
        attachments: [...attachments],
        patientContext
      };

      // Add user message to active session
      updateActiveSession((s) => {
        const newTitle = s.messages.length === 0 ? textToSend.slice(0, 32) || 'Consulta de IA' : s.title;
        return {
          ...s,
          title: newTitle,
          messages: [...s.messages, userMessage],
          patientContext: patientContext || s.patientContext
        };
      });

      // Clear composer
      if (!textOverride) setComposerValue('');
      setAttachments([]);

      // Start KokonutUI AI Text Loading processing stages
      setStage('retrieving-context');

      try {
        await new Promise((resolve) => setTimeout(resolve, 600));
        setStage('analyzing');
        await new Promise((resolve) => setTimeout(resolve, 800));

        if (mode === 'evolution-comparison') {
          setStage('comparing');
          await new Promise((resolve) => setTimeout(resolve, 700));
        }

        setStage('generating');

        // Build clinical system prompt
        const systemPrompt = buildClinicalAgentPrompt({
          appointments: [],
          evaluationsByPatient: {},
          includeClinicalContext: true,
          patients: patientContext
            ? [
                {
                  id: patientContext.id,
                  name: patientContext.displayName,
                  phone: '',
                  email: '',
                  birthDate: '',
                  notes: '',
                  archived: false,
                  createdAt: new Date().toISOString(),
                  updatedAt: patientContext.lastAppointmentAt || new Date().toISOString()
                }
              ]
            : []
        });

        const history = [...activeMessages, userMessage].map((m) => ({
          role: m.role,
          content: m.content
        }));

        const replyText = await generateAiReply({
          config: providerConfig,
          messages: history,
          systemPrompt,
          thinkingLevel: 'minimal'
        });

        setStage('streaming');

        // Check if response warrants structured clinical card
        let clinicalData: StructuredClinicalData | undefined = undefined;

        if (patientContext && (mode === 'clinical-analysis' || mode === 'assistant')) {
          clinicalData = {
            patientSummary: {
              name: patientContext.displayName,
              maskedIdentifier: patientContext.maskedIdentifier,
              lastAppointment: patientContext.lastAppointmentAt || 'Recente',
              evaluationsCount: 4,
              status: 'Acompanhamento Ativo'
            }
          };
        } else if (mode === 'evolution-comparison') {
          clinicalData = {
            woundEvolution: {
              initialDate: '12/05/2026',
              currentDate: '28/07/2026',
              dimensions: '4.2 x 2.8 cm',
              areaEstimate: '11.7 cm²',
              healthScore: 82,
              roiVariationPercentage: 18.5,
              trend: 'improving',
              requiresReview: true
            },
            imageComparison: {
              previousImageUrl: '/images/healplus-login-banner.jpg',
              previousDate: '12/05/2026',
              currentImageUrl: '/images/healplus-login-banner.jpg',
              currentDate: '28/07/2026',
              metricsSummary: 'Redução de 18.5% da área total com granulação saudável.'
            }
          };
        } else if (mode === 'report-draft') {
          clinicalData = {
            reportDraft: {
              title: 'Relatório de Evolução da Lesão',
              content: replyText.slice(0, 400) + '...'
            }
          };
        }

        const assistantMsgId = `ast-${Date.now()}`;
        const assistantMessage: ChatMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: replyText,
          timestamp: Date.now(),
          provider: providerConfig.provider,
          model: providerConfig.model,
          clinicalData
        };

        updateActiveSession((s) => ({
          ...s,
          messages: [...s.messages, assistantMessage]
        }));

        setStage('completed');
        setTimeout(() => setStage('idle'), 1000);
      } catch (err: any) {
        setStage('error');
        const assistantMsgId = `ast-err-${Date.now()}`;
        const errorMessage: ChatMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: err.message || 'Não foi possível concluir a consulta de IA. Verifique sua chave ou conexão.',
          error: true,
          timestamp: Date.now()
        };

        updateActiveSession((s) => ({
          ...s,
          messages: [...s.messages, errorMessage]
        }));
      }
    },
    [
      composerValue,
      attachments,
      patientContext,
      activeMessages,
      mode,
      providerConfig,
      updateActiveSession
    ]
  );

  const handleEditUserMessage = useCallback(
    (id: string, newText: string) => {
      updateActiveSession((s) => {
        const msgIdx = s.messages.findIndex((m) => m.id === id);
        if (msgIdx === -1) return s;
        const truncated = s.messages.slice(0, msgIdx);
        return { ...s, messages: truncated };
      });
      handleSendMessage(newText);
    },
    [updateActiveSession, handleSendMessage]
  );

  const handleRegenerateLastResponse = useCallback(() => {
    if (activeMessages.length === 0) return;
    const lastUserMsg = [...activeMessages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg) {
      updateActiveSession((s) => {
        let lastUserIdx = -1;
        for (let i = s.messages.length - 1; i >= 0; i--) {
          if (s.messages[i].role === 'user') {
            lastUserIdx = i;
            break;
          }
        }
        if (lastUserIdx === -1) return s;
        return { ...s, messages: s.messages.slice(0, lastUserIdx + 1) };
      });
      handleSendMessage(lastUserMsg.content);
    }
  }, [activeMessages, updateActiveSession, handleSendMessage]);

  const handleFeedbackMessage = useCallback(
    (id: string, type: 'positive' | 'negative') => {
      updateActiveSession((s) => ({
        ...s,
        messages: s.messages.map((m) => (m.id === id ? { ...m, feedback: type } : m))
      }));
    },
    [updateActiveSession]
  );

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    activeSession,
    activeMessages,
    stage,
    composerValue,
    setComposerValue,
    mode,
    setMode,
    internalSearchEnabled,
    setInternalSearchEnabled,
    externalSearchEnabled,
    setExternalSearchEnabled,
    attachments,
    setAttachments,
    patientContext,
    setPatientContext,
    providerConfig,
    setProviderConfig,
    handleNewSession,
    handleRenameSession,
    handlePinSession,
    handleArchiveSession,
    handleDeleteSession,
    handleClearCurrentMessages,
    handleSendMessage,
    handleCancelGeneration,
    handleEditUserMessage,
    handleRegenerateLastResponse,
    handleFeedbackMessage
  };
}
