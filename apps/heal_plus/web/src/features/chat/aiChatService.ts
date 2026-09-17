import type { AiProviderConfig } from './aiProvider';
import {
  aiProviderFailureMessage,
  getAiTransport,
  normalizeAiProviderFailure,
  type AiTransport
} from './aiTransport';
import { validateClinicalAiOutput } from './clinicalOutputPolicy';
import {
  consumeAiTransmissionAuthorization,
  type AiTransmissionAuthorization
} from './externalTransmission';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface GenerateAiReplyInput {
  config: AiProviderConfig;
  messages: readonly AiChatMessage[];
  systemPrompt: string;
  thinkingLevel: 'minimal' | 'high';
  signal?: AbortSignal;
  timeoutMs?: number;
  transport?: AiTransport;
  authorization?: AiTransmissionAuthorization;
}

function requestSignal(signal: AbortSignal | undefined, timeoutMs: number): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  return signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
}

export async function generateAiReply(input: GenerateAiReplyInput): Promise<string> {
  consumeAiTransmissionAuthorization(
    input.authorization,
    input.config,
    input.messages.length
  );
  const transport = input.transport ?? getAiTransport(input.config);

  try {
    const response = await transport.generate({
      config: input.config,
      messages: input.messages,
      signal: requestSignal(input.signal, input.timeoutMs ?? 30_000),
      systemPrompt: input.systemPrompt,
      thinkingLevel: input.thinkingLevel
    });
    return validateClinicalAiOutput(response).text;
  } catch (error) {
    const failure = normalizeAiProviderFailure(error);
    if (failure.code === 'aborted' && input.signal?.aborted) throw error;
    throw new Error(aiProviderFailureMessage(failure));
  }
}
