import { useState, useMemo } from 'react';
import { Search, UserCheck } from 'lucide-react';
import type { PatientContext } from '../../types';
import type { Patient } from '../../../../lib/types';
import { Modal } from '../../../../components/ui/Modal';

interface PatientSelectorDialogProps {
  isOpen: boolean;
  onClose: () => void;
  patients: Patient[];
  currentPatientId?: string;
  onSelectPatient: (patient: PatientContext) => void;
}

export function PatientSelectorDialog({
  isOpen,
  onClose,
  patients,
  currentPatientId,
  onSelectPatient
}: PatientSelectorDialogProps) {
  const [search, setSearch] = useState('');

  const filteredPatients = useMemo(() => {
    if (!search.trim()) return patients;
    const q = search.toLowerCase();
    return patients.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.email && p.email.toLowerCase().includes(q)) ||
        (p.phone && p.phone.includes(q))
    );
  }, [patients, search]);

  if (!isOpen) return null;

  return (
    <Modal open={isOpen} onClose={onClose} title="Vincular Paciente ao Chat">
      <div className="space-y-4 pt-1">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Selecione um paciente cadastrado no Heal+ para direcionar as consultas de IA ao prontuário correto.
        </p>

        {/* Search Input */}
        <div className="relative flex items-center">
          <Search size={16} className="absolute left-3 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome, e-mail ou telefone..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
          />
        </div>

        {/* Patient List */}
        <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
          {filteredPatients.map((p) => {
            const isSelected = p.id === currentPatientId;
            const maskedId = p.phone ? `Tel ${p.phone}` : undefined;

            return (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  onSelectPatient({
                    id: p.id,
                    displayName: p.name,
                    maskedIdentifier: maskedId,
                    lastAppointmentAt: p.updatedAt
                  });
                  onClose();
                }}
                className={`flex w-full items-center justify-between gap-3 rounded-2xl border p-3 text-left transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50/80 text-blue-900 shadow-sm dark:border-blue-500 dark:bg-blue-950/80 dark:text-blue-200 font-semibold'
                    : 'border-slate-200 bg-white hover:border-blue-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/80'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white font-bold">
                    {p.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      {p.name}
                    </h4>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {p.email ? `${p.email} • ` : ''} {p.archived ? 'Arquivado' : 'Ativo'}
                    </p>
                  </div>
                </div>

                {isSelected ? (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white">
                    <UserCheck size={14} />
                  </span>
                ) : (
                  <span className="text-xs font-semibold text-blue-600 hover:underline">
                    Selecionar
                  </span>
                )}
              </button>
            );
          })}

          {filteredPatients.length === 0 && (
            <div className="py-8 text-center text-xs text-slate-500">
              Nenhum paciente encontrado para a busca.
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
