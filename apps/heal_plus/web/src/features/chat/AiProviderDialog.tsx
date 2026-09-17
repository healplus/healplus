import { ExternalLink, Eye, EyeOff, KeyRound, ShieldCheck, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { Modal } from '../../components/ui/Modal';
import { AiProviderMark } from './AiProviderMark';
import {
  AI_PROVIDERS,
  createDefaultAiProviderConfig,
  getAiProviderDefinition,
  validateAiProviderConfig,
  type AiProviderConfig,
  type AiProviderId
} from './aiProvider';

interface AiProviderDialogProps {
  config: AiProviderConfig | null;
  onClose: () => void;
  onRemove: () => void;
  onSave: (config: AiProviderConfig) => void;
  open: boolean;
}

export function AiProviderDialog({
  config,
  onClose,
  onRemove,
  onSave,
  open
}: AiProviderDialogProps) {
  const [draft, setDraft] = useState<AiProviderConfig>(() => config ?? createDefaultAiProviderConfig());
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const definition = useMemo(() => getAiProviderDefinition(draft.provider), [draft.provider]);

  useEffect(() => {
    if (!open) return;
    setDraft(config ?? createDefaultAiProviderConfig());
    setVisible(false);
    setError(null);
  }, [config, open]);

  function changeProvider(provider: AiProviderId) {
    setDraft(createDefaultAiProviderConfig(provider));
    setError(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = {
      ...draft,
      apiKey: draft.apiKey.trim(),
      endpoint: draft.endpoint.trim(),
      model: draft.model.trim()
    };
    const validationError = validateAiProviderConfig(next);
    if (validationError) {
      setError(validationError);
      return;
    }
    onSave(next);
  }

  return (
    <Modal open={open} onClose={onClose} title="Conectar uma IA" size="md">
      <form className="space-y-5" onSubmit={submit}>
        <div className="flex items-start gap-3 rounded-2xl bg-heal-softBlue/70 p-4 dark:bg-blue-950/20">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-heal-blue" />
          <div>
            <p className="text-sm font-bold text-heal-ink dark:text-white">Sua chave fica nesta sessão</p>
            <p className="mt-1 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
              O Redisus envia a chave somente para a IA escolhida. Ela não é salva na conta nem compartilhada entre usuários.
            </p>
          </div>
        </div>

        <fieldset>
          <legend className="mb-2 block text-sm font-semibold text-heal-ink dark:text-white">Escolha o provedor</legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {AI_PROVIDERS.map(provider => {
              const selected = provider.id === draft.provider;
              return (
                <button
                  aria-pressed={selected}
                  className={`flex min-h-[76px] items-center gap-3 rounded-2xl border p-3 text-left transition-colors ${
                    selected
                      ? 'border-heal-blue bg-heal-softBlue/70 ring-2 ring-heal-blue/10 dark:bg-blue-950/25'
                      : 'border-heal-line bg-white hover:border-heal-blue/35 hover:bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800'
                  }`}
                  key={provider.id}
                  onClick={() => changeProvider(provider.id)}
                  type="button"
                >
                  <AiProviderMark provider={provider.id} />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-extrabold text-heal-ink dark:text-white">{provider.label}</span>
                    <span className="mt-0.5 block text-[11px] leading-snug text-heal-muted dark:text-zinc-400">{provider.description}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          {definition.models.length > 0 ? (
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-heal-ink dark:text-white">Modelo</span>
              <select
                className="h-11 w-full rounded-xl border border-heal-line bg-white px-3.5 text-sm text-heal-ink outline-none focus:border-heal-blue focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                onChange={event => setDraft(current => ({ ...current, model: event.target.value }))}
                value={draft.model}
              >
                {definition.models.map(model => (
                  <option key={model.id} value={model.id}>{model.label}</option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-sm font-semibold text-heal-ink dark:text-white">ID do modelo</span>
              <input
                className="h-11 w-full rounded-xl border border-heal-line bg-white px-3.5 text-sm text-heal-ink outline-none focus:border-heal-blue focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                onChange={event => setDraft(current => ({ ...current, model: event.target.value }))}
                placeholder={draft.provider === 'openrouter' ? 'ex.: fabricante/modelo' : 'ex.: meu-modelo'}
                value={draft.model}
              />
            </label>
          )}

          {definition.models.length > 0 ? (
            <div className="hidden sm:block">
              <span className="mb-1.5 block text-sm font-semibold text-heal-ink dark:text-white">Conexão</span>
              <div className="flex h-11 items-center gap-2 rounded-xl bg-heal-canvas px-3 text-xs font-semibold text-heal-muted dark:bg-zinc-900 dark:text-zinc-400">
                <AiProviderMark provider={draft.provider} size="sm" />
                API oficial
              </div>
            </div>
          ) : null}
        </div>

        {draft.provider === 'custom' ? (
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-heal-ink dark:text-white">Endpoint de chat completions</span>
            <input
              className="h-11 w-full rounded-xl border border-heal-line bg-white px-3.5 text-sm text-heal-ink outline-none focus:border-heal-blue focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
              onChange={event => setDraft(current => ({ ...current, endpoint: event.target.value }))}
              placeholder="https://provedor.example/v1/chat/completions"
              type="url"
              value={draft.endpoint}
            />
            <p className="mt-1.5 text-xs text-heal-muted dark:text-zinc-500">
              O endpoint receberá as mensagens e, quando autorizado, o contexto clínico.
            </p>
          </label>
        ) : null}

        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold text-heal-ink dark:text-white">Chave de API</span>
          <span className="flex items-center rounded-xl border border-heal-line bg-white pr-2 focus-within:border-heal-blue focus-within:ring-2 focus-within:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900">
            <KeyRound className="ml-3.5 h-4 w-4 shrink-0 text-heal-muted" />
            <input
              autoComplete="off"
              className="h-11 min-w-0 flex-1 border-0 bg-transparent px-3 text-sm text-heal-ink outline-none dark:text-white"
              onChange={event => setDraft(current => ({ ...current, apiKey: event.target.value }))}
              placeholder={`Cole sua chave de ${definition.label}`}
              type={visible ? 'text' : 'password'}
              value={draft.apiKey}
            />
            <button
              aria-label={visible ? 'Ocultar chave' : 'Mostrar chave'}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={() => setVisible(current => !current)}
              type="button"
            >
              {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </span>
        </label>

        {definition.apiKeyUrl ? (
          <a
            className="inline-flex items-center gap-1.5 text-xs font-bold text-heal-blue hover:underline"
            href={definition.apiKeyUrl}
            rel="noreferrer"
            target="_blank"
          >
            Criar uma chave em {definition.label}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}

        {error ? (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 dark:bg-red-950/30 dark:text-red-300" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-heal-line pt-4 dark:border-zinc-800">
          <div>
            {config ? (
              <button
                className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                onClick={onRemove}
                type="button"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remover chave
              </button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <button
              className="rounded-xl px-4 py-2 text-sm font-bold text-heal-muted hover:bg-heal-surfaceHover hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
              onClick={onClose}
              type="button"
            >
              Agora não
            </button>
            <button className="rounded-xl bg-heal-blue px-4 py-2 text-sm font-bold text-slate-950 shadow-sm hover:bg-heal-blueDark" type="submit">
              Salvar e usar
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
