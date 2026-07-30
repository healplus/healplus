// @vitest-environment node

import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment
} from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, Timestamp } from 'firebase/firestore';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

let testEnv: RulesTestEnvironment;

const projectId = `healplus-rules-${Date.now()}`;
const now = Timestamp.now();

const userDoc = {
  displayName: 'Dra Alice',
  email: 'alice@heal.plus',
  photoURL: null,
  role: 'professional',
  createdAt: now,
  updatedAt: now,
  settings: {
    theme: 'light',
    notificationsEnabled: true,
    emailNotificationsEnabled: true,
    agendaRemindersEnabled: true,
    hideEmailPreview: false,
    showProfilePhoto: true
  }
};

const patientDoc = {
  name: 'Tania Silva',
  phone: '11999999999',
  email: '',
  birthDate: '1985-05-12',
  notes: '',
  archived: false,
  createdAt: now,
  updatedAt: now
};

const evaluationDoc = {
  patientId: 'p1',
  patientName: 'Tania Silva',
  date: '2026-04-28',
  woundLocation: 'Regiao Sacral',
  woundEtiology: 'Lesao por Pressao',
  painLevel: 4,
  exudateAmount: 'Pequeno',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regulares',
  periwoundSkin: 'Integra',
  infectionSigns: [],
  timers: { tissue: '', infection: '', moisture: '', edge: '', repair: '', social: '' },
  comorbidities: [],
  medications: [],
  notes: '',
  images: [],
  createdAt: now,
  updatedAt: now
};

const linkedAnalysisDoc = {
  id: 'analysis-b',
  patientId: 'patient-b',
  assessmentId: 'evaluation-b',
  createdAt: '2026-01-01T00:00:00Z',
  mode: 'assessment_context',
  analysisVersion: 'synthetic-v1',
  roiVersion: 'synthetic-v1',
  roisUsed: [],
  imageQuality: {},
  visualFindings: {},
  clinicalContext: {},
  evolution: {},
  aiInference: {},
  alerts: [],
  recommendations: [],
  consideredData: [],
  disclaimer: 'Synthetic fixture; professional review required.'
};

const standaloneAnalysisDoc = {
  id: 'standalone-b',
  createdAt: '2026-01-01T00:00:00Z',
  mode: 'standalone',
  analysisVersion: 'synthetic-v1',
  roiVersion: 'synthetic-v1',
  roisUsed: [],
  imageQuality: {},
  visualFindings: {},
  clinicalContext: {},
  evolution: {},
  aiInference: {},
  alerts: [],
  recommendations: [],
  consideredData: [],
  disclaimer: 'Synthetic fixture; professional review required.'
};

const crossUserDocuments = [
  {
    resource: 'patient',
    existingPath: 'users/bob/patients/patient-b',
    missingPath: 'users/bob/patients/missing-patient',
    ownPath: 'users/alice/patients/patient-b',
    payload: patientDoc
  },
  {
    resource: 'wound evaluation',
    existingPath: 'users/bob/patients/patient-b/evaluations/evaluation-b',
    missingPath: 'users/bob/patients/patient-b/evaluations/missing-evaluation',
    ownPath: 'users/alice/patients/patient-b/evaluations/evaluation-b',
    payload: { ...evaluationDoc, patientId: 'patient-b' }
  },
  {
    resource: 'evaluation analysis job/result',
    existingPath: 'users/bob/patients/patient-b/evaluations/evaluation-b/analysisResults/analysis-b',
    missingPath: 'users/bob/patients/patient-b/evaluations/evaluation-b/analysisResults/missing-analysis',
    ownPath: 'users/alice/patients/patient-b/evaluations/evaluation-b/analysisResults/analysis-b',
    payload: linkedAnalysisDoc
  },
  {
    resource: 'standalone analysis job/result',
    existingPath: 'users/bob/analysisResults/standalone-b',
    missingPath: 'users/bob/analysisResults/missing-standalone',
    ownPath: 'users/alice/analysisResults/standalone-b',
    payload: standaloneAnalysisDoc
  }
];

async function rejectedCode(operation: Promise<unknown>) {
  try {
    await operation;
  } catch (error) {
    return (error as { code?: string }).code;
  }
  throw new Error('Expected Firebase operation to be denied');
}

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId,
    firestore: {
      rules: readFileSync('firestore.rules', 'utf8')
    }
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
  await testEnv.withSecurityRulesDisabled(async context => {
    const firestore = context.firestore();
    await Promise.all(
      crossUserDocuments.map(item =>
        setDoc(doc(firestore, item.existingPath), item.payload)
      )
    );
  });
});

describe('Firestore security rules', () => {
  it('usuario autenticado cria seu perfil e paciente', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice'), userDoc));
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1'), patientDoc));
  });

  it('usuario autenticado le seus pacientes', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice'), userDoc));
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1'), patientDoc));
    await assertSucceeds(getDoc(doc(alice, 'users/alice/patients/p1')));
  });

  it('usuario nao autenticado nao acessa nada', async () => {
    const guest = testEnv.unauthenticatedContext().firestore();
    await assertFails(getDoc(doc(guest, 'users/alice/patients/p1')));
  });

  it('usuario A nao acessa dados do usuario B', async () => {
    const bob = testEnv.authenticatedContext('bob').firestore();
    await assertFails(getDoc(doc(bob, 'users/alice/patients/p1')));
  });

  it.each(crossUserDocuments)(
    'nega leitura de $resource sem distinguir ID existente de inexistente',
    async ({ existingPath, missingPath }) => {
      const alice = testEnv.authenticatedContext('alice').firestore();
      const existingCode = await rejectedCode(getDoc(doc(alice, existingPath)));
      const missingCode = await rejectedCode(getDoc(doc(alice, missingPath)));

      expect(existingCode).toBe('permission-denied');
      expect(missingCode).toBe(existingCode);
    }
  );

  it.each(crossUserDocuments)(
    'nega escrita de $resource sem distinguir ID existente de inexistente',
    async ({ existingPath, missingPath, payload }) => {
      const alice = testEnv.authenticatedContext('alice').firestore();
      const existingCode = await rejectedCode(setDoc(doc(alice, existingPath), payload));
      const missingCode = await rejectedCode(setDoc(doc(alice, missingPath), payload));

      expect(existingCode).toBe('permission-denied');
      expect(missingCode).toBe(existingCode);
    }
  );

  it.each(crossUserDocuments)(
    'aceita o mesmo payload valido de $resource no namespace proprio',
    async ({ ownPath, payload }) => {
      const alice = testEnv.authenticatedContext('alice').firestore();
      await assertSucceeds(setDoc(doc(alice, ownPath), payload));
    }
  );

  it('avaliacao precisa ficar dentro do paciente correto', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1/evaluations/e1'), evaluationDoc));
    await assertFails(setDoc(doc(alice, 'users/alice/patients/p2/evaluations/e1'), evaluationDoc));
  });

  it('bloqueia documentos com estrutura invalida', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertFails(setDoc(doc(alice, 'users/alice/patients/bad'), { name: 'X' }));
    await expect(true).toBe(true);
  });
});
