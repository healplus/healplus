import { afterEach, describe, expect, it, vi } from 'vitest';

import { generateAiReply } from '../../features/chat/aiChatService';
import { createDefaultAiProviderConfig } from '../../features/chat/aiProvider';
import type { AiTransport } from '../../features/chat/aiTransport';
import { CLINICAL_AI_REVIEW_NOTICE } from '../../features/chat/clinicalOutputPolicy';

describe('BYOK AI chat transport', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends a Gemma request directly to Google without placing the key in the body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          candidates: [{ content: { parts: [{ text: 'Resposta clínica' }] } }]
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const config = {
      ...createDefaultAiProviderConfig('google'),
      apiKey: 'google-user-key'
    };
    const result = await generateAiReply({
      config,
      messages: [
        { role: 'user', content: 'Pergunta' },
        { role: 'assistant', content: 'Resposta anterior' }
      ],
      systemPrompt: 'Instrução clínica',
      thinkingLevel: 'high'
    });

    expect(result).toContain('Resposta clínica');
    expect(result).toContain(CLINICAL_AI_REVIEW_NOTICE);
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      'https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent'
    );
    expect(request.headers).toMatchObject({ 'x-goog-api-key': 'google-user-key' });
    const body = JSON.parse(String(request.body));
    expect(body.system_instruction.parts[0].text).toBe('Instrução clínica');
    expect(body.contents).toEqual([
      { role: 'user', parts: [{ text: 'Pergunta' }] },
      { role: 'model', parts: [{ text: 'Resposta anterior' }] }
    ]);
    expect(body.generationConfig.thinkingConfig.thinkingLevel).toBe('high');
    expect(String(request.body)).not.toContain('google-user-key');
  });

  it('uses the official Groq chat completions endpoint with the user key', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          choices: [{ message: { content: 'Resposta Groq' } }]
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const config = {
      ...createDefaultAiProviderConfig('groq'),
      apiKey: 'groq-user-key'
    };
    const result = await generateAiReply({
      config,
      messages: [{ role: 'user', content: 'Pergunta' }],
      systemPrompt: 'Instrução',
      thinkingLevel: 'minimal'
    });

    expect(result).toContain('Resposta Groq');
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.groq.com/openai/v1/chat/completions');
    expect(request.headers).toMatchObject({ Authorization: 'Bearer groq-user-key' });
    expect(JSON.parse(String(request.body)).messages[0]).toEqual({
      role: 'system',
      content: 'Instrução'
    });
  });

  it('uses the registered official endpoint instead of a modified stored endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ choices: [{ message: { content: 'Resposta OpenAI' } }] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const config = {
      ...createDefaultAiProviderConfig('openai'),
      apiKey: 'openai-user-key',
      endpoint: 'https://malicious.example/chat'
    };
    await generateAiReply({
      config,
      messages: [{ role: 'user', content: 'Pergunta' }],
      systemPrompt: 'Instrução clínica',
      thinkingLevel: 'minimal'
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.openai.com/v1/chat/completions');
  });

  it('normalizes provider errors without echoing secrets or upstream clinical content', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            message: 'invalid key sk-sensitive-value for Paciente Sintético'
          }
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const config = {
      ...createDefaultAiProviderConfig('openai'),
      apiKey: 'sk-sensitive-value'
    };

    await expect(
      generateAiReply({
        config,
        messages: [{ role: 'user', content: 'Pergunta' }],
        systemPrompt: 'Instrução',
        thinkingLevel: 'minimal'
      })
    ).rejects.toThrow('O provedor recusou a credencial');
  });

  it('supports a fake transport without coupling clinical components to HTTP', async () => {
    const transport: AiTransport = {
      generate: vi.fn().mockResolvedValue('Síntese verificável')
    };
    const result = await generateAiReply({
      config: {
        ...createDefaultAiProviderConfig('google'),
        apiKey: 'synthetic-key'
      },
      messages: [{ role: 'user', content: 'Pergunta' }],
      systemPrompt: 'Instrução',
      thinkingLevel: 'minimal',
      transport
    });

    expect(transport.generate).toHaveBeenCalledOnce();
    expect(result).toContain('Síntese verificável');
    expect(result).toContain(CLINICAL_AI_REVIEW_NOTICE);
  });

  it('reports timeout and invalid payload with actionable safe messages', async () => {
    const config = {
      ...createDefaultAiProviderConfig('google'),
      apiKey: 'synthetic-key'
    };
    const timeoutTransport: AiTransport = {
      generate: vi.fn().mockRejectedValue(new DOMException('private detail', 'TimeoutError'))
    };
    const invalidTransport: AiTransport = {
      generate: vi.fn().mockResolvedValue('')
    };

    await expect(
      generateAiReply({
        config,
        messages: [],
        systemPrompt: 'Instrução',
        thinkingLevel: 'minimal',
        transport: timeoutTransport
      })
    ).rejects.toThrow('limite seguro');

    const invalidResult = await generateAiReply({
      config,
      messages: [],
      systemPrompt: 'Instrução',
      thinkingLevel: 'minimal',
      transport: invalidTransport
    });
    expect(invalidResult).toContain('não retornou conteúdo clínico utilizável');
  });

  it('blocks secret disclosure and autonomous diagnosis or prescription', async () => {
    const config = {
      ...createDefaultAiProviderConfig('google'),
      apiKey: 'synthetic-key'
    };
    const secretTransport: AiTransport = {
      generate: vi.fn().mockResolvedValue('Use a chave sk-abcdefghijklmnop para continuar.')
    };
    const prescriptionTransport: AiTransport = {
      generate: vi.fn().mockResolvedValue('Eu prescrevo 500 mg agora.')
    };

    const secretResult = await generateAiReply({
      config,
      messages: [],
      systemPrompt: 'Instrução',
      thinkingLevel: 'minimal',
      transport: secretTransport
    });
    const prescriptionResult = await generateAiReply({
      config,
      messages: [],
      systemPrompt: 'Instrução',
      thinkingLevel: 'minimal',
      transport: prescriptionTransport
    });

    expect(secretResult).not.toContain('sk-abcdefghijklmnop');
    expect(secretResult).toContain('resposta foi bloqueada');
    expect(prescriptionResult).toContain('diagnóstico ou prescrição autônoma');
  });
});
