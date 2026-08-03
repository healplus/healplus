import { beforeEach, describe, expect, it } from 'vitest';

import {
  AI_CREDENTIAL_STORAGE_PREFIX,
  AI_CONSENT_LOG_STORAGE_PREFIX,
  CHAT_HISTORY_STORAGE_PREFIX,
  HEALPLUS_CHAT_STORAGE_PREFIX,
  clearSensitiveSessionState,
  isolateSensitiveSessionState
} from '../../features/auth/sessionLifecycle';

describe('ciclo de dados sensíveis da sessão', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('remove credenciais BYOK, histórico e cópias legadas no logout', () => {
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'segredo');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'dados-clinicos');
    sessionStorage.setItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-a`, 'dados-clinicos-v3');
    sessionStorage.setItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-a`, 'recibo-sem-conteudo');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'copia-legada');
    sessionStorage.setItem('preferencia-nao-sensivel', 'preservada');

    clearSensitiveSessionState('user-a');

    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem('preferencia-nao-sensivel')).toBe('preservada');
  });

  it('isola a conta restaurada e elimina estado pertencente a outro usuário', () => {
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`, 'chave-a');
    sessionStorage.setItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-b`, 'chave-b');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'historico-a');
    sessionStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-b`, 'historico-b');
    sessionStorage.setItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-a`, 'historico-v3-a');
    sessionStorage.setItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-b`, 'historico-v3-b');
    sessionStorage.setItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-a`, 'recibo-a');
    sessionStorage.setItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-b`, 'recibo-b');
    localStorage.setItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`, 'legado-a');

    isolateSensitiveSessionState('user-b');

    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-a`)).toBeNull();
    expect(sessionStorage.getItem(`${AI_CREDENTIAL_STORAGE_PREFIX}user-b`)).toBe('chave-b');
    expect(sessionStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-b`)).toBe('historico-b');
    expect(sessionStorage.getItem(`${HEALPLUS_CHAT_STORAGE_PREFIX}user-b`)).toBe('historico-v3-b');
    expect(sessionStorage.getItem(`${AI_CONSENT_LOG_STORAGE_PREFIX}user-b`)).toBe('recibo-b');
    expect(localStorage.getItem(`${CHAT_HISTORY_STORAGE_PREFIX}user-a`)).toBeNull();
  });
});
