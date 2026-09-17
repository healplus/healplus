import { useState, useRef, useEffect, type ChangeEvent } from 'react';
import { Paperclip, Image as ImageIcon, FileText, UserPlus, FileCheck } from 'lucide-react';
import type { ChatAttachment, PatientContext } from '../../types';

interface AttachmentButtonProps {
  onAddAttachment: (attachment: ChatAttachment) => void;
  onOpenPatientSelector: () => void;
  disabled?: boolean;
}

export function AttachmentButton({ onAddAttachment, onOpenPatientSelector, disabled }: AttachmentButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      const isImage = file.type.startsWith('image/');
      const isPdf = file.type === 'application/pdf';

      const attachment: ChatAttachment = {
        id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        name: file.name,
        type: isImage ? 'image' : isPdf ? 'pdf' : 'report',
        status: 'ready',
        size: file.size,
        file,
        previewUrl: isImage ? URL.createObjectURL(file) : undefined
      };

      onAddAttachment(attachment);
    });

    if (fileInputRef.current) fileInputRef.current.value = '';
    setIsOpen(false);
  };

  return (
    <div className="relative inline-block" ref={popoverRef}>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept="image/*,.pdf,.doc,.docx,.txt"
        multiple
        className="hidden"
      />

      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 hover:text-blue-600 disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-400 transition-colors"
        title="Anexar imagem, documento ou paciente"
        aria-label="Anexar arquivos"
      >
        <Paperclip size={18} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-56 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-800 dark:bg-slate-900 z-50 animate-in fade-in slide-in-from-bottom-2">
          <div className="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Anexar Conteúdo
          </div>

          <div className="mt-1 space-y-0.5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-600 dark:text-slate-200 dark:hover:bg-slate-800/80"
            >
              <ImageIcon size={16} className="text-blue-500" />
              <span>Foto / Imagem da lesão</span>
            </button>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-600 dark:text-slate-200 dark:hover:bg-slate-800/80"
            >
              <FileText size={16} className="text-emerald-500" />
              <span>Documento PDF / Laudo</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onOpenPatientSelector();
                setIsOpen(false);
              }}
              className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-600 dark:text-slate-200 dark:hover:bg-slate-800/80"
            >
              <UserPlus size={16} className="text-purple-500" />
              <span>Vincular paciente ao chat</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
