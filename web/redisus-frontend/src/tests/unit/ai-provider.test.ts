import { beforeEach, describe, expect, it } from 'vitest';

import {
  AI_PROVIDERS,
  clearAiProviderConfig,
  createDefaultAiProviderConfig,
  loadAiProviderConfig,
  saveAiProviderConfig,
  validateAiProviderConfig
} from '../../features/chat/aiProvider';

describe('BYOK AI provider configuration', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('keeps credentials in session storage and isolates them by user', () => {
    const config = {
      ...createDefaultAiProviderConfig('google'),
      apiKey: 'user-owned-key'
    };

    saveAiProviderConfig('user-a', config);

    expect(loadAiProviderConfig('user-a')).toEqual(config);
    expect(loadAiProviderConfig('user-b')).toBeNull();
    expect(localStorage.length).toBe(0);

    clearAiProviderConfig('user-a');
    expect(loadAiProviderConfig('user-a')).toBeNull();
  });

  it('offers the visible provider catalog with safe default endpoints', () => {
    expect(AI_PROVIDERS.map(provider => provider.id)).toEqual([
      'google',
      'openai',
      'groq',
      'openrouter',
      'custom'
    ]);
    expect(createDefaultAiProviderConfig('openai')).toMatchObject({
      model: 'gpt-5.2',
      endpoint: 'https://api.openai.com/v1/chat/completions'
    });
    expect(createDefaultAiProviderConfig('openrouter').endpoint).toBe(
      'https://openrouter.ai/api/v1/chat/completions'
    );
  });

  it('requires HTTPS for remote custom endpoints', () => {
    const config = {
      provider: 'custom' as const,
      apiKey: 'key',
      model: 'custom-model',
      endpoint: 'http://example.com/v1/chat/completions'
    };

    expect(validateAiProviderConfig(config)).toContain('HTTPS');
    expect(
      validateAiProviderConfig({
        ...config,
        endpoint: 'http://localhost:11434/v1/chat/completions'
      })
    ).toBeNull();
  });

  it('does not accept credentials embedded in a custom endpoint URL', () => {
    expect(
      validateAiProviderConfig({
        provider: 'custom',
        apiKey: 'key',
        model: 'custom-model',
        endpoint: 'https://user:password@example.com/v1/chat/completions'
      })
    ).toBe('Não inclua credenciais na URL.');
  });

  it('never accepts empty credentials or model identifiers', () => {
    expect(
      validateAiProviderConfig({
        ...createDefaultAiProviderConfig('google'),
        apiKey: ''
      })
    ).toBe('Informe a chave de API.');

    expect(
      validateAiProviderConfig({
        ...createDefaultAiProviderConfig('google'),
        apiKey: 'key',
        model: ''
      })
    ).toBe('Informe o modelo.');
  });
});
