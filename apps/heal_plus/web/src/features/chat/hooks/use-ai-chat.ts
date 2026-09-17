import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { generateAiReply, type AiChatMessage } from '../aiChatService';
import { HEALPLUS_CHAT_STORAGE_PREFIX } from '../../auth/sessionLifecycle';
import { buildClinicalAgentPrompt } from '../clinicalAgent';
import {
  createAiTransmissionAuthorization,
  recordAiTransmissionConsent,
  toAiTransmissionReceipt
} from '../externalTransmission';
import {
  createDefaultAiProviderConfig,
  loadAiProviderConfig,
  type AiProviderConfig
} from '../aiProvider';
import type {
  AIMode,
  ChatAttachment,
  ChatMessage,
  ChatSession,
  PatientContext,
  ProcessingStage,
  StructuredClinicalData
} from '../types';

const MAX_SHARED_HISTORY_MESSAGES = 6;

type PendingTransmissionKind = 'edit' | 'new' | 'retry';

interface PendingTransmission {
  attachments: ChatAttachment[];
  content: string;
  history: ChatMessage[];
  id: string;
  kind: PendingTransmissionKind;
  localMessageId?: string;
  sessionId: string;
}

interface SessionStore {
  currentSessionId: string;
  ownerId: string;
  sessions: ChatSession[];
}

function createSession(patientContext?: PatientContext): ChatSession {
  const now = Date.now();
  return {
    id: `sess-${now}-${Math.random().toString(36).slice(2, 8)}`,
    title: 'Nova conversa clínica',
    messages: [],
    createdAt: now,
    patientContext
  };
}

