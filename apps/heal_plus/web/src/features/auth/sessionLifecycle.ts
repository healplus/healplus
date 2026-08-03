export const AI_CREDENTIAL_STORAGE_PREFIX = 'redisus-ai-credential-v1:';
export const CHAT_HISTORY_STORAGE_PREFIX = 'redisus-chat-history-v2:';
export const HEALPLUS_CHAT_STORAGE_PREFIX = 'healplus_ai_chat_sessions_v3:';
export const AI_CONSENT_LOG_STORAGE_PREFIX = 'healplus_ai_consent_log_v1:';

const SENSITIVE_STORAGE_PREFIXES = [
  AI_CREDENTIAL_STORAGE_PREFIX,
  CHAT_HISTORY_STORAGE_PREFIX,
  HEALPLUS_CHAT_STORAGE_PREFIX,
  AI_CONSENT_LOG_STORAGE_PREFIX
] as const;

function getStorage(kind: 'localStorage' | 'sessionStorage'): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window[kind];
  } catch {
    return null;
  }
}

function removeMatchingKeys(storage: Storage | null, userId?: string): void {
  if (!storage) return;

  try {
    const keys: string[] = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (!key) continue;
      if (
        SENSITIVE_STORAGE_PREFIXES.some(prefix =>
          userId ? key === `${prefix}${userId}` : key.startsWith(prefix)
        )
      ) {
        keys.push(key);
      }
    }
    keys.forEach(key => storage.removeItem(key));
  } catch {
    // Storage restrictions must not prevent the authentication state transition.
  }
}

export function clearSensitiveSessionState(userId?: string): void {
  removeMatchingKeys(getStorage('sessionStorage'), userId);
  removeMatchingKeys(getStorage('localStorage'), userId);
}

export function isolateSensitiveSessionState(currentUserId: string): void {
  const sessionStorage = getStorage('sessionStorage');
  if (sessionStorage) {
    try {
      const allowedKeys = new Set(
        SENSITIVE_STORAGE_PREFIXES.map(prefix => `${prefix}${currentUserId}`)
      );
      const keysToRemove: string[] = [];
      for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);
        if (
          key &&
          SENSITIVE_STORAGE_PREFIXES.some(prefix => key.startsWith(prefix)) &&
          !allowedKeys.has(key)
        ) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => sessionStorage.removeItem(key));
    } catch {
      // A blocked storage API is treated as an unavailable cache.
    }
  }

  // Clinical conversations used to be persisted in localStorage. Remove all
  // legacy copies because they can outlive both logout and the browser session.
  removeMatchingKeys(getStorage('localStorage'));
}
