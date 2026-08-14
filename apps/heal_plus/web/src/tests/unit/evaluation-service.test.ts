import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createEvaluation, updateEvaluation } from '../../features/evaluations/evaluationService';
import type { EvaluationFormValues } from '../../features/evaluations/evaluationSchema';
import type { ImageDraft } from '../../lib/types';

const supabaseMocks = vi.hoisted(() => {
  const insert = vi.fn((_payload: Record<string, unknown>) => Promise.resolve({ error: null }));
  const finalEq = vi.fn((_column: string, _value: string) => Promise.resolve({ error: null }));
  const firstEq = vi.fn((_column: string, _value: string) => ({ eq: finalEq }));
  const update = vi.fn((_payload: Record<string, unknown>) => ({ eq: firstEq }));
  const createSignedUrl = vi.fn().mockResolvedValue({
    data: { signedUrl: 'https://example.invalid/signed-synthetic.jpg' },
    error: null
  });
  const remove = vi.fn().mockResolvedValue({ error: null });

  return {
    insert,
    finalEq,
    firstEq,
    update,
    createSignedUrl,
    remove,
    from: vi.fn(() => ({ insert, update })),
    storageFrom: vi.fn(() => ({ createSignedUrl, remove }))
  };
});

const clinicalImageMocks = vi.hoisted(() => ({
  prepare: vi.fn(),
  upload: vi.fn()
}));

vi.mock('../../lib/supabase', () => ({
  supabase: {
    from: supabaseMocks.from,
    storage: {
      from: supabaseMocks.storageFrom
    }
  }
}));

vi.mock('../../lib/clinicalImagePreparation', () => ({
  prepareClinicalImage: clinicalImageMocks.prepare
}));

vi.mock('../../lib/clinicalImageUpload', () => ({
  uploadClinicalImage: clinicalImageMocks.upload
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

const privateImagePathPattern =
  /^user-1\/patient-1\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(?:webp|jpg)$/u;

describe('evaluationService', () => {
  beforeEach(() => {
    supabaseMocks.insert.mockReset().mockResolvedValue({ error: null });
    supabaseMocks.update.mockClear();
    supabaseMocks.firstEq.mockClear();
    supabaseMocks.finalEq.mockReset().mockResolvedValue({ error: null });
    supabaseMocks.createSignedUrl.mockClear();
    supabaseMocks.remove.mockReset().mockResolvedValue({ error: null });
    clinicalImageMocks.prepare.mockReset().mockImplementation(async (file: File) => (
      new File(['prepared'], 'clinical-image-synthetic.webp', { type: 'image/webp' })
    ));
    clinicalImageMocks.upload.mockReset().mockResolvedValue(undefined);
  });

  it('salva a avaliação mesmo quando o upload da imagem falha', async () => {
    clinicalImageMocks.upload.mockRejectedValue(new Error('Supabase Storage não está disponível'));

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

    expect(result.imageUploadError).toMatch(/Supabase Storage não está disponível/i);
    expect(supabaseMocks.insert).toHaveBeenCalledWith(
      expect.objectContaining({
        patient_id: 'patient-1',
        user_id: 'user-1',
        images: []
      })
    );
    expect(supabaseMocks.remove).toHaveBeenCalledWith([
      expect.stringMatching(privateImagePathPattern)
    ]);
  });

  it('persiste somente o caminho privado e resolve uma URL assinada temporária', async () => {
    const images: ImageDraft[] = [
      {
        id: 'image-1',
        file: new File(['image'], 'nome-do-paciente.jpeg', { type: 'image/jpeg' }),
        previewURL: 'blob:test',
        fileName: 'nome-do-paciente.jpeg',
        contentType: 'image/jpeg',
        size: 5,
        rois: []
      }
    ];

    await createEvaluation('user-1', evaluationValues, images);

    const persistedImages = (supabaseMocks.insert.mock.calls[0][0] as { images: Array<Record<string, unknown>> }).images;
    expect(persistedImages).toHaveLength(1);
    expect(persistedImages[0].storagePath).toMatch(privateImagePathPattern);
    expect(persistedImages[0].downloadURL).toBe('');
    expect(persistedImages[0].fileName).toBe('clinical-image-synthetic.webp');
  });

  it('remove objetos enviados quando o upload é cancelado', async () => {
    const controller = new AbortController();
    clinicalImageMocks.upload.mockRejectedValue(new DOMException('Envio cancelado.', 'AbortError'));
    const images: ImageDraft[] = [
      {
        id: 'image-1',
        file: new File(['image'], 'synthetic.jpeg', { type: 'image/jpeg' }),
        previewURL: 'blob:test',
        fileName: 'synthetic.jpeg',
        contentType: 'image/jpeg',
        size: 5,
        rois: []
      }
    ];

    await expect(createEvaluation('user-1', evaluationValues, images, {
      signal: controller.signal
    })).rejects.toMatchObject({ name: 'AbortError' });

    expect(supabaseMocks.remove).toHaveBeenCalledWith([
      expect.stringMatching(privateImagePathPattern)
    ]);
    expect(supabaseMocks.insert).not.toHaveBeenCalled();
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
