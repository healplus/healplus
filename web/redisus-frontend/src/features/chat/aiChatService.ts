import { getAiProviderDefinition, type AiProviderConfig } from './aiProvider';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface GenerateAiReplyInput {
  config: AiProviderConfig;
  messages: readonly AiChatMessage[];
  systemPrompt: string;
  thinkingLevel: 'minimal' | 'high';
  signal?: AbortSignal;
}

interface GoogleGenerateResponse {
  candidates?: Array<{
    content?: {
      parts?: Array<{ text?: string; thought?: boolean }>;
    };
  }>;
  error?: { message?: string };
}

interface OpenAiGenerateResponse {
  choices?: Array<{
    message?: {
      content?: string | Array<{ text?: string; type?: string }>;
    };
  }>;
  error?: { message?: string };
}

async function responseError(response: Response): Promise<Error> {
  let detail = '';
  try {
    const payload = (await response.json()) as { error?: { message?: string }; message?: string };
    detail = payload.error?.message || payload.message || '';
  } catch {
    detail = '';
  }
  const suffix = detail ? `: ${detail.slice(0, 240)}` : '';
  return new Error(`O provedor recusou a solicitação (${response.status})${suffix}`);
}

function googleModelName(model: string): string {
  return model.trim().replace(/^models\//, '');
}

async function generateWithGoogle(input: GenerateAiReplyInput): Promise<string> {
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

  if (!response.ok) throw await responseError(response);
  const payload = (await response.json()) as GoogleGenerateResponse;
  const text = payload.candidates?.[0]?.content?.parts
    ?.filter(part => !part.thought)
    .map(part => part.text ?? '')
    .join('')
    .trim();
  if (!text) {
    throw new Error(payload.error?.message || 'O provedor retornou uma resposta vazia.');
  }
  return text;
}

function openAiText(payload: OpenAiGenerateResponse): string {
  const content = payload.choices?.[0]?.message?.content;
  if (typeof content === 'string') return content.trim();
  if (!Array.isArray(content)) return '';
  return content.map(part => part.text ?? '').join('').trim();
}

async function generateWithOpenAiCompatible(input: GenerateAiReplyInput): Promise<string> {
  const definition = getAiProviderDefinition(input.config.provider);
  const endpoint = input.config.provider === 'custom'
    ? input.config.endpoint.trim()
    : definition.endpoint ?? '';
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${input.config.apiKey}`,
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

  if (!response.ok) throw await responseError(response);
  const payload = (await response.json()) as OpenAiGenerateResponse;
  const text = openAiText(payload);
  if (!text) {
    throw new Error(payload.error?.message || 'O provedor retornou uma resposta vazia.');
  }
  return text;
}

export async function generateAiReply(input: GenerateAiReplyInput): Promise<string> {
  if (input.config.provider === 'google') {
    return generateWithGoogle(input);
  }
  return generateWithOpenAiCompatible(input);
}
