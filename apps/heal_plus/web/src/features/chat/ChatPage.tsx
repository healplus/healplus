import {
  Bookmark,
  Check,
  ChevronDown,
  Copy,
  Database,
  History,
  KeyRound,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  RotateCw,
  Search,
  SendHorizontal,
  ShieldCheck,
  StopCircle,
  Trash2,
  X
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { Sidebar } from '../../components/layout/sidebar';
import { Topbar } from '../../components/layout/Topbar';
import { LoadingState } from '../../components/ui/LoadingState';
import { MarkdownRenderer } from '../../components/ui/MarkdownRenderer';
import { Modal } from '../../components/ui/Modal';
import type { Appointment, Evaluation, Patient } from '../../lib/types';
import { subscribeAppointments } from '../agenda/agendaService';
import { CHAT_HISTORY_STORAGE_PREFIX } from '../auth/sessionLifecycle';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';
import { AiProviderDialog } from './AiProviderDialog';
import { AiProviderMark } from './AiProviderMark';
import { generateAiReply } from './aiChatService';
import {
  AI_PROVIDERS,
  aiProviderLabel,
  clearAiProviderConfig,
  getAiProviderDefinition,
  loadAiProviderConfig,
  saveAiProviderConfig,
  type AiProviderConfig,
  type AiProviderId
} from './aiProvider';
import { buildClinicalAgentPrompt } from './clinicalAgent';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  error?: boolean;
  model?: string;
  provider?: AiProviderId;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  isSaved?: boolean;
}

const AI_HISTORY_LIMIT = 20;

function nextId(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<Message>;
  return (
    (message.role === 'user' || message.role === 'assistant') &&
    typeof message.id === 'string' &&
    typeof message.content === 'string'
  );
}

function readHistory(key: string): ChatSession[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? '[]') as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is ChatSession => {
      if (!item || typeof item !== 'object') return false;
      const session = item as Partial<ChatSession>;
      return (
        typeof session.id === 'string' &&
        typeof session.title === 'string' &&
        typeof session.createdAt === 'number' &&
        Array.isArray(session.messages) &&
        session.messages.every(isMessage)
      );
    });
  } catch {
    return [];
  }
}

function writeHistory(key: string, history: readonly ChatSession[]): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(history));
  } catch {
    // The current conversation remains available even when browser storage is blocked.
  }
}

