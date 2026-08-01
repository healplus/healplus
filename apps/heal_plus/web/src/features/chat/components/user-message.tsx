import { useState } from 'react';
import { Pencil, FileText, Image as ImageIcon, UserCheck } from 'lucide-react';
import type { ChatMessage } from '../types';

interface UserMessageProps {
  message: ChatMessage;
  onEditMessage?: (id: string, newText: string) => void;
}

export function UserMessage({ message, onEditMessage }: UserMessageProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(message.content);

  const handleSaveEdit = () => {
    if (editText.trim() && onEditMessage) {
      onEditMessage(message.id, editText.trim());
      setIsEditing(false);
    }
  };

  return (
    <div className="flex flex-col items-end my-4 animate-in fade-in slide-in-from-bottom-2">
      {/* Patient Context badge above user message if present */}
      {message.patientContext && (
        <div className="mb-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1">
          <UserCheck size={12} /> {message.patientContext.displayName}
        </div>
      )}

      <div className="group relative max-w-[85%] sm:max-w-[75%] rounded-3xl bg-blue-600 px-4 py-3 text-white shadow-md shadow-blue-600/15 dark:bg-blue-600">
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full rounded-xl bg-blue-700/80 p-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-white/40"
              rows={3}
            />
            <div className="flex justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="rounded-lg bg-blue-800 px-2.5 py-1 text-white hover:bg-blue-900"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                className="rounded-lg bg-white px-2.5 py-1 font-bold text-blue-700 hover:bg-blue-50"
              >
                Salvar
              </button>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap font-sans">{message.content}</p>

            {/* Attachments inside user message */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-2 border-t border-blue-500/60 pt-2">
                {message.attachments.map((att) => (
                  <div
                    key={att.id}
                    className="flex items-center gap-2 rounded-xl bg-blue-700/80 px-2.5 py-1 text-xs text-white"
                  >
                    {att.type === 'image' && att.previewUrl ? (
                      <img src={att.previewUrl} alt={att.name} className="h-6 w-6 rounded-md object-cover" />
                    ) : att.type === 'image' ? (
                      <ImageIcon size={14} />
                    ) : (
                      <FileText size={14} />
                    )}
                    <span className="truncate max-w-[120px] font-medium">{att.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Edit Action Button */}
        {!isEditing && onEditMessage && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="absolute -left-8 top-2 rounded-lg p-1 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            title="Editar mensagem"
            aria-label="Editar mensagem"
          >
            <Pencil size={14} />
          </button>
        )}
      </div>

      <span className="mt-1 text-[10px] text-slate-400">
        {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
      </span>
    </div>
  );
}
