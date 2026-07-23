export type AiProviderId = 'google' | 'openai' | 'groq' | 'openrouter' | 'custom';

export interface AiModelOption {
  id: string;
  label: string;
}

export interface AiProviderDefinition {
  id: AiProviderId;
  label: string;
  description: string;
  models: readonly AiModelOption[];
  apiKeyUrl?: string;
  endpoint?: string;
}

export interface AiProviderConfig {
  provider: AiProviderId;
  apiKey: string;
  model: string;
  endpoint: string;
}

export const AI_PROVIDERS: readonly AiProviderDefinition[] = [
  {
    id: 'google',
    label: 'Gemma',
    description: 'Gemma 4 pela API oficial do Google AI',
    apiKeyUrl: 'https://aistudio.google.com/app/apikey',
    endpoint: 'https://generativelanguage.googleapis.com/v1beta',
    models: [
      { id: 'gemma-4-26b-a4b-it', label: 'Gemma 4 26B A4B IT' },
      { id: 'gemma-4-31b-it', label: 'Gemma 4 31B IT' }
    ]
  },
  {
    id: 'openai',
    label: 'OpenAI',
    description: 'Modelos GPT pela API oficial da OpenAI',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
    endpoint: 'https://api.openai.com/v1/chat/completions',
    models: [
      { id: 'gpt-5.2', label: 'GPT-5.2' }
    ]
  },
  {
    id: 'groq',
    label: 'Groq',
    description: 'Modelos rápidos hospedados no GroqCloud',
    apiKeyUrl: 'https://console.groq.com/keys',
    endpoint: 'https://api.groq.com/openai/v1/chat/completions',
    models: [
      { id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B' },
      { id: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B' },
      { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B Versatile' }
    ]
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    description: 'Vários modelos usando uma única chave',
    apiKeyUrl: 'https://openrouter.ai/settings/keys',
    endpoint: 'https://openrouter.ai/api/v1/chat/completions',
    models: []
  },
  {
    id: 'custom',
    label: 'Outro endpoint',
    description: 'API compatível com o formato da OpenAI',
    models: []
  }
] as const;

const STORAGE_PREFIX = 'redisus-ai-credential-v1';

export function getAiProviderDefinition(provider: AiProviderId): AiProviderDefinition {
  return AI_PROVIDERS.find(item => item.id === provider) ?? AI_PROVIDERS[0];
}

export function createDefaultAiProviderConfig(provider: AiProviderId = 'google'): AiProviderConfig {
  const definition = getAiProviderDefinition(provider);
  return {
    provider,
    apiKey: '',
    model: definition.models[0]?.id ?? '',
    endpoint: definition.endpoint ?? ''
  };
}

export function validateAiProviderConfig(config: AiProviderConfig): string | null {
  if (!config.apiKey.trim()) {
    return 'Informe a chave de API.';
  }
  if (!config.model.trim()) {
    return 'Informe o modelo.';
  }
  if (config.provider !== 'custom') {
    return null;
  }

  let url: URL;
  try {
    url = new URL(config.endpoint);
  } catch {
    return 'Informe uma URL de endpoint válida.';
  }

  const localHttp =
    url.protocol === 'http:' &&
    (url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.hostname === '::1');
  if (url.protocol !== 'https:' && !localHttp) {
    return 'Use HTTPS. HTTP é permitido somente para um endpoint local.';
  }
  if (url.username || url.password) {
    return 'Não inclua credenciais na URL.';
  }
  return null;
}

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}:${userId}`;
}

function getSessionStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function isProviderId(value: unknown): value is AiProviderId {
  return value === 'google' || value === 'openai' || value === 'groq' || value === 'openrouter' || value === 'custom';
}

export function loadAiProviderConfig(userId: string): AiProviderConfig | null {
  const storage = getSessionStorage();
  if (!storage) return null;

  try {
    const value = JSON.parse(storage.getItem(storageKey(userId)) ?? 'null') as Partial<AiProviderConfig> | null;
    if (
      !value ||
      !isProviderId(value.provider) ||
      typeof value.apiKey !== 'string' ||
      typeof value.model !== 'string' ||
      typeof value.endpoint !== 'string'
    ) {
      return null;
    }
    const config: AiProviderConfig = {
      provider: value.provider,
      apiKey: value.apiKey,
      model: value.model,
      endpoint: value.endpoint
    };
    return validateAiProviderConfig(config) ? null : config;
  } catch {
    return null;
  }
}

export function saveAiProviderConfig(userId: string, config: AiProviderConfig): void {
  const error = validateAiProviderConfig(config);
  if (error) throw new Error(error);

  const storage = getSessionStorage();
  if (!storage) {
    throw new Error('O armazenamento seguro da sessão não está disponível neste navegador.');
  }
  storage.setItem(storageKey(userId), JSON.stringify(config));
}

export function clearAiProviderConfig(userId: string): void {
  getSessionStorage()?.removeItem(storageKey(userId));
}

export function aiProviderLabel(config: AiProviderConfig): string {
  const provider = getAiProviderDefinition(config.provider);
  const model = provider.models.find(item => item.id === config.model);
  return `${provider.label} · ${model?.label ?? config.model}`;
}