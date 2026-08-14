import { MAX_IMAGE_UPLOAD_BYTES, MAX_IMAGE_UPLOAD_MB } from './constants';
import { validateImageFile } from './validators';

export const CLINICAL_IMAGE_MAX_DIMENSION = 2560;
export const CLINICAL_IMAGE_WEBP_QUALITY = 0.84;

interface PrepareClinicalImageOptions {
  signal?: AbortSignal;
}

interface DrawableImage {
  source: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) throw new DOMException('Preparação da imagem cancelada.', 'AbortError');
}

async function loadDrawableImage(file: File, signal?: AbortSignal): Promise<DrawableImage> {
  throwIfAborted(signal);

  if ('createImageBitmap' in globalThis) {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    throwIfAborted(signal);
    return {
      source: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      close: () => bitmap.close()
    };
  }

  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      const abort = () => {
        element.src = '';
        reject(new DOMException('Preparação da imagem cancelada.', 'AbortError'));
      };
      signal?.addEventListener('abort', abort, { once: true });
      element.onload = () => {
        signal?.removeEventListener('abort', abort);
        resolve(element);
      };
      element.onerror = () => {
        signal?.removeEventListener('abort', abort);
        reject(new Error('Não foi possível decodificar a imagem selecionada.'));
      };
      element.src = objectUrl;
    });
    throwIfAborted(signal);
    return {
      source: image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      close: () => undefined
    };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function encodeCanvas(canvas: HTMLCanvasElement, type: string, quality: number, signal?: AbortSignal) {
  return new Promise<Blob>((resolve, reject) => {
    throwIfAborted(signal);
    canvas.toBlob(blob => {
      try {
        throwIfAborted(signal);
        if (!blob) throw new Error('O navegador não conseguiu preparar a imagem para envio.');
        resolve(blob);
      } catch (error) {
        reject(error);
      }
    }, type, quality);
  });
}

export async function prepareClinicalImage(
  file: File,
  { signal }: PrepareClinicalImageOptions = {}
): Promise<File> {
  const validationError = validateImageFile(file);
  if (validationError) throw new Error(validationError);

  const drawable = await loadDrawableImage(file, signal);
  try {
    if (!drawable.width || !drawable.height) {
      throw new Error('A imagem selecionada não possui dimensões válidas.');
    }

    const scale = Math.min(1, CLINICAL_IMAGE_MAX_DIMENSION / Math.max(drawable.width, drawable.height));
    const width = Math.max(1, Math.round(drawable.width * scale));
    const height = Math.max(1, Math.round(drawable.height * scale));
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext('2d', { alpha: false });
    if (!context) throw new Error('O navegador não oferece suporte ao preparo seguro de imagens.');
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, width, height);
    context.drawImage(drawable.source, 0, 0, width, height);

    let encoded = await encodeCanvas(canvas, 'image/webp', CLINICAL_IMAGE_WEBP_QUALITY, signal);
    if (encoded.type !== 'image/webp') {
      encoded = await encodeCanvas(canvas, 'image/jpeg', 0.88, signal);
    }
    if (encoded.size > MAX_IMAGE_UPLOAD_BYTES) {
      throw new Error(`A imagem preparada ainda excede o limite de ${MAX_IMAGE_UPLOAD_MB} MB.`);
    }

    const extension = encoded.type === 'image/webp' ? 'webp' : 'jpg';
    return new File([encoded], `clinical-image-${crypto.randomUUID()}.${extension}`, {
      type: encoded.type,
      lastModified: Date.now()
    });
  } finally {
    drawable.close();
  }
}
