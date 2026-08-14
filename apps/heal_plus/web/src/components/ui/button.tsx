import { Loader2 } from 'lucide-react';
import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'teal' | 'outline';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: React.ReactNode;
  isLoading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-heal-blue text-slate-950 shadow-blue hover:bg-heal-blueDark hover:shadow-soft active:scale-[0.98] focus-visible:ring-heal-blue',
  secondary:
    'bg-white text-heal-ink border border-heal-line hover:bg-slate-50 hover:border-heal-blue/40 dark:bg-zinc-900 dark:text-white dark:border-zinc-700 dark:hover:bg-zinc-800 active:scale-[0.98]',
  danger:
    'bg-red-700 text-white hover:bg-red-800 shadow-xs active:scale-[0.98] focus-visible:ring-heal-danger',
  ghost:
    'bg-transparent text-heal-muted hover:text-heal-ink hover:bg-slate-100 dark:hover:text-white dark:hover:bg-zinc-800',
  teal:
    'bg-emerald-700 text-white hover:bg-emerald-800 shadow-sm active:scale-[0.98] focus-visible:ring-heal-teal',
  outline:
    'bg-transparent text-on-surface border border-outline-variant/30 hover:bg-surface-container hover:border-primary/30 dark:text-white dark:border-white/10 dark:hover:bg-white/10',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-lg',
  md: 'h-10 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-xl',
};

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  isLoading,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={isLoading || undefined}
      className={`
        inline-flex items-center justify-center font-semibold
        motion-safe:transition-all motion-safe:duration-150 motion-safe:ease-out
        disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${className}
      `}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />
      ) : icon ? (
        <span className="shrink-0 flex items-center">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
