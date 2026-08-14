import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DotField from '../../components/ui/DotField';

const contextStub = {
  arc: vi.fn(),
  beginPath: vi.fn(),
  clearRect: vi.fn(),
  createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  fill: vi.fn(),
  fillStyle: '',
  moveTo: vi.fn(),
  setTransform: vi.fn()
};

describe('DotField', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mantém o campo estático sem iniciar animação quando o movimento é reduzido', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(query => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    }));
    vi.spyOn(window.HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      contextStub as unknown as CanvasRenderingContext2D
    );
    const requestAnimationFrameSpy = vi.spyOn(window, 'requestAnimationFrame');

    const { container } = render(<DotField />);

    expect(container.querySelector('canvas')).toHaveAttribute('data-motion', 'reduced');
    expect(contextStub.fill).toHaveBeenCalled();
    expect(requestAnimationFrameSpy).not.toHaveBeenCalled();
  });
});
