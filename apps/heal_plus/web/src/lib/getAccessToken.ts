import { supabase } from './supabase';

/** Returns the current Supabase session token for authenticated API requests. */
export async function getAccessToken(): Promise<string> {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session?.access_token) {
    throw new Error('Sessão não encontrada. Faça login novamente.');
  }
  return session.access_token;
}