function hydrateSessionStore(userId: string, patientContext?: PatientContext): SessionStore {
  try {
    const parsed = JSON.parse(
      sessionStorage.getItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}${userId}`) ?? '[]'
    ) as unknown;
    if (Array.isArray(parsed) && parsed.length > 0) {
      const sessions = parsed as ChatSession[];
      return { ownerId: userId, sessions, currentSessionId: sessions[0].id };
    }
  } catch {
    // A conversa continua disponível somente em memória.
  }
  const session = createSession(patientContext);
  return { ownerId: userId, sessions: [session], currentSessionId: session.id };
}

export function useAiChat(userId = 'default-user', initialPatientContext?: PatientContext) {
  const [sessionStore, setSessionStore] = useState<SessionStore>(() =>
    hydrateSessionStore(userId, initialPatientContext)
  );
  const [stage, setStage] = useState<ProcessingStage>('idle');
  const [composerValue, setComposerValue] = useState('');
  const [mode, setMode] = useState<AIMode>('assistant');
  const [internalSearchEnabled, setInternalSearchEnabled] = useState(true);
  const [externalSearchEnabled, setExternalSearchEnabled] = useState(false);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [patientContext, setPatientContext] = useState<PatientContext | undefined>(initialPatientContext);
  const [pendingTransmission, setPendingTransmission] = useState<PendingTransmission | null>(null);
  const [providerConfig, setProviderConfigState] = useState<AiProviderConfig>(() =>
    loadAiProviderConfig(userId) || createDefaultAiProviderConfig('google')
  );

  const abortControllerRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sessions = sessionStore.ownerId === userId ? sessionStore.sessions : [];
  const currentSessionId = sessionStore.ownerId === userId
    ? sessionStore.currentSessionId
    : '';

  useEffect(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    busyRef.current = false;
    setSessionStore(hydrateSessionStore(userId, initialPatientContext));
    setProviderConfigState(loadAiProviderConfig(userId) || createDefaultAiProviderConfig('google'));
    setComposerValue('');
    setAttachments([]);
    setPatientContext(initialPatientContext);
    setPendingTransmission(null);
    setStage('idle');
  }, [userId, initialPatientContext]);

  useEffect(() => {
    if (sessionStore.ownerId !== userId) return;
    try {
      sessionStorage.setItem(
        `${HEALPLUS_CHAT_STORAGE_PREFIX}${userId}`,
        JSON.stringify(sessionStore.sessions)
      );
    } catch {
      // A conversa continua disponível somente em memória.
    }
  }, [sessionStore, userId]);

  useEffect(() => () => {
    abortControllerRef.current?.abort();
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
  }, []);

  const scheduleIdle = useCallback((delay = 1000) => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(() => setStage('idle'), delay);
  }, []);

  const activeSession = useMemo(
    () => sessions.find(session => session.id === currentSessionId) || sessions[0] || null,
    [currentSessionId, sessions]
  );
  const activeMessages = activeSession?.messages ?? [];

  const updateSession = useCallback(
    (sessionId: string, updater: (session: ChatSession) => ChatSession) => {
      setSessionStore(previous => {
        if (previous.ownerId !== userId) return previous;
        return {
          ...previous,
          sessions: previous.sessions.map(session =>
            session.id === sessionId ? updater(session) : session
          )
        };
      });
    },
    [userId]
  );

  const updateActiveSession = useCallback(
    (updater: (session: ChatSession) => ChatSession) => {
      if (activeSession) updateSession(activeSession.id, updater);
    },
    [activeSession, updateSession]
  );

  const setCurrentSessionId = useCallback((sessionId: string) => {
    setSessionStore(previous => previous.ownerId === userId
      ? { ...previous, currentSessionId: sessionId }
      : previous
    );
  }, [userId]);

  const handleNewSession = useCallback(() => {
    const session = createSession(patientContext);
    setSessionStore(previous => previous.ownerId === userId
      ? {
          ...previous,
          sessions: [session, ...previous.sessions],
          currentSessionId: session.id
        }
      : previous
    );
    setComposerValue('');
    setAttachments([]);
    setPendingTransmission(null);
  }, [patientContext, userId]);

  const handleRenameSession = useCallback((id: string, newTitle: string) => {
    updateSession(id, session => ({ ...session, title: newTitle }));
  }, [updateSession]);

  const handlePinSession = useCallback((id: string) => {
    updateSession(id, session => ({ ...session, isPinned: !session.isPinned }));
  }, [updateSession]);

  const handleArchiveSession = useCallback((id: string) => {
    updateSession(id, session => ({ ...session, isArchived: true }));
  }, [updateSession]);

  const handleDeleteSession = useCallback((id: string) => {
    setSessionStore(previous => {
      if (previous.ownerId !== userId) return previous;
      let next = previous.sessions.filter(session => session.id !== id);
      if (next.length === 0) next = [createSession(patientContext)];
      return {
        ...previous,
        sessions: next,
        currentSessionId: previous.currentSessionId === id
          ? next[0].id
          : previous.currentSessionId
      };
    });
  }, [patientContext, userId]);

  const handleClearCurrentMessages = useCallback(() => {
    updateActiveSession(session => ({ ...session, messages: [] }));
  }, [updateActiveSession]);

  const handleCancelGeneration = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setStage('cancelled');
    scheduleIdle(1200);
  }, [scheduleIdle]);

  const requestTransmission = useCallback((
    content: string,
    kind: PendingTransmissionKind,
    localMessageId?: string,
    transmissionAttachments: ChatAttachment[] = attachments
  ) => {
    const trimmed = content.trim();
    if (!trimmed || !activeSession || busyRef.current) return;

    const localIndex = localMessageId
      ? activeSession.messages.findIndex(message => message.id === localMessageId)
      : -1;
    const history = kind === 'new'
      ? activeSession.messages
      : activeSession.messages.slice(0, Math.max(0, localIndex));

    setPendingTransmission({
      attachments: [...transmissionAttachments],
      content: trimmed,
      history,
      id: `pending-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      kind,
      localMessageId,
      sessionId: activeSession.id
    });
  }, [activeSession, attachments]);

  const handleSendMessage = useCallback((textOverride?: string) => {
    requestTransmission(textOverride ?? composerValue, 'new');
  }, [composerValue, requestTransmission]);

  const handleCancelTransmission = useCallback(() => {
    setPendingTransmission(null);
  }, []);

  const handleConfirmTransmission = useCallback(async (includeConversationHistory: boolean) => {
    const pending = pendingTransmission;
    if (!pending || busyRef.current) return;

    busyRef.current = true;
    const authorization = createAiTransmissionAuthorization(
      providerConfig,
      includeConversationHistory
    );
    const receipt = toAiTransmissionReceipt(authorization);
    recordAiTransmissionConsent(userId, receipt);
    const history: AiChatMessage[] = includeConversationHistory
      ? pending.history
          .filter(message => !message.error && message.content.trim())
          .slice(-MAX_SHARED_HISTORY_MESSAGES)
          .map(message => ({ role: message.role, content: message.content }))
      : [];
    const outboundMessages: AiChatMessage[] = [
      ...history,
      { role: 'user', content: pending.content }
    ];

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setPendingTransmission(null);
    setStage('retrieving-context');

    const now = Date.now();
    updateSession(pending.sessionId, session => {
      if (pending.kind === 'new') {
        const userMessage: ChatMessage = {
          id: `usr-${now}`,
          role: 'user',
          content: pending.content,
          timestamp: now,
          attachments: pending.attachments,
          patientContext
        };
        return {
          ...session,
          title: session.messages.length === 0
            ? pending.content.slice(0, 32)
            : session.title,
          messages: [...session.messages, userMessage],
          patientContext: patientContext || session.patientContext
        };
      }

      const index = session.messages.findIndex(message => message.id === pending.localMessageId);
      if (index < 0) return session;
      if (pending.kind === 'edit') {
        const editedMessage = {
          ...session.messages[index],
          content: pending.content,
          timestamp: now
        };
        return { ...session, messages: [...session.messages.slice(0, index), editedMessage] };
      }
      return { ...session, messages: session.messages.slice(0, index + 1) };
    });

    if (pending.kind === 'new') {
      setComposerValue('');
      setAttachments([]);
    }

    try {
      setStage('analyzing');
      const systemPrompt = buildClinicalAgentPrompt({
        appointments: [],
        evaluationsByPatient: {},
        includeClinicalContext: false,
        patients: []
      });
      setStage('generating');
      const replyText = await generateAiReply({
        authorization,
        config: providerConfig,
        messages: outboundMessages,
        signal: controller.signal,
        systemPrompt,
        thinkingLevel: 'minimal'
      });

      setStage('streaming');
      let clinicalData: StructuredClinicalData | undefined;
      if (mode === 'report-draft') {
        clinicalData = {
          reportDraft: {
            title: 'Rascunho de relatório clínico',
            content: replyText.slice(0, 400)
          }
        };
      }
      const assistantMessage: ChatMessage = {
        id: `ast-${Date.now()}`,
        role: 'assistant',
        content: replyText,
        timestamp: Date.now(),
        provider: providerConfig.provider,
        model: providerConfig.model,
        clinicalData,
        transmissionConsentId: receipt.id
      };
      updateSession(pending.sessionId, session => ({
        ...session,
        messages: [...session.messages, assistantMessage]
      }));
      setStage('completed');
      scheduleIdle();
    } catch (error) {
      if (controller.signal.aborted) {
        setStage('cancelled');
        scheduleIdle(1200);
      } else {
        const message = error instanceof Error
          ? error.message
          : 'Não foi possível concluir a consulta de IA. Verifique a conexão e tente novamente.';
        updateSession(pending.sessionId, session => ({
          ...session,
          messages: [
            ...session.messages,
            {
              id: `ast-err-${Date.now()}`,
              role: 'assistant',
              content: message,
              error: true,
              timestamp: Date.now()
            }
          ]
        }));
        setStage('error');
      }
    } finally {
      if (abortControllerRef.current === controller) abortControllerRef.current = null;
      busyRef.current = false;
    }
  }, [
    mode,
    patientContext,
    pendingTransmission,
    providerConfig,
    scheduleIdle,
    updateSession,
    userId
  ]);

  const handleEditUserMessage = useCallback((id: string, newText: string) => {
    const message = activeMessages.find(item => item.id === id);
    requestTransmission(newText, 'edit', id, message?.attachments ?? []);
  }, [activeMessages, requestTransmission]);

  const handleRegenerateLastResponse = useCallback(() => {
    const lastUserMessage = [...activeMessages].reverse().find(message => message.role === 'user');
    if (!lastUserMessage) return;
    requestTransmission(
      lastUserMessage.content,
      'retry',
      lastUserMessage.id,
      lastUserMessage.attachments ?? []
    );
  }, [activeMessages, requestTransmission]);

  const handleFeedbackMessage = useCallback((id: string, type: 'positive' | 'negative') => {
    updateActiveSession(session => ({
      ...session,
      messages: session.messages.map(message =>
        message.id === id ? { ...message, feedback: type } : message
      )
    }));
  }, [updateActiveSession]);

  const setProviderConfig = useCallback((config: AiProviderConfig) => {
    setProviderConfigState(config);
    setPendingTransmission(null);
  }, []);

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
    pendingTransmission,
    pendingTransmissionHistoryCount: pendingTransmission?.history.filter(message => !message.error).length ?? 0,
    handleNewSession,
    handleRenameSession,
    handlePinSession,
    handleArchiveSession,
    handleDeleteSession,
    handleClearCurrentMessages,
    handleSendMessage,
    handleCancelGeneration,
    handleCancelTransmission,
    handleConfirmTransmission,
    handleEditUserMessage,
    handleRegenerateLastResponse,
    handleFeedbackMessage
  };
}
