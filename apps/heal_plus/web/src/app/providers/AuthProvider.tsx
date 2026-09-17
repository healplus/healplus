import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { User } from '@supabase/supabase-js';

import { supabase, isSupabaseConfigured } from '../../lib/supabase';
import type { UserProfile } from '../../lib/types';
import { ensureUserProfile } from '../../features/auth/authService';
import {
  clearSensitiveSessionState,
  isolateSensitiveSessionState
} from '../../features/auth/sessionLifecycle';

export interface AppUser extends User {
  uid: string;
  displayName: string | null;
  photoURL: string | null;
  providerData: Array<{ providerId: string }>;
  metadata: {
    creationTime?: string;
    lastSignInTime?: string;
  };
}

function adaptUser(supabaseUser: User | null): AppUser | null {
  if (!supabaseUser) return null;
  return {
    ...supabaseUser,
    uid: supabaseUser.id,
    displayName: supabaseUser.user_metadata?.full_name || supabaseUser.email?.split('@')[0] || 'Profissional',
    photoURL: supabaseUser.user_metadata?.avatar_url || null,
    providerData: (supabaseUser.app_metadata?.providers || []).map((p: string) => ({ providerId: p })),
    metadata: {
      creationTime: supabaseUser.created_at,
      lastSignInTime: supabaseUser.last_sign_in_at
    }
  };
}

interface AuthContextValue {
  user: AppUser | null;
  profile: UserProfile | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const previousUserId = useRef<string | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured) {
      clearSensitiveSessionState();
      void supabase.removeAllChannels();
      setLoadingAuth(false);
      return undefined;
    }

    let active = true;
    let latestTransition = 0;
    let channelCleanup = Promise.resolve();

    const transitionIdentity = (rawUser: User | null) => {
      const nextUser = adaptUser(rawUser);
      const transition = ++latestTransition;
      const previousId = previousUserId.current;
      const nextId = nextUser?.id ?? null;
      const identityChanged = previousId !== nextId;

      if (!nextId) {
        clearSensitiveSessionState(previousId ?? undefined);
      } else {
        if (previousId && previousId !== nextId) {
          clearSensitiveSessionState(previousId);
        }
        isolateSensitiveSessionState(nextId);
      }

      if (!identityChanged) {
        setUser(nextUser);
        setLoadingAuth(false);
        return;
      }

      setUser(null);
      setProfile(null);
      setLoadingProfile(Boolean(nextUser));
      setLoadingAuth(Boolean(nextUser));

      channelCleanup = channelCleanup
        .catch(() => undefined)
        .then(() => supabase.removeAllChannels())
        .then(() => undefined, () => undefined);

      void channelCleanup.then(() => {
        if (!active || transition !== latestTransition) return;

        previousUserId.current = nextId;
        setUser(nextUser);
        if (nextUser) {
          void ensureUserProfile(nextUser.id).catch(() => undefined);
        } else {
          setLoadingProfile(false);
        }
        setLoadingAuth(false);
      });
    };

    // Initialise from existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (active) transitionIdentity(session?.user ?? null);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (active) transitionIdentity(session?.user ?? null);
      }
    );

    return () => {
      active = false;
      latestTransition += 1;
      subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!user) {
      setProfile(null);
      setLoadingProfile(false);
      return undefined;
    }

    setLoadingProfile(true);
    setProfile(null);
    let active = true;

    const fetchProfile = async () => {
      const { data, error } = await supabase
        .from('users')
        .select('*')
        .eq('uid', user.id)
        .maybeSingle();

      if (error) {
        if (active) setLoadingProfile(false);
        return;
      }

      if (data && active) {
        setProfile({
          uid: data.uid,
          displayName: data.display_name,
          email: data.email,
          photoURL: data.photo_url || null,
          providerIds: data.provider_ids || [],
          role: (data.role as UserProfile['role']) || 'professional',
          settings: data.settings || {},
          professionalArea: data.professional_area || '',
          clinicName: data.clinic_name || '',
          phone: data.phone || '',
          onboardingCompleted: data.onboarding_completed || false,
          createdAt: data.created_at,
          updatedAt: data.updated_at
        });
      }
      if (active) setLoadingProfile(false);
    };

    void fetchProfile();

    const channel = supabase
      .channel(`user-profile-changes-${user.id}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'users', filter: `uid=eq.${user.id}` },
        () => {
          if (active) void fetchProfile();
        }
      )
      .subscribe();

    return () => {
      active = false;
      void supabase.removeChannel(channel);
    };
  }, [user]);

  const value = useMemo(
    () => ({ user, profile, loading: loadingAuth || loadingProfile }),
    [loadingAuth, loadingProfile, profile, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return context;
}
