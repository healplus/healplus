import { useEffect, useRef, type KeyboardEvent } from 'react';

interface AutoResizeTextareaProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  disabled?: boolean;
  minRows?: number;
  maxRows?: number;
}

export function AutoResizeTextarea({
  value,
  onChange,
  onSubmit,
  placeholder,
  disabled = false,
  minRows = 1,
  maxRows = 6
}: AutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = 'auto';
    const lineHeight = 22;
    const minHeight = minRows * lineHeight;
    const maxHeight = maxRows * lineHeight;
    const computedHeight = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);

    el.style.height = `${computedHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }, [value, minRows, maxRows]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) {
        onSubmit();
      }
    }
  };

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      rows={minRows}
      className="w-full resize-none bg-transparent px-1 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white dark:placeholder:text-slate-500 leading-relaxed font-sans"
    />
  );
}
