import { useState } from 'react';
import { FileText, X, Image as ImageIcon, Eye, Loader2 } from 'lucide-react';
import type { ChatAttachment } from '../../types';

interface AttachmentPreviewProps {
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
}

export function AttachmentPreview({ attachments, onRemoveAttachment }: AttachmentPreviewProps) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  if (attachments.length === 0) return null;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 pb-2">
        {attachments.map((item) => (
          <div
            key={item.id}
            className="group relative flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 shadow-sm dark:border-slate-800 dark:bg-slate-900 animate-in fade-in zoom-in-95"
          >
            {item.type === 'image' && item.previewUrl ? (
              <div
                onClick={() => setSelectedImage(item.previewUrl!)}
                className="relative h-7 w-7 cursor-pointer overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700"
              >
                <img src={item.previewUrl} alt={item.name} className="h-full w-full object-cover" />
                <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity group-hover:opacity-100">
                  <Eye size={12} className="text-white" />
                </div>
              </div>
            ) : item.type === 'image' ? (
              <ImageIcon size={16} className="text-blue-500 shrink-0" />
            ) : (
              <FileText size={16} className="text-emerald-500 shrink-0" />
            )}

            <div className="flex flex-col min-w-0 max-w-[130px]">
              <span className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">
                {item.name}
              </span>
              {item.status === 'uploading' ? (
                <span className="flex items-center gap-1 text-[10px] text-blue-600">
                  <Loader2 size={10} className="animate-spin" /> {item.progress ?? 0}%
                </span>
              ) : item.size ? (
                <span className="text-[10px] text-slate-400">
                  {(item.size / 1024 / 1024).toFixed(1)} MB
                </span>
              ) : null}
            </div>

            <button
              type="button"
              onClick={() => onRemoveAttachment(item.id)}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              title="Remover anexo"
              aria-label="Remover anexo"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>

      {/* Expanded Image Viewer Modal */}
      {selectedImage && (
        <div
          onClick={() => setSelectedImage(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
        >
          <div className="relative max-h-[90vh] max-w-[90vw] overflow-hidden rounded-2xl bg-black shadow-2xl">
            <button
              type="button"
              onClick={() => setSelectedImage(null)}
              className="absolute top-3 right-3 rounded-full bg-black/60 p-2 text-white hover:bg-black"
              aria-label="Fechar pré-visualização"
            >
              <X size={18} />
            </button>
            <img src={selectedImage} alt="Visualização ampliada" className="max-h-[85vh] max-w-[85vw] object-contain" />
          </div>
        </div>
      )}
    </>
  );
}
