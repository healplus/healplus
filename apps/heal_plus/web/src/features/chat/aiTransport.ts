import { getAiProviderDefinition, type AiProviderConfig } from './aiProvider';

export interface AiTransportMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AiTransportInput {
  config: AiProviderConfig;
  messages: readonly AiTransportMessage[];
  signal: AbortSignal;
  systemPrompt: string;
  thinkingLevel: 'minimal' | 'high';
}

export interface AiTransport {
  generate(input: AiTransportInput): Promise<string>;
}

export type AiProviderFailureCode =
  | 'aborted'
  | 'http_error'
  | 'invalid_response'
  | 'network_error'
  | 'timeout';

export class AiProviderFailure extends Error {
  constructor(
    readonly code: AiProviderFailureCode,
    readonly status?: number
  ) {
    super(code);
    this.name = 'AiProviderFailure';
  }
}

interface GoogleGenerateResponse {
  candidates?: Array<{
    content?: {
      parts?: Array<{ text?: string; thought?: boolean }>;
    };
  }>;
}

interface OpenAiGenerateResponse {
  choices?: Array<{
    message?: {
      content?: string | Array<{ text?: string; type?: string }>;
    };
  }>;
}

function httpFailure(response: Response): AiProviderFailure {
  return new AiProviderFailure('http_error', response.status);
}

function googleModelName(model: string): string {
  return model.trim().replace(/^models\//, '');
}

const googleTransport: AiTransport = {
  async generate(input) {
    const model = googleModelName(input.config.model);
    const endpoint =
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-goog-api-key': input.config.apiKey
      },
      body: JSON.stringify({
        system_instruction: {
          parts: [{ text: input.systemPrompt }]
        },
        contents: input.messages.map(message => ({
          role: message.role === 'assistant' ? 'model' : 'user',
          parts: [{ text: message.content }]
        })),
        generationConfig: {
          thinkingConfig: {
            thinkingLevel: input.thinkingLevel
          }
        }
      }),
      signal: input.signal
    });

    if (!response.ok) throw httpFailure(response);
    const payload = (await response.json()) as GoogleGenerateResponse;
    const text = payload.candidates?.[0]?.content?.parts
      ?.filter(part => !part.thought)
      .map(part => part.text ?? '')
      .join('')
      .trim();
    if (!text) throw new AiProviderFailure('invalid_response');
    return text;
  }
};

function openAiText(payload: OpenAiGenerateResponse): string {
  const content = payload.choices?.[0]?.message?.content;
  if (typeof content === 'string') return content.trim();
  if (!Array.isArray(content)) return '';
  return content.map(part => part.text ?? '').join('').trim();
}

const openAiCompatibleTransport: AiTransport = {
  async generate(input) {
    const definition = getAiProviderDefinition(input.config.provider);
    const endpoint = input.config.provider === 'custom'
      ? input.config.endpoint.trim()
      : definition.endpoint ?? '';
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${input.config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: input.config.model,
        messages: [
          { role: 'system', content: input.systemPrompt },
          ...input.messages
        ]
      }),
      signal: input.signal
    });

    if (!response.ok) throw httpFailure(response);
    const payload = (await response.json()) as OpenAiGenerateResponse;
    const text = openAiText(payload);
    if (!text) throw new AiProviderFailure('invalid_response');
    return text;
  }
};

export function getAiTransport(config: AiProviderConfig): AiTransport {
  return config.provider === 'google' ? googleTransport : openAiCompatibleTransport;
}

export function normalizeAiProviderFailure(error: unknown): AiProviderFailure {
  if (error instanceof AiProviderFailure) return error;
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new AiProviderFailure('aborted');
  }
  if (error instanceof DOMException && error.name === 'TimeoutError') {
    return new AiProviderFailure('timeout');
  }
  return new AiProviderFailure('network_error');
}

export function aiProviderFailureMessage(error: AiProviderFailure): string {
  if (error.code === 'timeout') {
    return 'O provedor demorou mais que o limite seguro. Tente novamente.';
  }
  if (error.code === 'invalid_response') {
    return 'O provedor retornou uma resposta inválida. Tente outro modelo ou provedor.';
  }
  if (error.code === 'http_error') {
    return error.status === 401 || error.status === 403
      ? 'O provedor recusou a credencial. Revise a chave e tente novamente.'
      : 'O provedor não conseguiu concluir a solicitação. Tente novamente mais tarde.';
  }
  if (error.code === 'aborted') return 'A resposta foi interrompida.';
  return 'Não foi possível acessar o provedor. Verifique a conexão e tente novamente.';
}
