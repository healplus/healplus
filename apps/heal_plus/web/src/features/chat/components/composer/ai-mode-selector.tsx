import { useState, useRef, useEffect } from 'react';
import { Bot, Stethoscope, ArrowLeftRight, FileText, Search, Globe, ChevronDown, Check } from 'lucide-react';
import type { AIMode } from '../../types';

interface AIModeOption {
  id: AIMode;
  label: string;
  description: string;
  icon: typeof Bot;
}

const AI_MODES: AIModeOption[] = [
  {
    id: 'assistant',
    label: 'Assistente',
    description: 'Apoio operacional e perguntas gerais',
    icon: Bot
  },
  {
    id: 'clinical-analysis',
    label: 'Análise clínica',
    description: 'Análise aprofundada da lesão e tecidos',
    icon: Stethoscope
  },
  {
    id: 'evolution-comparison',
    label: 'Comparar evolução',
    description: 'Comparativo de consultas e imagens',
    icon: ArrowLeftRight
  },
  {
    id: 'report-draft',
    label: 'Criar relatório',
    description: 'Rascunho estruturado do histórico',
    icon: FileText
  },
  {
    id: 'medical-record-search',
    label: 'Buscar no prontuário',
    description: 'Localizar dados no Heal+',
    icon: Search
  },
  {
    id: 'external-search',
    label: 'Pesquisa externa',
    description: 'Consultar fontes médicas públicas',
    icon: Globe
  }
];

interface AIModeSelectorProps {
  currentMode: AIMode;
  onSelectMode: (mode: AIMode) => void;
}

export function AIModeSelector({ currentMode, onSelectMode }: AIModeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedOption = AI_MODES.find((m) => m.id === currentMode) || AI_MODES[0];
  const SelectedIcon = selectedOption.icon;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200/90 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 transition-all hover:bg-slate-100 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        title={selectedOption.description}
      >
        <SelectedIcon size={14} className="text-blue-600 dark:text-blue-400" />
        <span>{selectedOption.label}</span>
        <ChevronDown size={13} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-64 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl ring-1 ring-black/5 dark:border-slate-800 dark:bg-slate-900 z-50 animate-in fade-in slide-in-from-bottom-2">
          <div className="px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Modo da IA
          </div>
          <div className="mt-1 space-y-0.5">
            {AI_MODES.map((option) => {
              const Icon = option.icon;
              const isSelected = option.id === currentMode;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => {
                    onSelectMode(option.id);
                    setIsOpen(false);
                  }}
                  className={`flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors ${
                    isSelected
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 font-semibold'
                      : 'text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <Icon size={16} className={`mt-0.5 shrink-0 ${isSelected ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold leading-none flex items-center justify-between">
                      {option.label}
                      {isSelected && <Check size={13} className="text-blue-600 dark:text-blue-400" />}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-1 font-normal">
                      {option.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
