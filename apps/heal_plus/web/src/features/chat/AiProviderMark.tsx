import { Braces } from 'lucide-react';

import type { AiProviderId } from './aiProvider';

interface AiProviderMarkProps {
  className?: string;
  provider: AiProviderId;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'h-5 w-5 rounded-md',
  md: 'h-8 w-8 rounded-lg',
  lg: 'h-14 w-14 rounded-2xl'
} as const;

export function AiProviderMark({ className = '', provider, size = 'md' }: AiProviderMarkProps) {
  const classes = `inline-grid shrink-0 place-items-center overflow-hidden ${sizeClasses[size]} ${className}`;

  if (provider === 'google') {
    return (
      <span aria-hidden="true" className={`${classes} bg-white`}>
        <img alt="" className="h-full w-full object-contain p-[8%]" src="/images/ai/gemma.png" />
      </span>
    );
  }

  if (provider === 'openai') {
    return (
      <span aria-hidden="true" className={`${classes} bg-[#101010] text-white`}>
        <svg className="h-[62%] w-[62%]" fill="none" viewBox="0 0 24 24">
          <path d="M12 3.1a4.3 4.3 0 0 1 7.4 3.7 4.3 4.3 0 0 1 .2 7.6 4.3 4.3 0 0 1-3.9 6.6 4.3 4.3 0 0 1-7.2-3.8 4.3 4.3 0 0 1-4-6.6 4.3 4.3 0 0 1 3.9-6.7A4.3 4.3 0 0 1 12 3.1Z" stroke="currentColor" strokeWidth="1.8" />
          <path d="m8.1 7.3 7.8 4.5v5.3M15.9 7.2 8.1 11.7V17M5.2 11.2l6.8 4 6.8-4" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.45" />
        </svg>
      </span>
    );
  }

  if (provider === 'groq') {
    return (
      <span aria-hidden="true" className={`${classes} bg-[#f55036] text-white`}>
        <span className="text-[0.68em] font-black tracking-[-0.08em]">GQ</span>
      </span>
    );
  }

  if (provider === 'openrouter') {
    return (
      <span aria-hidden="true" className={`${classes} bg-[#6f5cff] text-white`}>
        <svg className="h-[62%] w-[62%]" fill="none" viewBox="0 0 24 24">
          <path d="M4 8h11.5M13 4.8 16.5 8 13 11.2M20 16H8.5M11 12.8 7.5 16l3.5 3.2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </svg>
      </span>
    );
  }

  return (
    <span aria-hidden="true" className={`${classes} bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-200`}>
      <Braces className="h-[58%] w-[58%]" />
    </span>
  );
}