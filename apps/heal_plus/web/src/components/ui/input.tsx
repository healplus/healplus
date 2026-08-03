import React, { forwardRef } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  endAdornment?: React.ReactNode;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, endAdornment, helperText, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);
    const errorId = inputId ? `${inputId}-error` : undefined;
    const helperId = inputId ? `${inputId}-helper` : undefined;

    return (
      <div className={className}>
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-semibold text-heal-ink dark:text-white mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-heal-muted">
              {icon}
            </div>
          )}
          <input
            aria-describedby={error ? errorId : helperText ? helperId : props['aria-describedby']}
            aria-invalid={Boolean(error)}
            ref={ref}
            id={inputId}
            className={`
              block w-full rounded-xl border bg-white
              text-sm text-heal-ink placeholder:text-slate-400
              motion-safe:transition-colors motion-safe:duration-150
              focus:outline-none focus:ring-2 focus:ring-heal-blue/20 focus:border-heal-blue
              disabled:opacity-50 disabled:bg-slate-100 disabled:cursor-not-allowed
              dark:bg-zinc-900 dark:text-white dark:border-zinc-700
              dark:placeholder:text-zinc-500 dark:focus:ring-heal-blue/30 dark:focus:border-heal-blue
              ${icon ? 'pl-10' : 'pl-3.5'}
              ${error ? 'border-heal-danger focus:ring-heal-danger/20 focus:border-heal-danger' : 'border-heal-line'}
              h-11 ${endAdornment ? 'pr-11' : 'pr-3.5'}
            `}
            {...props}
          />
          {endAdornment ? (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-heal-muted">
              {endAdornment}
            </div>
          ) : null}
        </div>
        {error && (
          <p id={errorId} role="alert" className="mt-1.5 text-xs font-medium text-heal-danger">{error}</p>
        )}
        {helperText && !error && (
          <p id={helperId} className="mt-1.5 text-xs text-heal-muted">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
