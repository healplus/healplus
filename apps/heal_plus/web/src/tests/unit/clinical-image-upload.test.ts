import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { uploadClinicalImage } from '../../lib/clinicalImageUpload';

const authMocks = vi.hoisted(() => ({
  getSession: vi.fn().mockResolvedValue({
    data: { session: { access_token: 'synthetic-session-token' } },
    error: null
  })
}));

vi.mock('../../lib/supabase', () => ({
  supabase: { auth: { getSession: authMocks.getSession } },
  supabaseUrl: 'https://synthetic-project.invalid',
  supabaseAnonKey: 'synthetic-public-key'
}));

class FakeXMLHttpRequest {
  static current: FakeXMLHttpRequest;
  static deferNext = false;

  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onabort: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onload: (() => void) | null = null;
  responseText = '{}';
  status = 201;
  headers = new Map<string, string>();
  method = '';
  url = '';
  body: FormData | null = null;
  deferResponse = FakeXMLHttpRequest.deferNext;

  constructor() {
    FakeXMLHttpRequest.current = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers.set(name.toLowerCase(), value);
  }

  send(body: FormData) {
    this.body = body;
    if (this.deferResponse) return;
    const file = body.get('');
    if (!(file instanceof File)) throw new Error('Arquivo ausente no multipart do teste.');
    this.upload.onprogress?.({ loaded: file.size / 2, total: file.size, lengthComputable: true } as ProgressEvent);
    this.onload?.();
  }

  abort() {
    this.onabort?.();
  }
}

describe('uploadClinicalImage', () => {
  beforeEach(() => {
    authMocks.getSession.mockClear();
    FakeXMLHttpRequest.deferNext = false;
    vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest);
  });

  afterEach(() => vi.unstubAllGlobals());

  it('envia com a sessão atual e publica progresso por bytes', async () => {
    const onProgress = vi.fn();
    const file = new File(['synthetic-image'], 'clinical.webp', { type: 'image/webp' });

    await uploadClinicalImage('user 1/patient/image.webp', file, { onProgress });

    expect(FakeXMLHttpRequest.current.method).toBe('POST');
    expect(FakeXMLHttpRequest.current.url).toBe(
      'https://synthetic-project.invalid/storage/v1/object/wound-images/user%201/patient/image.webp'
    );
    expect(FakeXMLHttpRequest.current.headers.get('authorization')).toBe('Bearer synthetic-session-token');
    expect(FakeXMLHttpRequest.current.headers.get('apikey')).toBe('synthetic-public-key');
    expect(FakeXMLHttpRequest.current.headers.get('x-upsert')).toBe('false');
    expect(FakeXMLHttpRequest.current.headers.has('content-type')).toBe(false);
    expect(FakeXMLHttpRequest.current.body?.get('cacheControl')).toBe('3600');
    expect(FakeXMLHttpRequest.current.body?.get('')).toBe(file);
    expect(onProgress).toHaveBeenCalledWith(file.size / 2, file.size);
    expect(onProgress).toHaveBeenLastCalledWith(file.size, file.size);
  });

  it('aborta a requisição em andamento', async () => {
    const controller = new AbortController();
    FakeXMLHttpRequest.deferNext = true;
    const promise = uploadClinicalImage(
      'user/patient/image.webp',
      new File(['synthetic-image'], 'clinical.webp', { type: 'image/webp' }),
      { signal: controller.signal }
    );
    await Promise.resolve();
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
  });
});
