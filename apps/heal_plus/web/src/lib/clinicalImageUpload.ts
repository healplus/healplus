import { supabase, supabaseAnonKey, supabaseUrl } from './supabase';

interface ClinicalImageUploadOptions {
  signal?: AbortSignal;
  onProgress?: (loadedBytes: number, totalBytes: number) => void;
}

function encodedStoragePath(path: string) {
  return path.split('/').map(encodeURIComponent).join('/');
}

function responseMessage(request: XMLHttpRequest) {
  try {
    const body = JSON.parse(request.responseText) as { message?: string; error?: string };
    return body.message || body.error || `Falha no envio da imagem (${request.status}).`;
  } catch {
    return `Falha no envio da imagem (${request.status}).`;
  }
}

export async function uploadClinicalImage(
  storagePath: string,
  file: File,
  { signal, onProgress }: ClinicalImageUploadOptions = {}
) {
  if (signal?.aborted) throw new DOMException('Envio cancelado.', 'AbortError');

  const { data, error } = await supabase.auth.getSession();
  if (error) throw new Error(error.message);
  if (!data.session?.access_token) {
    throw new Error('Sessão expirada. Entre novamente antes de enviar imagens.');
  }
  if (signal?.aborted) throw new DOMException('Envio cancelado.', 'AbortError');

  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    const body = new FormData();
    const abort = () => request.abort();

    body.append('cacheControl', '3600');
    body.append('', file);
    signal?.addEventListener('abort', abort, { once: true });

    const finish = () => signal?.removeEventListener('abort', abort);
    request.upload.onprogress = event => {
      onProgress?.(event.loaded, event.lengthComputable ? event.total : file.size);
    };
    request.onerror = () => {
      finish();
      reject(new Error('A conexão foi interrompida durante o envio da imagem.'));
    };
    request.onabort = () => {
      finish();
      reject(new DOMException('Envio cancelado.', 'AbortError'));
    };
    request.onload = () => {
      finish();
      if (request.status >= 200 && request.status < 300) {
        onProgress?.(file.size, file.size);
        resolve();
        return;
      }
      reject(new Error(responseMessage(request)));
    };

    request.open('POST', `${supabaseUrl}/storage/v1/object/wound-images/${encodedStoragePath(storagePath)}`);
    request.setRequestHeader('Authorization', `Bearer ${data.session.access_token}`);
    request.setRequestHeader('apikey', supabaseAnonKey);
    request.setRequestHeader('x-upsert', 'false');
    request.send(body);
  });
}
