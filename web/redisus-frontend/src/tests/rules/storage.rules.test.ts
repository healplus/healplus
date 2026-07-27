// @vitest-environment node

import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment
} from '@firebase/rules-unit-testing';
import type firebase from 'firebase/compat/app';
import 'firebase/compat/storage';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

let testEnv: RulesTestEnvironment;
const bobImagePath = 'users/bob/patients/patient-b/evaluations/evaluation-b/wounds/image-b.png';
const missingBobImagePath = 'users/bob/patients/patient-b/evaluations/evaluation-b/wounds/missing-image.png';
const syntheticImage = new Uint8Array([1, 2, 3]);

function uploadTaskPromise(task: firebase.storage.UploadTask) {
  return new Promise((resolve, reject) => {
    task.on('state_changed', undefined, reject, () => resolve(task.snapshot));
  });
}

async function rejectedCode(operation: Promise<unknown>) {
  try {
    await operation;
  } catch (error) {
    return (error as { code?: string }).code;
  }
  throw new Error('Expected Firebase Storage operation to be denied');
}

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'demo-healplus',
    storage: {
      rules: readFileSync('storage.rules', 'utf8'),
      host: '127.0.0.1',
      port: 9199
    }
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearStorage();
  const bob = testEnv.authenticatedContext('bob').storage(`gs://${testEnv.projectId}.appspot.com`);
  await assertSucceeds(
    uploadTaskPromise(bob.ref(bobImagePath).put(syntheticImage, { contentType: 'image/png' }))
  );
});

describe('Storage security rules', () => {
  it('permite imagem no path do proprio usuario', async () => {
    const storage = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    await assertSucceeds(
      uploadTaskPromise(
        storage
          .ref('users/alice/patients/p1/evaluations/e1/wounds/img.png')
          .put(syntheticImage, { contentType: 'image/png' })
      )
    );
  });

  it('bloqueia upload no path de outro usuario', async () => {
    const storage = testEnv.authenticatedContext('bob').storage(`gs://${testEnv.projectId}.appspot.com`);
    await assertFails(
      uploadTaskPromise(
        storage
          .ref('users/alice/patients/p1/evaluations/e1/wounds/img.png')
          .put(syntheticImage, { contentType: 'image/png' })
      )
    );
  });

  it('bloqueia arquivo que nao e imagem', async () => {
    const storage = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const text = new Uint8Array([1, 2, 3]);
    await assertFails(uploadTaskPromise(storage.ref('users/alice/patients/p1/evaluations/e1/wounds/img.txt').put(text, { contentType: 'text/plain' })));
  });

  it('nega leitura cross-user sem distinguir imagem existente de inexistente', async () => {
    const alice = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const existingCode = await rejectedCode(alice.ref(bobImagePath).getDownloadURL());
    const missingCode = await rejectedCode(alice.ref(missingBobImagePath).getDownloadURL());

    expect(existingCode).toBe('storage/unauthorized');
    expect(missingCode).toBe(existingCode);
  });

  it('nega escrita cross-user sem distinguir imagem existente de inexistente', async () => {
    const alice = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const metadata = { contentType: 'image/png' };
    const existingCode = await rejectedCode(
      uploadTaskPromise(alice.ref(bobImagePath).put(syntheticImage, metadata))
    );
    const missingCode = await rejectedCode(
      uploadTaskPromise(alice.ref(missingBobImagePath).put(syntheticImage, metadata))
    );

    expect(existingCode).toBe('storage/unauthorized');
    expect(missingCode).toBe(existingCode);
  });

  it('nega exclusao cross-user sem distinguir imagem existente de inexistente', async () => {
    const alice = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const existingCode = await rejectedCode(alice.ref(bobImagePath).delete());
    const missingCode = await rejectedCode(alice.ref(missingBobImagePath).delete());

    expect(existingCode).toBe('storage/unauthorized');
    expect(missingCode).toBe(existingCode);
  });
});
