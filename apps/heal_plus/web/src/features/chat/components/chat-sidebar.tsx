import { useState, useMemo } from 'react';
import {
  Plus,
  Search,
  MessageSquare,
  Pin,
  Archive,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  User,
  Check,
  UserCheck
} from 'lucide-react';
import type { ChatSession } from '../types';
import { isToday, isYesterday, subDays, isAfter } from 'date-fns';

interface ChatSidebarProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onRenameSession: (id: string, newTitle: string) => void;
  onPinSession: (id: string) => void;
  onArchiveSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  userDisplayName?: string;
  userRole?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function ChatSidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onPinSession,
  onArchiveSession,
  onDeleteSession,
  userDisplayName = 'Profissional de Saúde',
  userRole = 'Enfermeiro(a) / Clínico(a)',
  isCollapsed = false,
  onToggleCollapse,
  isMobileOpen = false,
  onCloseMobile
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const filteredSessions = useMemo(() => {
    return sessions.filter((s) => {
      if (s.isArchived) return false;
      if (!searchQuery.trim()) return true;
      const query = searchQuery.toLowerCase();
      return (
        s.title.toLowerCase().includes(query) ||
        s.patientContext?.displayName.toLowerCase().includes(query)
      );
    });
  }, [sessions, searchQuery]);

  const groupedSessions = useMemo(() => {
    const pinned: ChatSession[] = [];
    const today: ChatSession[] = [];
    const yesterday: ChatSession[] = [];
    const last7Days: ChatSession[] = [];
    const older: ChatSession[] = [];

    const now = new Date();
    const sevenDaysAgo = subDays(now, 7);

    filteredSessions.forEach((s) => {
      if (s.isPinned) {
        pinned.push(s);
        return;
      }
      const date = new Date(s.createdAt);
      if (isToday(date)) {
        today.push(s);
      } else if (isYesterday(date)) {
        yesterday.push(s);
      } else if (isAfter(date, sevenDaysAgo)) {
        last7Days.push(s);
      } else {
        older.push(s);
      }
    });

    return { pinned, today, yesterday, last7Days, older };
  }, [filteredSessions]);

  const startRename = (s: ChatSession) => {
    setEditingId(s.id);
    setEditingTitle(s.title);
    setMenuOpenId(null);
  };

  const saveRename = (id: string) => {
    if (editingTitle.trim()) {
      onRenameSession(id, editingTitle.trim());
    }
    setEditingId(null);
  };

  const sidebarContent = (
    <div className="flex h-full flex-col bg-slate-900 text-slate-200">
      {/* Top Header: Logo & New Chat */}
      <div className="flex items-center justify-between p-4 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <img
            src="/images/Logo_final_modobranco.png"
            alt="Heal+"
            className="h-7 w-auto object-contain"
          />
          {!isCollapsed && (
            <span className="text-[10px] font-mono tracking-widest uppercase text-blue-400 font-bold border-l border-slate-700 pl-2">
              IA CLINICAL
            </span>
          )}
        </div>

        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden md:flex rounded-xl p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
            title={isCollapsed ? 'Expandir sidebar' : 'Recolher sidebar'}
            aria-label="Recolher sidebar"
          >
            {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        )}
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          type="button"
          onClick={onNewSession}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/25 transition-all hover:bg-blue-500 active:scale-98"
        >
          <Plus size={18} strokeWidth={2.5} />
          {!isCollapsed && <span>Nova conversa</span>}
        </button>
      </div>

      {!isCollapsed && (
        <>
          {/* Search Box */}
          <div className="px-3 pb-2">
            <div className="relative flex items-center">
              <Search size={14} className="absolute left-3 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar conversas..."
                className="w-full rounded-xl bg-slate-800/80 pl-9 pr-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
          </div>

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto px-2 py-1 space-y-4">
            {/* Pinned Group */}
            {groupedSessions.pinned.length > 0 && (
              <GroupSection
                title="Fixadas"
                sessions={groupedSessions.pinned}
                currentSessionId={currentSessionId}
                editingId={editingId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                saveRename={saveRename}
                menuOpenId={menuOpenId}
                setMenuOpenId={setMenuOpenId}
                onSelectSession={onSelectSession}
                startRename={startRename}
                onPinSession={onPinSession}
                onArchiveSession={onArchiveSession}
                onDeleteSession={onDeleteSession}
              />
            )}

            {/* Today Group */}
            {groupedSessions.today.length > 0 && (
              <GroupSection
                title="Hoje"
                sessions={groupedSessions.today}
                currentSessionId={currentSessionId}
                editingId={editingId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                saveRename={saveRename}
                menuOpenId={menuOpenId}
                setMenuOpenId={setMenuOpenId}
                onSelectSession={onSelectSession}
                startRename={startRename}
                onPinSession={onPinSession}
                onArchiveSession={onArchiveSession}
                onDeleteSession={onDeleteSession}
              />
            )}

            {/* Yesterday Group */}
            {groupedSessions.yesterday.length > 0 && (
              <GroupSection
                title="Ontem"
                sessions={groupedSessions.yesterday}
                currentSessionId={currentSessionId}
                editingId={editingId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                saveRename={saveRename}
                menuOpenId={menuOpenId}
                setMenuOpenId={setMenuOpenId}
                onSelectSession={onSelectSession}
                startRename={startRename}
                onPinSession={onPinSession}
                onArchiveSession={onArchiveSession}
                onDeleteSession={onDeleteSession}
              />
            )}

            {/* Last 7 Days Group */}
            {groupedSessions.last7Days.length > 0 && (
              <GroupSection
                title="Últimos 7 dias"
                sessions={groupedSessions.last7Days}
                currentSessionId={currentSessionId}
                editingId={editingId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                saveRename={saveRename}
                menuOpenId={menuOpenId}
                setMenuOpenId={setMenuOpenId}
                onSelectSession={onSelectSession}
                startRename={startRename}
                onPinSession={onPinSession}
                onArchiveSession={onArchiveSession}
                onDeleteSession={onDeleteSession}
              />
            )}

            {/* Older Group */}
            {groupedSessions.older.length > 0 && (
              <GroupSection
                title="Anteriores"
                sessions={groupedSessions.older}
                currentSessionId={currentSessionId}
                editingId={editingId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                saveRename={saveRename}
                menuOpenId={menuOpenId}
                setMenuOpenId={setMenuOpenId}
                onSelectSession={onSelectSession}
                startRename={startRename}
                onPinSession={onPinSession}
                onArchiveSession={onArchiveSession}
                onDeleteSession={onDeleteSession}
              />
            )}

            {filteredSessions.length === 0 && (
              <div className="p-4 text-center text-xs text-slate-500">
                Nenhuma conversa encontrada.
              </div>
            )}
          </div>
        </>
      )}

      {/* Professional Footer */}
      <div className="border-t border-slate-800 p-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white font-bold">
            {userDisplayName.slice(0, 2).toUpperCase()}
          </div>
          {!isCollapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-bold text-white">{userDisplayName}</p>
              <p className="truncate text-[10px] text-slate-400">{userRole}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col border-r border-slate-800 transition-all duration-300 ${
          isCollapsed ? 'w-16' : 'w-72'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <div className="relative w-80 max-w-[85vw] h-full shadow-2xl animate-in slide-in-from-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}

interface GroupSectionProps {
  title: string;
  sessions: ChatSession[];
  currentSessionId: string | null;
  editingId: string | null;
  editingTitle: string;
  setEditingTitle: (val: string) => void;
  saveRename: (id: string) => void;
  menuOpenId: string | null;
  setMenuOpenId: (id: string | null) => void;
  onSelectSession: (id: string) => void;
  startRename: (s: ChatSession) => void;
  onPinSession: (id: string) => void;
  onArchiveSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

function GroupSection({
  title,
  sessions,
  currentSessionId,
  editingId,
  editingTitle,
  setEditingTitle,
  saveRename,
  menuOpenId,
  setMenuOpenId,
  onSelectSession,
  startRename,
  onPinSession,
  onArchiveSession,
  onDeleteSession
}: GroupSectionProps) {
  return (
    <div>
      <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {title}
      </div>
      <div className="mt-1 space-y-0.5">
        {sessions.map((s) => {
          const isSelected = s.id === currentSessionId;
          const isEditing = s.id === editingId;
          const isMenuOpen = s.id === menuOpenId;

          return (
            <div key={s.id} className="relative group">
              {isEditing ? (
                <div className="flex items-center gap-1 px-2 py-1.5">
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && saveRename(s.id)}
                    autoFocus
                    className="w-full rounded-lg bg-slate-800 px-2 py-1 text-xs text-white focus:outline-none ring-1 ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => saveRename(s.id)}
                    className="p-1 text-emerald-400 hover:text-emerald-300"
                  >
                    <Check size={14} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onSelectSession(s.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left text-xs transition-colors ${
                    isSelected
                      ? 'bg-blue-600/20 text-white font-semibold border border-blue-500/30'
                      : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare size={14} className={isSelected ? 'text-blue-400' : 'text-slate-500'} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate">{s.title}</p>
                      {s.patientContext && (
                        <p className="text-[10px] text-blue-400 font-medium truncate flex items-center gap-1">
                          <UserCheck size={10} /> {s.patientContext.displayName}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpenId(isMenuOpen ? null : s.id);
                      }}
                      className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-700"
                    >
                      <MoreVertical size={13} />
                    </button>
                  </div>
                </button>
              )}

              {/* Context Menu */}
              {isMenuOpen && (
                <div className="absolute right-2 top-full mt-1 w-40 rounded-xl border border-slate-700 bg-slate-800 p-1 shadow-xl z-50 animate-in fade-in">
                  <button
                    type="button"
                    onClick={() => startRename(s)}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 hover:bg-slate-700"
                  >
                    <MessageSquare size={13} /> Renomear
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      onPinSession(s.id);
                      setMenuOpenId(null);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 hover:bg-slate-700"
                  >
                    <Pin size={13} /> {s.isPinned ? 'Desafixar' : 'Fixar'}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      onArchiveSession(s.id);
                      setMenuOpenId(null);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 hover:bg-slate-700"
                  >
                    <Archive size={13} /> Arquivar
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      onDeleteSession(s.id);
                      setMenuOpenId(null);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-950/60"
                  >
                    <Trash2 size={13} /> Excluir
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
