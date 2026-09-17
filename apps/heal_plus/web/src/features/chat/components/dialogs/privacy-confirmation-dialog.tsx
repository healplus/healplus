import { ShieldAlert } from 'lucide-react';
import { Modal } from '../../../../components/ui/Modal';
import type { PatientContext } from '../../types';

interface PrivacyConfirmationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  targetPatient: PatientContext | null;
  onConfirm: () => void;
}

export function PrivacyConfirmationDialog({
  isOpen,
  onClose,
  targetPatient,
  onConfirm
}: PrivacyConfirmationDialogProps) {
  if (!isOpen || !targetPatient) return null;

  return (
    <Modal open={isOpen} onClose={onClose} title="Confirmar Troca de Paciente">
      <div className="space-y-4 pt-1">
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-3.5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/60 dark:text-amber-200">
          <ShieldAlert size={20} className="shrink-0 text-amber-600 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-bold">Aviso de Segurança de Dados Clínicos</p>
            <p>
              Você está alterando o contexto do paciente ativo para <strong>{targetPatient.displayName}</strong>.
            </p>
            <p className="text-slate-600 dark:text-slate-300">
              Para evitar misturar dados de prontuários diferentes, os anexos atuais serão limpos e o novo contexto será isolado.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 shadow-md"
          >
            Confirmar Troca
          </button>
        </div>
      </div>
    </Modal>
  );
}
