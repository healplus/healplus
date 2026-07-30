import { createClient } from '@supabase/supabase-js';
import { auth } from './firebase';

const configuredSupabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const configuredSupabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

export const isSupabaseConfigured = Boolean(configuredSupabaseUrl && configuredSupabaseAnonKey);

// Keep public routes renderable in local development. Data-backed routes are
// already protected by the Firebase configuration check in App.tsx.
const supabaseUrl = configuredSupabaseUrl || 'http://127.0.0.1:54321';
const supabaseAnonKey = configuredSupabaseAnonKey || 'local-development-anon-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  // Supabase must be configured to trust this Firebase project as a
  // third-party identity provider. RLS remains the authorization boundary.
  accessToken: async () => (await auth.currentUser?.getIdToken(false)) ?? null
});
