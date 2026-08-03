import { getAiProviderDefinition, type AiProviderConfig } from './aiProvider';
import { AI_CONSENT_LOG_STORAGE_PREFIX } from '../auth/sessionLifecycle';

export type AiTransmissionCategory = 'current-message' | 'recent-conversation';

export interface AiTransmissionAuthorization {
  readonly id: string;
  readonly provider: AiProviderConfig['provider'];
  readonly providerFingerprint: string;
  readonly destination: string;
  readonly purpose: 'clinical-decision-support';
  readonly dataCategories: readonly AiTransmissionCategory[];
  readonly explicitAction: 'authorized-once';
  readonly issuedAt: number;
  readonly expiresAt: number;
}

export interface AiTransmissionReceipt {
  id: string;
  provider: AiProviderConfig['provider'];
  destination: string;
  purpose: AiTransmissionAuthorization['purpose'];
  dataCategories: AiTransmissionCategory[];
  authorizedAt: number;
}

const consumedAuthorizations = new WeakSet<AiTransmissionAuthorization>();

function configuredEndpoint(config: AiProviderConfig): string {
  const definition = getAiProviderDefinition(config.provider);
  return config.provider === 'custom' ? config.endpoint.trim() : definition.endpoint ?? '';
}

export function aiTransmissionDestination(config: AiProviderConfig): string {
  const endpoint = configuredEndpoint(config);
  try {
    const url = new URL(endpoint);
    url.search = '';
    url.hash = '';
    return `${url.origin}${url.pathname.replace(/\/+$/, '')}`;
  } catch {
    return 'destino não configurado';
  }
}

export function aiProviderFingerprint(config: AiProviderConfig): string {
  return [config.provider, config.model.trim(), configuredEndpoint(config)].join('|');
}

export function createAiTransmissionAuthorization(
  config: AiProviderConfig,
  includeConversationHistory: boolean,
  now = Date.now()
): AiTransmissionAuthorization {
  return Object.freeze({
    id: globalThis.crypto?.randomUUID?.() ?? `consent-${now}-${Math.random().toString(36).slice(2)}`,
    provider: config.provider,
    providerFingerprint: aiProviderFingerprint(config),
    destination: aiTransmissionDestination(config),
    purpose: 'clinical-decision-support' as const,
    dataCategories: [
      'current-message' as const,
      ...(includeConversationHistory ? (['recent-conversation'] as const) : [])
    ],
    explicitAction: 'authorized-once' as const,
    issuedAt: now,
    expiresAt: now + 2 * 60_000
  });
}

export function consumeAiTransmissionAuthorization(
  authorization: AiTransmissionAuthorization | undefined,
  config: AiProviderConfig,
  messageCount: number,
  now = Date.now()
): void {
  if (!authorization || authorization.explicitAction !== 'authorized-once') {
    throw new Error('Autorize este envio antes de contatar o provedor de IA.');
  }
  if (consumedAuthorizations.has(authorization)) {
    throw new Error('Esta autorização já foi utilizada. Confirme o novo envio.');
  }
  if (
    authorization.expiresAt < now ||
    authorization.provider !== config.provider ||
    authorization.providerFingerprint !== aiProviderFingerprint(config) ||
    authorization.destination !== aiTransmissionDestination(config)
  ) {
    throw new Error('O provedor mudou ou a autorização expirou. Confirme o envio novamente.');
  }
  if (!authorization.dataCategories.includes('current-message')) {
    throw new Error('A autorização não cobre a mensagem atual.');
  }
  if (messageCount > 1 && !authorization.dataCategories.includes('recent-conversation')) {
    throw new Error('O histórico não foi autorizado para este envio.');
  }
  consumedAuthorizations.add(authorization);
}

export function toAiTransmissionReceipt(
  authorization: AiTransmissionAuthorization
): AiTransmissionReceipt {
  return {
    id: authorization.id,
    provider: authorization.provider,
    destination: authorization.destination,
    purpose: authorization.purpose,
    dataCategories: [...authorization.dataCategories],
    authorizedAt: authorization.issuedAt
  };
}

export function recordAiTransmissionConsent(userId: string, receipt: AiTransmissionReceipt): void {
  try {
    const storage = window.sessionStorage;
    const key = `${AI_CONSENT_LOG_STORAGE_PREFIX}${userId}`;
    const parsed = JSON.parse(storage.getItem(key) ?? '[]') as unknown;
    const previous = Array.isArray(parsed) ? parsed : [];
    storage.setItem(key, JSON.stringify([...previous.slice(-99), receipt]));
  } catch {
    // O envio continua bloqueado pela autorização em memória; a UI não expõe detalhes internos.
  }
}
