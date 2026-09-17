import { supabase } from './supabase';
import type { WoundImage } from './types';

export async function clinicalImageUrl(storagePath: string): Promise<string> {
  const { data, error } = await supabase.storage.from('wound-images').createSignedUrl(storagePath, 3600);
  if (error || !data?.signedUrl) throw new Error('Não foi possível carregar a imagem. Atualize a página para tentar novamente.');
  return data.signedUrl;
}

export async function hydrateClinicalImages(images: WoundImage[]): Promise<WoundImage[]> {
  return Promise.all(images.map(async image => ({
    ...image,
    // Always resolve from the private object; never reuse an old public URL.
    downloadURL: await clinicalImageUrl(image.storagePath)
  })));
}

export function persistableImages(images: WoundImage[]): WoundImage[] {
  return images.map(image => ({ ...image, downloadURL: '' }));
}
