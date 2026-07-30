import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createEvaluation, updateEvaluation } from '../../features/evaluations/evaluationService';
import type { EvaluationFormValues } from '../../features/evaluations/evaluationSchema';
import type { ImageDraft } from '../../lib/types';

const supabaseMocks = vi.hoisted(() => {
  const insert = vi.fn((_payload: Record<string, unknown>) => Promise.resolve({ error: null }));
  const finalEq = vi.fn((_column: string, _value: string) => Promise.resolve({ error: null }));
  const firstEq = vi.fn((_column: string, _value: string) => ({ eq: finalEq }));
  const update = vi.fn((_payload: Record<string, unknown>) => ({ eq: firstEq }));
  const upload = vi.fn();
  const getPublicUrl = vi.fn(() => ({
    data: { publicUrl: 'https://example.invalid/synthetic.jpg' }
  }));

  return {
    insert,
    finalEq,
    firstEq,
    update,
    upload,
    getPublicUrl,
    from: vi.fn(() => ({ insert, update })),
    storageFrom: vi.fn(() => ({ upload, getPublicUrl }))
  };
});

vi.mock('../../lib/supabase', () => ({
  supabase: {
    from: supabaseMocks.from,
    storage: {
      from: supabaseMocks.storageFrom
    }
  }
}));

const evaluationValues: EvaluationFormValues = {
  patientId: 'patient-1',
  patientName: 'Paciente Teste',
  date: '2026-04-28',
  woundLocation: 'Perna',
  woundEtiology: 'Venosa',
  painLevel: 2,
  exudateAmount: 'Pouco',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regular',
  periwoundSkin: 'Integra',
  infectionSigns: [],
  timers: {
    tissue: '',
    infection: '',
    moisture: '',
    edge: '',
    repair: '',
    social: ''
  },
  comorbidities: [],
  medications: [],
  notes: ''
};

describe('evaluationService', () => {
  beforeEach(() => {
    supabaseMocks.insert.mockReset().mockResolvedValue({ error: null });
    supabaseMocks.update.mockClear();
    supabaseMocks.firstEq.mockClear();
    supabaseMocks.finalEq.mockReset().mockResolvedValue({ error: null });
    supabaseMocks.upload.mockReset().mockResolvedValue({ error: null });
    supabaseMocks.getPublicUrl.mockClear();
  });

  it('salva a avaliação mesmo quando o upload da imagem falha', async () => {
    supabaseMocks.upload.mockResolvedValue({
      error: { message: 'Firebase Storage não está disponível' }
    });

    const images: ImageDraft[] = [
      {
        id: 'image-1',
        file: new File(['image'], 'ferida.jpeg', { type: 'image/jpeg' }),
        previewURL: 'blob:test',
        fileName: 'ferida.jpeg',
        contentType: 'image/jpeg',
        size: 5,
        rois: []
      }
    ];

    const result = await createEvaluation('user-1', evaluationValues, images);

    expect(result.imageUploadError).toMatch(/Firebase Storage não está disponível/i);
    expect(supabaseMocks.insert).toHaveBeenCalledWith(
      expect.objectContaining({
        patient_id: 'patient-1',
        user_id: 'user-1',
        images: []
      })
    );
  });

  it('atualiza a avaliação no escopo do usuário sem replicar snapshot clínico', async () => {
    await updateEvaluation('user-1', evaluationValues, 'evaluation-9', [], {
      updatedBy: 'user-1',
      previousData: { id: 'evaluation-9', painLevel: 2 }
    });

    expect(supabaseMocks.update).toHaveBeenCalledWith(
      expect.objectContaining({
        patient_name: 'Paciente Teste',
        pain_level: 2
      })
    );
    expect(supabaseMocks.firstEq).toHaveBeenCalledWith('id', 'evaluation-9');
    expect(supabaseMocks.finalEq).toHaveBeenCalledWith('user_id', 'user-1');
    expect(supabaseMocks.update.mock.calls[0][0]).not.toHaveProperty('previousData');
    expect(supabaseMocks.update.mock.calls[0][0]).not.toHaveProperty('auditLog');
  });
});
