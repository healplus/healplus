import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CLINICAL_IMAGE_MAX_DIMENSION, prepareClinicalImage } from '../../lib/clinicalImagePreparation';

describe('prepareClinicalImage', () => {
  const drawImage = vi.fn();
  const close = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({
      width: 5000,
      height: 2500,
      close
    }));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      fillStyle: '',
      fillRect: vi.fn(),
      drawImage
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => {
      callback(new Blob(['reencoded-without-source-metadata'], { type: 'image/webp' }));
    });
    vi.stubGlobal('crypto', { randomUUID: () => 'synthetic-id' });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  const readFile = (file: File) => new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });

  it('redimensiona, reencoda em WebP e troca o nome de origem', async () => {
    const source = new File(['EXIF:synthetic-sensitive-metadata'], 'patient-name.jpg', { type: 'image/jpeg' });

    const prepared = await prepareClinicalImage(source);

    expect(prepared.name).toBe('clinical-image-synthetic-id.webp');
    expect(prepared.type).toBe('image/webp');
    expect(await readFile(prepared)).toBe('reencoded-without-source-metadata');
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, CLINICAL_IMAGE_MAX_DIMENSION, 1280);
    expect(close).toHaveBeenCalled();
  });

  it('interrompe antes de decodificar quando cancelado', async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(prepareClinicalImage(
      new File(['synthetic'], 'synthetic.png', { type: 'image/png' }),
      { signal: controller.signal }
    )).rejects.toMatchObject({ name: 'AbortError' });
  });
});