export function ChatPage() {
  const { user } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] =
    useState<Record<string, Evaluation[]>>({});
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [thinkingLevel, setThinkingLevel] = useState<'minimal' | 'high'>('minimal');
  const [providerConfig, setProviderConfig] = useState<AiProviderConfig | null>(null);
  const [providerDialogOpen, setProviderDialogOpen] = useState(false);
  const [clinicalContextEnabled, setClinicalContextEnabled] = useState(false);
  const [contextConsentOpen, setContextConsentOpen] = useState(false);
  const [pendingClinicalPrompt, setPendingClinicalPrompt] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [history, setHistory] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [historyTab, setHistoryTab] = useState<'chats' | 'saved'>('chats');
  const [isThinkingMenuOpen, setIsThinkingMenuOpen] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const thinkingMenuRef = useRef<HTMLDivElement>(null);
  const historyKey = useMemo(
    () => (user ? `${CHAT_HISTORY_STORAGE_PREFIX}${user.uid}` : ''),
    [user]
  );
  const activeProvider = getAiProviderDefinition(providerConfig?.provider ?? 'google');
  const activeModelLabel = providerConfig
    ? activeProvider.models.find(model => model.id === providerConfig.model)?.label ?? providerConfig.model
    : activeProvider.models[0]?.label ?? activeProvider.label;

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return undefined;
    }

    setLoading(true);
    const unsubscribePatients = subscribePatients(user.uid, next => {
      setPatients(next);
      setLoading(false);
      void Promise.all(next.map(patient => listEvaluations(user.uid, patient.id)))
        .then(groups => {
          setEvaluationsByPatient(
            Object.fromEntries(next.map((patient, index) => [patient.id, groups[index] ?? []]))
          );
        })
        .catch(() => setEvaluationsByPatient({}));
    });
    const unsubscribeAppointments = subscribeAppointments(user.uid, setAppointments);
    return () => {
      unsubscribePatients();
      unsubscribeAppointments();
    };
  }, [user]);

  useEffect(() => {
    if (!user) {
      setProviderConfig(null);
      return;
    }
    const stored = loadAiProviderConfig(user.uid);
    setProviderConfig(stored);
    setProviderDialogOpen(!stored);
  }, [user]);

  useEffect(() => {
    if (!historyKey) return;
    setHistory(readHistory(historyKey));
    setMessages([]);
    setActiveChatId(null);
  }, [historyKey]);

  useEffect(() => {
    if (!historyKey || messages.length === 0) return undefined;
    const userMessages = messages.filter(message => message.role === 'user');
    if (userMessages.length === 0) return undefined;

    const timeout = window.setTimeout(() => {
      const firstPrompt = userMessages[0].content.trim();
      const title = firstPrompt.length > 52 ? `${firstPrompt.slice(0, 52)}…` : firstPrompt || 'Conversa';
      if (!activeChatId) {
        const id = nextId('redisus-chat');
        const session: ChatSession = {
          id,
          title,
          messages,
          createdAt: Date.now()
        };
        setActiveChatId(id);
        setHistory(current => {
          const next = [session, ...current];
          writeHistory(historyKey, next);
          return next;
        });
        return;
      }

      setHistory(current => {
        const existing = current.find(session => session.id === activeChatId);
        const next = existing
          ? current.map(session => session.id === activeChatId ? { ...session, messages } : session)
          : [{ id: activeChatId, title, messages, createdAt: Date.now() }, ...current];
        writeHistory(historyKey, next);
        return next;
      });
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [activeChatId, historyKey, messages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
  }, [input]);

  useEffect(() => {
    if (!isThinkingMenuOpen) return undefined;
    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (target instanceof Node && thinkingMenuRef.current?.contains(target)) return;
      setIsThinkingMenuOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsThinkingMenuOpen(false);
    }
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isThinkingMenuOpen]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function clinicalPrompt(includeClinicalContext: boolean): string {
    return buildClinicalAgentPrompt({
      appointments,
      evaluationsByPatient,
      includeClinicalContext,
      patients
    });
  }

  async function requestReply(conversation: readonly Message[], includeClinicalContext: boolean) {
    if (!providerConfig || thinking) return;
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setThinking(true);
    setNotice(null);

    try {
      const text = await generateAiReply({
        config: providerConfig,
        messages: conversation
          .filter(message => !message.error)
          .slice(-AI_HISTORY_LIMIT)
          .map(message => ({ role: message.role, content: message.content })),
        signal: controller.signal,
        systemPrompt: clinicalPrompt(includeClinicalContext),
        thinkingLevel
      });
      if (controller.signal.aborted) return;
      setMessages(current => [
        ...current,
        {
          id: nextId('assistant'),
          role: 'assistant',
          content: text,
          model: aiProviderLabel(providerConfig),
          provider: providerConfig.provider
        }
      ]);
    } catch (error) {
      if (controller.signal.aborted) return;
      const detail = error instanceof Error ? error.message : 'Não foi possível consultar o provedor.';
      setMessages(current => [
        ...current,
        {
          id: nextId('assistant-error'),
          role: 'assistant',
          content: `${detail}\n\nRevise a chave, o modelo e a conexão nas configurações do chat.`,
          error: true
        }
      ]);
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setThinking(false);
      }
    }
  }

  async function send(override?: string, includeClinicalContext = clinicalContextEnabled) {
    const question = (override ?? input).trim();
    if (!question || thinking) return;
    if (!providerConfig) {
      setNotice('Conecte sua própria chave de API para enviar mensagens.');
      setProviderDialogOpen(true);
      return;
    }

    const userMessage: Message = {
      id: nextId('user'),
      role: 'user',
      content: question
    };
    const conversation = [...messages, userMessage];
    setMessages(conversation);
    setInput('');
    await requestReply(conversation, includeClinicalContext);
  }

  function cancelReply() {
    abortRef.current?.abort();
    abortRef.current = null;
    setThinking(false);
    setNotice('Resposta interrompida.');
  }

  function handleNewChat() {
    cancelReply();
    setActiveChatId(null);
    setMessages([]);
    setInput('');
    setClinicalContextEnabled(false);
    setNotice(null);
  }

  function handleSelectSession(session: ChatSession) {
    abortRef.current?.abort();
    setThinking(false);
    setActiveChatId(session.id);
    setMessages(session.messages);
    setClinicalContextEnabled(false);
    setIsHistoryOpen(false);
    setNotice(null);
  }

  function toggleBookmark(id: string, event: ReactMouseEvent) {
    event.stopPropagation();
    setHistory(current => {
      const next = current.map(session =>
        session.id === id ? { ...session, isSaved: !session.isSaved } : session
      );
      writeHistory(historyKey, next);
      return next;
    });
  }

  function deleteSession(id: string, event: ReactMouseEvent) {
    event.stopPropagation();
    setHistory(current => {
      const next = current.filter(session => session.id !== id);
      writeHistory(historyKey, next);
      return next;
    });
    if (activeChatId === id) handleNewChat();
  }

  function regenerate(messageId: string) {
    if (thinking || !providerConfig) return;
    const index = messages.findIndex(message => message.id === messageId);
    if (index < 0) return;
    const conversation = messages.slice(0, index);
    if (!conversation.some(message => message.role === 'user')) return;
    setMessages(conversation);
    void requestReply(conversation, clinicalContextEnabled);
  }

  function requestClinicalContext(prompt: string | null = null) {
    if (clinicalContextEnabled) {
      if (prompt) void send(prompt, true);
      else setClinicalContextEnabled(false);
      return;
    }
    setPendingClinicalPrompt(prompt);
    setContextConsentOpen(true);
  }

  function confirmClinicalContext() {
    const prompt = pendingClinicalPrompt;
    setClinicalContextEnabled(true);
    setContextConsentOpen(false);
    setPendingClinicalPrompt(null);
    if (prompt) void send(prompt, true);
  }

  function handleProviderSave(config: AiProviderConfig) {
    if (!user) return;
    try {
      saveAiProviderConfig(user.uid, config);
      setProviderConfig(config);
      setProviderDialogOpen(false);
      setNotice(`Conectado a ${aiProviderLabel(config)}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Não foi possível salvar a chave nesta sessão.');
    }
  }

  function handleProviderRemove() {
    if (!user) return;
    clearAiProviderConfig(user.uid);
    setProviderConfig(null);
    setNotice('Chave removida desta sessão.');
  }

  if (loading) return <LoadingState label="Carregando o assistente..." />;

  function renderComposer() {
    return (
      <div className="w-full max-w-[720px]">
        <div className="grid min-h-[112px] grid-rows-[minmax(48px,auto)_44px] overflow-visible rounded-[22px] border border-heal-line/80 bg-white px-2 pb-2 shadow-[0_8px_28px_rgba(15,23,42,0.07)] transition-[border-color,box-shadow] focus-within:border-heal-blue/45 focus-within:shadow-[0_8px_28px_rgba(15,23,42,0.07),0_0_0_4px_rgba(65,182,230,0.10)] dark:border-zinc-800 dark:bg-[#171719] dark:focus-within:border-heal-blue/50">
          <textarea
            aria-label="Mensagem para o assistente"
            className="m-0 block max-h-[184px] min-h-[48px] w-full resize-none self-stretch border-0 bg-transparent px-3 pb-1 pt-4 text-sm leading-relaxed text-heal-ink !outline-none !ring-0 placeholder:text-heal-muted focus:!border-transparent focus:!outline-none focus:!ring-0 focus-visible:!outline-none focus-visible:!ring-0 dark:text-white dark:placeholder:text-zinc-600"
            data-enable-grammarly="false"
            data-gramm="false"
            data-gramm_editor="false"
            disabled={thinking}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.nativeEvent.isComposing) return;
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
            placeholder={providerConfig ? 'Envie uma mensagem…' : 'Conecte uma IA para começar…'}
            ref={inputRef}
            rows={1}
            spellCheck={false}
            value={input}
          />

          <div className="flex min-w-0 items-end justify-between gap-2">
            <div className="flex min-w-0 items-center gap-1 overflow-hidden">
              <button
                aria-pressed={clinicalContextEnabled}
                className={`inline-flex h-8 min-w-0 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-bold transition-colors ${
                  clinicalContextEnabled
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/35 dark:text-emerald-300'
                    : 'text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white'
                }`}
                onClick={() => requestClinicalContext()}
                type="button"
              >
                {clinicalContextEnabled
                  ? <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
                  : <Database className="h-3.5 w-3.5 shrink-0" />}
                <span className="truncate">{clinicalContextEnabled ? 'Contexto clínico' : 'Sem dados clínicos'}</span>
              </button>

              <button
                aria-label="Configurar provedor de IA"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                onClick={() => setProviderDialogOpen(true)}
                type="button"
              >
                <KeyRound className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="flex shrink-0 items-center gap-1">
              {providerConfig?.provider === 'google' ? (
                <div className="relative" ref={thinkingMenuRef}>
                  <button
                    aria-expanded={isThinkingMenuOpen}
                    aria-haspopup="menu"
                    aria-label="Nível de raciocínio"
                    className="inline-flex h-9 items-center gap-1.5 rounded-full border border-heal-blue/20 bg-heal-softBlue/50 pl-3 pr-2.5 text-[11px] font-bold text-heal-ink shadow-sm outline-none transition hover:border-heal-blue/40 hover:bg-heal-softBlue focus-visible:ring-2 focus-visible:ring-heal-blue/35 dark:border-blue-400/20 dark:bg-blue-950/20 dark:text-zinc-100 dark:hover:bg-blue-950/35"
                    onClick={() => setIsThinkingMenuOpen(open => !open)}
                    type="button"
                  >
                    <span>{thinkingLevel === 'high' ? 'Profundo' : 'Rápido'}</span>
                    <ChevronDown
                      className={`h-3.5 w-3.5 text-heal-blue transition-transform ${isThinkingMenuOpen ? 'rotate-180' : ''}`}
                    />
                  </button>

                  {isThinkingMenuOpen ? (
                    <div className="absolute bottom-[calc(100%+10px)] right-0 z-30 w-[224px] rounded-[18px] border border-heal-line/80 bg-white p-2 shadow-[0_18px_48px_rgba(15,23,42,0.18)] after:absolute after:-bottom-1.5 after:right-6 after:h-3 after:w-3 after:rotate-45 after:border-b after:border-r after:border-heal-line/80 after:bg-white dark:border-zinc-800 dark:bg-[#1b1b1f] dark:after:border-zinc-800 dark:after:bg-[#1b1b1f]">
                      <div className="px-2 pb-2 pt-1">
                        <p className="text-[11px] font-extrabold text-heal-ink dark:text-white">Modo de resposta</p>
                        <p className="mt-0.5 text-[10px] leading-4 text-heal-muted dark:text-zinc-400">
                          Escolha o nível de detalhamento.
                        </p>
                      </div>

                      <div aria-label="Modo de resposta" className="grid gap-1" role="menu">
                        {[
                          { value: 'minimal' as const, label: 'Rápido', hint: 'Mais ágil e direto' },
                          { value: 'high' as const, label: 'Profundo', hint: 'Mais completo e detalhado' }
                        ].map(option => {
                          const selected = thinkingLevel === option.value;
                          return (
                            <button
                              aria-checked={selected}
                              className={`grid w-full grid-cols-[1fr_22px] items-center gap-3 rounded-xl border px-3 py-2 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-heal-blue/30 ${
                                selected
                                  ? 'border-heal-blue/25 bg-heal-softBlue/75 text-heal-ink dark:border-blue-400/25 dark:bg-blue-950/35 dark:text-white'
                                  : 'border-transparent text-heal-ink hover:bg-heal-surfaceHover dark:text-zinc-200 dark:hover:bg-zinc-800'
                              }`}
                              key={option.value}
                              onClick={() => {
                                setThinkingLevel(option.value);
                                setIsThinkingMenuOpen(false);
                              }}
                              role="menuitemradio"
                              type="button"
                            >
                              <span className="min-w-0">
                                <span className="block text-[11px] font-extrabold leading-4">{option.label}</span>
                                <span className="block truncate text-[10px] leading-4 text-heal-muted dark:text-zinc-400">
                                  {option.hint}
                                </span>
                              </span>
                              <span
                                aria-hidden="true"
                                className={`grid h-5 w-5 place-items-center rounded-full border ${
                                  selected
                                    ? 'border-heal-blue bg-heal-blue text-white'
                                    : 'border-heal-line bg-white text-transparent dark:border-zinc-700 dark:bg-zinc-900'
                                }`}
                              >
                                <Check className="h-3 w-3" strokeWidth={3} />
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {thinking ? (
                <button
                  aria-label="Interromper resposta"
                  className="grid h-10 w-10 place-items-center rounded-full bg-zinc-800 text-white hover:bg-zinc-700"
                  onClick={cancelReply}
                  type="button"
                >
                  <StopCircle className="h-[18px] w-[18px]" />
                </button>
              ) : (
                <button
                  aria-label="Enviar mensagem"
                  className="grid h-10 w-10 place-items-center rounded-full bg-heal-blue text-white transition-colors hover:bg-heal-blueDark disabled:bg-heal-canvas disabled:text-heal-muted dark:disabled:bg-zinc-900 dark:disabled:text-zinc-700"
                  disabled={!input.trim() || !providerConfig}
                  onClick={() => void send()}
                  type="button"
                >
                  <SendHorizontal className="h-[18px] w-[18px]" />
                </button>
              )}
            </div>
          </div>
        </div>
        <p aria-live="polite" className="min-h-5 px-2 pt-2 text-center text-[11px] text-heal-muted dark:text-zinc-500">
          {notice ??
            (clinicalContextEnabled
              ? 'Os registros necessários serão enviados ao provedor nesta conversa.'
              : 'Nenhum registro clínico será enviado ao provedor.')}
        </p>
      </div>
    );
  }
  function renderHistoryDrawer() {
    const query = historySearch.trim().toLocaleLowerCase('pt-BR');
    const filtered = history.filter(session => {
      if (historyTab === 'saved' && !session.isSaved) return false;
      if (!query) return true;
      return (
        session.title.toLocaleLowerCase('pt-BR').includes(query) ||
        session.messages.some(message => message.content.toLocaleLowerCase('pt-BR').includes(query))
      );
    });

    return (
      <>
        {isHistoryOpen ? (
          <button
            aria-label="Fechar histórico"
            className="fixed inset-0 z-40 bg-black/45 backdrop-blur-sm"
            onClick={() => setIsHistoryOpen(false)}
            type="button"
          />
        ) : null}
        <aside
          aria-hidden={!isHistoryOpen}
          className={`fixed right-0 top-0 z-50 flex h-screen w-full max-w-[390px] flex-col border-l border-heal-line bg-white shadow-2xl transition-transform duration-200 dark:border-zinc-800 dark:bg-[#0d0d0f] ${
            isHistoryOpen ? 'translate-x-0' : 'translate-x-full'
          }`}
        >
          <div className="flex items-center justify-between border-b border-heal-line px-5 py-4 dark:border-zinc-800">
            <div className="flex items-center gap-2.5">
              <History className="h-4 w-4 text-heal-blue" />
              <h2 className="text-base font-black text-heal-ink dark:text-white">Histórico</h2>
            </div>
            <button
              aria-label="Fechar histórico"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={() => setIsHistoryOpen(false)}
              type="button"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex border-b border-heal-line px-3 dark:border-zinc-800">
            {(['chats', 'saved'] as const).map(tab => (
              <button
                className={`relative flex-1 py-3 text-xs font-bold ${
                  historyTab === tab ? 'text-heal-ink dark:text-white' : 'text-heal-muted'
                }`}
                key={tab}
                onClick={() => setHistoryTab(tab)}
                type="button"
              >
                {tab === 'chats' ? 'Conversas' : 'Salvos'}
                {historyTab === tab ? (
                  <span className="absolute bottom-0 left-1/4 h-0.5 w-1/2 rounded-full bg-heal-blue" />
                ) : null}
              </button>
            ))}
          </div>

          <div className="border-b border-heal-line p-4 dark:border-zinc-800">
            <label className="flex h-10 items-center rounded-xl border border-heal-line bg-heal-canvas px-3 focus-within:border-heal-blue dark:border-zinc-800 dark:bg-zinc-900">
              <Search className="mr-2 h-4 w-4 shrink-0 text-heal-muted" />
              <span className="sr-only">Pesquisar conversas</span>
              <input
                className="min-w-0 flex-1 border-0 bg-transparent text-xs text-heal-ink outline-none dark:text-white"
                onChange={event => setHistorySearch(event.target.value)}
                placeholder="Pesquisar conversas…"
                value={historySearch}
              />
              {historySearch ? (
                <button
                  aria-label="Limpar pesquisa"
                  className="text-heal-muted hover:text-heal-ink dark:hover:text-white"
                  onClick={() => setHistorySearch('')}
                  type="button"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </label>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {filtered.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center text-center text-heal-muted">
                <History className="mb-2 h-7 w-7" />
                <p className="text-xs">
                  {historyTab === 'saved' ? 'Nenhuma conversa salva.' : 'Nenhuma conversa encontrada.'}
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {filtered.map(session => (
                  <div
                    className={`group flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left ${
                      activeChatId === session.id
                        ? 'border-heal-blue/25 bg-heal-softBlue text-heal-ink dark:bg-blue-950/25 dark:text-white'
                        : 'border-transparent text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-900 dark:hover:text-white'
                    }`}
                    key={session.id}
                  >
                    <button
                      className="min-w-0 flex-1 truncate text-left text-xs font-semibold"
                      onClick={() => handleSelectSession(session)}
                      type="button"
                    >
                      {session.title}
                    </button>
                    <span className="flex items-center gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100">
                      <button
                        aria-label={session.isSaved ? 'Remover dos salvos' : 'Salvar conversa'}
                        className={`rounded-md p-1 hover:bg-white/70 dark:hover:bg-zinc-800 ${
                          session.isSaved ? 'text-heal-blue' : ''
                        }`}
                        onClick={event => toggleBookmark(session.id, event)}
                        type="button"
                      >
                        <Bookmark className="h-3.5 w-3.5" fill={session.isSaved ? 'currentColor' : 'none'} />
                      </button>
                      <button
                        aria-label="Excluir conversa"
                        className="rounded-md p-1 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
                        onClick={event => deleteSession(session.id, event)}
                        type="button"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-heal-canvas text-heal-ink antialiased dark:bg-[#080809] dark:text-white">
      {!isFullscreen ? <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} /> : null}

      <div
        className={`relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden ${
          !isFullscreen ? 'border-l border-heal-line lg:pl-[280px] dark:border-zinc-900' : ''
        }`}
      >
        {!isFullscreen ? (
          <div className="shrink-0 lg:hidden">
            <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
          </div>
        ) : null}

        <header className="z-20 flex h-12 shrink-0 items-center justify-between border-b border-heal-line bg-white/95 px-3 backdrop-blur-md dark:border-zinc-900 dark:bg-[#0d0d0f]/95">
          <div className="flex min-w-0 items-center gap-1">
            <button
              aria-label={isFullscreen ? 'Mostrar navegação' : 'Ocultar navegação'}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={() => setIsFullscreen(current => !current)}
              type="button"
            >
              {isFullscreen ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </button>
            <button
              aria-label="Abrir histórico"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={() => setIsHistoryOpen(true)}
              type="button"
            >
              <History className="h-4 w-4" />
            </button>
            <button
              aria-label={`Selecionar IA: ${activeModelLabel}`}
              className="flex h-9 min-w-0 max-w-[320px] items-center gap-2 rounded-lg px-2.5 text-left text-sm font-bold text-heal-ink hover:bg-heal-surfaceHover dark:text-white dark:hover:bg-zinc-800"
              onClick={() => setProviderDialogOpen(true)}
              type="button"
            >
              <AiProviderMark provider={activeProvider.id} size="sm" />
              <span className="truncate">{activeModelLabel}</span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-heal-muted" />
            </button>
          </div>

          <button
            aria-label="Nova conversa"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
            onClick={handleNewChat}
            type="button"
          >
            <Plus className="h-4 w-4" />
          </button>
        </header>
        {messages.length === 0 ? (
          <main className="flex min-h-0 flex-1 overflow-y-auto px-4">
            <div className="m-auto flex w-full max-w-[720px] flex-col items-center pb-[clamp(64px,12vh,124px)] pt-10">
              <div className="flex items-center gap-3 text-2xl font-extrabold tracking-tight text-heal-blue">
                <AiProviderMark provider={activeProvider.id} size="lg" />
                <span>Redisus IA</span>
              </div>
              <p className="mt-2 text-center text-sm text-heal-muted dark:text-zinc-400">
                {providerConfig ? activeModelLabel : 'Escolha uma IA e conecte sua própria chave'}
              </p>
              <button
                className="mt-3 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                onClick={() => setProviderDialogOpen(true)}
                type="button"
              >
                <span className="flex -space-x-1">
                  {AI_PROVIDERS.filter(provider => provider.id !== 'custom').map(provider => (
                    <AiProviderMark className="ring-2 ring-heal-canvas dark:ring-[#080809]" key={provider.id} provider={provider.id} size="sm" />
                  ))}
                </span>
                Gemma, OpenAI, Groq e OpenRouter
              </button>
              <div className="mt-6 w-full">{renderComposer()}</div>
            </div>
          </main>
        ) : (
          <>
            <main className="min-h-0 flex-1 overflow-y-auto px-4 py-7 sm:px-6">
              <div className="mx-auto flex w-full max-w-[820px] flex-col gap-4 pb-8">
                {messages.map(message =>
                  message.role === 'assistant' ? (
                    <article
                      className={`group grid w-full gap-1 py-2 text-sm leading-[1.6] ${
                        message.error ? 'text-red-700 dark:text-red-200' : 'text-heal-ink dark:text-white'
                      }`}
                      key={message.id}
                    >
                      <div className="min-w-0">
                        <MarkdownRenderer text={message.content} />
                      </div>
                      <div className="flex min-h-7 items-center gap-2 text-heal-muted dark:text-zinc-600">
                        {message.model ? (
                          <span className="inline-flex min-w-0 items-center gap-1.5 text-[10px] font-semibold">
                            <AiProviderMark provider={message.provider ?? activeProvider.id} size="sm" />
                            <span className="max-w-[260px] truncate">{message.model}</span>
                          </span>
                        ) : null}
                        <span className="flex items-center gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                          <button
                            aria-label="Copiar resposta"
                            className="grid h-7 w-7 place-items-center rounded-full hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                            onClick={() => void navigator.clipboard.writeText(message.content)}
                            type="button"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                          {!message.error ? (
                            <button
                              aria-label="Gerar nova resposta"
                              className="grid h-7 w-7 place-items-center rounded-full hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                              onClick={() => regenerate(message.id)}
                              type="button"
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                            </button>
                          ) : null}
                        </span>
                      </div>
                    </article>
                  ) : (
                    <article className="group flex max-w-[76%] flex-col items-end self-end" key={message.id}>
                      <div className="rounded-[15px] rounded-br-[4px] bg-white px-[13px] py-2.5 text-sm leading-[1.55] text-heal-ink shadow-sm ring-1 ring-heal-line/60 dark:bg-[#171719] dark:text-white dark:ring-zinc-800">
                        {message.content}
                      </div>
                      <div className="mt-1 flex min-h-7 items-center gap-1 text-heal-muted opacity-100 transition-opacity dark:text-zinc-600 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                        <button
                          aria-label="Copiar mensagem"
                          className="grid h-7 w-7 place-items-center rounded-full hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                          onClick={() => void navigator.clipboard.writeText(message.content)}
                          type="button"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                        <button
                          aria-label="Editar mensagem"
                          className="grid h-7 w-7 place-items-center rounded-full hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                          onClick={() => {
                            setInput(message.content);
                            inputRef.current?.focus();
                          }}
                          type="button"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </article>
                  )
                )}

                {thinking ? (
                  <div className="flex items-center gap-2 py-3 text-xs font-semibold text-heal-muted dark:text-zinc-500">
                    <Loader2 className="h-4 w-4 animate-spin text-heal-blue" />
                    {thinkingLevel === 'high' ? 'Analisando com mais profundidade…' : 'Preparando resposta…'}
                  </div>
                ) : null}
                <div ref={chatEndRef} />
              </div>
            </main>

            <footer className="shrink-0 bg-heal-canvas/95 px-4 pb-3 pt-2 backdrop-blur-md dark:bg-[#080809]/95">
              <div className="mx-auto flex w-full max-w-[720px] justify-center">
                {renderComposer()}
              </div>
            </footer>
          </>
        )}
        {renderHistoryDrawer()}
      </div>

      <AiProviderDialog
        config={providerConfig}
        onClose={() => setProviderDialogOpen(false)}
        onRemove={handleProviderRemove}
        onSave={handleProviderSave}
        open={providerDialogOpen}
      />

      <Modal
        onClose={() => {
          setContextConsentOpen(false);
          setPendingClinicalPrompt(null);
        }}
        open={contextConsentOpen}
        title="Compartilhar contexto clínico?"
        size="sm"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <div>
              <p className="text-sm font-bold text-heal-ink dark:text-white">
                Permissão válida somente para esta conversa
              </p>
              <p className="mt-1.5 text-sm leading-relaxed text-heal-muted dark:text-zinc-400">
                O Redisus enviará ao seu provedor os nomes e os dados clínicos necessários de
                pacientes, avaliações e agenda. Telefone, e-mail e data de nascimento não serão incluídos.
              </p>
            </div>
          </div>
          <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
            Confirme que o uso do provedor escolhido está de acordo com as regras de privacidade e
            proteção de dados da sua instituição.
          </p>
          <div className="flex justify-end gap-2 border-t border-heal-line pt-4 dark:border-zinc-800">
            <button
              className="rounded-xl px-4 py-2 text-sm font-bold text-heal-muted hover:bg-heal-surfaceHover dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={() => {
                setContextConsentOpen(false);
                setPendingClinicalPrompt(null);
              }}
              type="button"
            >
              Cancelar
            </button>
            <button
              className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700"
              onClick={confirmClinicalContext}
              type="button"
            >
              Permitir nesta conversa
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
