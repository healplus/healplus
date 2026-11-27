import { afterEach, describe, expect, it, vi } from 'vitest';

import { filterForPresentation, isPresentationMode } from '../../lib/presentationMode';

const items = [{ to: '/dashboard' }, { to: '/chat' }, { to: '/agenda' }, { to: '/analyzer' }];

describe('presentationMode', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('fica desligado por padrão', () => {
    vi.stubEnv('VITE_PRESENTATION_MODE', '');
    expect(isPresentationMode()).toBe(false);
    expect(filterForPresentation(items)).toEqual(items);
  });

  it('remove agenda e assistente quando ativado', () => {
    vi.stubEnv('VITE_PRESENTATION_MODE', 'true');
    expect(isPresentationMode()).toBe(true);
    expect(filterForPresentation(items).map(item => item.to)).toEqual(['/dashboard', '/analyzer']);
  });

  it('não altera a lista original', () => {
    const result = filterForPresentation(items, true);
    expect(result).not.toBe(items);
    expect(items).toHaveLength(4);
  });
});
