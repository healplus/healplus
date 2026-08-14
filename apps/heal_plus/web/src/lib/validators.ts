import { MAX_IMAGE_UPLOAD_BYTES, MAX_IMAGE_UPLOAD_MB } from './constants';

export function validateImageFile(file: File) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    return `Formato inválido: ${file.name}. Use JPEG, PNG ou WebP.`;
  }

  if (file.size > MAX_IMAGE_UPLOAD_BYTES) {
    return `Arquivo maior que ${MAX_IMAGE_UPLOAD_MB} MB: ${file.name}.`;
  }

  return null;
}

export function assertEnvIsConfigured() {
  const missing = [
    'VITE_FIREBASE_API_KEY',
    'VITE_FIREBASE_AUTH_DOMAIN',
    'VITE_FIREBASE_PROJECT_ID',
    'VITE_FIREBASE_STORAGE_BUCKET',
    'VITE_FIREBASE_APP_ID'
  ].filter(key => !import.meta.env[key]);

  return missing;
}
