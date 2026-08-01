import { useState } from 'react';
import { History, X, Search, Bookmark, Trash2 } from 'lucide-react';
import type { ChatSession } from '../types';

interface ChatHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onPinSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export function ChatHistoryDrawer({
  isOpen,
  onClose,
  sessions,
  currentSessionId,
  onSelectSession,
  onPinSession,
  onDeleteSession
}: ChatHistoryDrawerProps) {
  const [historyTab, setHistoryTab] = useState<'chats' | 'saved'>('chats');
  const [historySearch, setHistorySearch] = useState('');

  if (!isOpen) return null;

  const query = historySearch.trim().toLocaleLowerCase('pt-BR');
  const filtered = sessions.filter((session) => {
    if (historyTab === 'saved' && !session.isPinned) return false;
    if (!query) return true;
    return (
      session.title.toLocaleLowerCase('pt-BR').includes(query) ||
      session.messages.some((message) =>
        message.content.toLocaleLowerCase('pt-BR').includes(query)
      )
    );
  });

  return (
    <>
      <button
        aria-label="Fechar histórico"
        className="fixed inset-0 z-40 bg-black/45 backdrop-blur-sm"
        onClick={onClose}
        type="button"
      />
      <aside
        aria-hidden={!isOpen}
        className={`fixed right-0 top-0 z-50 flex h-screen w-full max-w-[390px] flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-200 dark:border-zinc-800 dark:bg-[#0d0d0f] ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-zinc-800">
          <div className="flex items-center gap-2.5">
            <History className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-base font-black text-slate-900 dark:text-white">Histórico</h2>
          </div>
          <button
            aria-label="Fechar histórico"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
            onClick={onClose}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex border-b border-slate-200 px-3 dark:border-zinc-800">
          {(['chats', 'saved'] as const).map((tab) => (
            <button
              className={`relative flex-1 py-3 text-xs font-bold ${
                historyTab === tab
                  ? 'text-slate-900 dark:text-white'
                  : 'text-slate-500 dark:text-zinc-400'
              }`}
              key={tab}
              onClick={() => setHistoryTab(tab)}
              type="button"
            >
              {tab === 'chats' ? 'Conversas' : 'Salvos'}
              {historyTab === tab ? (
                <span className="absolute bottom-0 left-1/4 h-0.5 w-1/2 rounded-full bg-blue-600" />
              ) : null}
            </button>
          ))}
        </div>

        <div className="border-b border-slate-200 p-4 dark:border-zinc-800">
          <label className="flex h-10 items-center rounded-xl border border-slate-200 bg-slate-50 px-3 focus-within:border-blue-600 dark:border-zinc-800 dark:bg-zinc-900">
            <Search className="mr-2 h-4 w-4 shrink-0 text-slate-400 dark:text-zinc-500" />
            <span className="sr-only">Pesquisar conversas</span>
            <input
              className="min-w-0 flex-1 border-0 bg-transparent text-xs text-slate-900 outline-none dark:text-white placeholder:text-slate-400"
              onChange={(event) => setHistorySearch(event.target.value)}
              placeholder="Pesquisar conversas…"
              value={historySearch}
            />
            {historySearch ? (
              <button
                aria-label="Limpar pesquisa"
                className="text-slate-400 hover:text-slate-900 dark:text-zinc-500 dark:hover:text-white"
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
            <div className="flex h-48 flex-col items-center justify-center text-center text-slate-400 dark:text-zinc-500">
              <History className="mb-2 h-7 w-7" />
              <p className="text-xs">
                {historyTab === 'saved' ? 'Nenhuma conversa salva.' : 'Nenhuma conversa encontrada.'}
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {filtered.map((session) => (
                <div
                  className={`group flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left ${
                    currentSessionId === session.id
                      ? 'border-blue-500/30 bg-blue-50 text-slate-900 dark:bg-blue-950/30 dark:text-white'
                      : 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white'
                  }`}
                  key={session.id}
                >
                  <button
                    className="min-w-0 flex-1 truncate text-left text-xs font-semibold"
                    onClick={() => {
                      onSelectSession(session.id);
                      onClose();
                    }}
                    type="button"
                  >
                    {session.title}
                  </button>
                  <span className="flex items-center gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100">
                    <button
                      aria-label={session.isPinned ? 'Remover dos salvos' : 'Salvar conversa'}
                      className={`rounded-md p-1 hover:bg-white/70 dark:hover:bg-zinc-800 ${
                        session.isPinned ? 'text-blue-600' : ''
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPinSession(session.id);
                      }}
                      type="button"
                    >
                      <Bookmark
                        className="h-3.5 w-3.5"
                        fill={session.isPinned ? 'currentColor' : 'none'}
                      />
                    </button>
                    <button
                      aria-label="Excluir conversa"
                      className="rounded-md p-1 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
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
