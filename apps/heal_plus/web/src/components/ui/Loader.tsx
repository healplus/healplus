import type { HTMLAttributes } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

import { cn } from '../../lib/utils';

interface LoaderProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeConfig = {
  sm: {
    container: 'size-20',
    title: 'text-sm font-medium leading-tight',
    subtitle: 'text-xs leading-relaxed',
    spacing: 'space-y-2',
    maxWidth: 'max-w-48'
  },
  md: {
    container: 'size-32',
    title: 'text-base font-medium leading-snug',
    subtitle: 'text-sm leading-relaxed',
    spacing: 'space-y-3',
    maxWidth: 'max-w-56'
  },
  lg: {
    container: 'size-40',
    title: 'text-lg font-semibold leading-tight',
    subtitle: 'text-base leading-relaxed',
    spacing: 'space-y-4',
    maxWidth: 'max-w-64'
  }
} as const;

const ringMask = (inner: number, start: number, end: number, outer: number) =>
  `radial-gradient(circle at 50% 50%, transparent ${inner}%, black ${start}%, black ${end}%, transparent ${outer}%)`;

export function Loader({
  title = 'Processando autenticação...',
  subtitle = 'Aguarde enquanto preparamos seu acesso.',
  size = 'md',
  className,
  ...props
}: LoaderProps) {
  const reduceMotion = useReducedMotion();
  const config = sizeConfig[size];

  const rings = [
    {
      background: 'conic-gradient(from 0deg, transparent 0deg, currentColor 90deg, transparent 180deg)',
      mask: ringMask(35, 37, 39, 41),
      opacity: 0.8,
      duration: 3,
      rotate: 360
    },
    {
      background: 'conic-gradient(from 0deg, transparent 0deg, currentColor 120deg, color-mix(in srgb, currentColor 50%, transparent) 240deg, transparent 360deg)',
      mask: ringMask(42, 44, 48, 50),
      opacity: 0.9,
      duration: 2.5,
      rotate: 360
    },
    {
      background: 'conic-gradient(from 180deg, transparent 0deg, color-mix(in srgb, currentColor 60%, transparent) 45deg, transparent 90deg)',
      mask: ringMask(52, 54, 56, 58),
      opacity: 0.35,
      duration: 4,
      rotate: -360
    },
    {
      background: 'conic-gradient(from 270deg, transparent 0deg, color-mix(in srgb, currentColor 40%, transparent) 20deg, transparent 40deg)',
      mask: ringMask(61, 62, 63, 64),
      opacity: 0.5,
      duration: 3.5,
      rotate: 360
    }
  ];

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={title}
      className={cn('flex flex-col items-center justify-center gap-8 p-8', className)}
      {...props}
    >
      <motion.div
        animate={reduceMotion ? undefined : { scale: [1, 1.02, 1] }}
        className={cn('relative text-heal-blue dark:text-white', config.container)}
        transition={{ duration: 4, repeat: Number.POSITIVE_INFINITY, ease: [0.4, 0, 0.6, 1] }}
      >
        {rings.map((ring, index) => (
          <motion.div
            key={ring.mask}
            aria-hidden="true"
            animate={reduceMotion ? undefined : { rotate: [0, ring.rotate] }}
            className="absolute inset-0 rounded-full"
            style={{
              background: ring.background,
              mask: ring.mask,
              WebkitMask: ring.mask,
              opacity: ring.opacity
            }}
            transition={{
              duration: ring.duration,
              repeat: Number.POSITIVE_INFINITY,
              ease: index === 0 || index === 3 ? 'linear' : [0.4, 0, 0.6, 1]
            }}
          />
        ))}
      </motion.div>

      <motion.div
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        className={cn('text-center', config.spacing, config.maxWidth)}
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        transition={{ delay: 0.4, duration: 1, ease: [0.4, 0, 0.2, 1] }}
      >
        <h1 className={cn(config.title, 'tracking-[-0.02em] text-heal-blue antialiased dark:text-white/90')}>
          <motion.span
            animate={reduceMotion ? undefined : { opacity: [0.9, 0.7, 0.9] }}
            transition={{ duration: 3, repeat: Number.POSITIVE_INFINITY, ease: [0.4, 0, 0.6, 1] }}
          >
            {title}
          </motion.span>
        </h1>
        <p className={cn(config.subtitle, 'tracking-[-0.01em] text-slate-600 antialiased dark:text-white/60')}>
          {subtitle}
        </p>
      </motion.div>
    </div>
  );
}
