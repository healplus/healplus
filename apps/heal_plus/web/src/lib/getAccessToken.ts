import { supabase } from './supabase';

/**
 * Returns the current Supabase session access token.
 *
 * Centralises token retrieval so callers that need an Authorization
 * header (HEAL Analyzer, Gemini service, reports) do not depend on
 * Firebase Auth anymore.
 */
export async function getAccessToken(): Promise<string> {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session?.access_token) {
    throw new Error('Sessão não encontrada. Faça login novamente.');
  }
  return session.access_token;
}
