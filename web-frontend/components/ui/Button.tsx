import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-none border border-[var(--app-ink)] text-xs font-medium uppercase tracking-[0.08em] ring-offset-background transition-[background,color,border-color,transform,box-shadow] duration-[var(--dur-fast)] ease-[var(--ease-standard)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-ink)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-[var(--accent-action)] text-white hover:bg-[var(--app-ink)] hover:border-[var(--app-ink)]',
        press: 'bg-[var(--accent-action)] text-white shadow-[var(--shadow-do)] hover:-translate-x-0.5 hover:-translate-y-0.5',
        destructive: 'bg-[var(--accent-alert)] text-white border-[var(--accent-alert)] hover:bg-[var(--app-ink)] hover:border-[var(--app-ink)]',
        outline: 'bg-[var(--app-sheet)] text-[var(--app-ink)] hover:bg-[var(--app-paper-2)]',
        secondary: 'bg-[var(--app-yellow)] text-[var(--app-ink)] border-[var(--app-yellow)] hover:bg-[var(--app-paper-2)] hover:border-[var(--app-ink)]',
        ghost: 'border-transparent bg-transparent text-[var(--app-ink)] hover:bg-[var(--app-paper-2)]',
        link: 'border-transparent bg-transparent p-0 text-[var(--app-blue)] underline-offset-4 hover:underline',
        success: 'bg-[var(--app-blue)] text-white border-[var(--app-blue)] hover:bg-[var(--app-ink)] hover:border-[var(--app-ink)]',
      },
      size: {
        default: 'h-11 px-5 py-3',
        sm: 'h-10 rounded-none px-4',
        lg: 'h-[52px] rounded-none px-8',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
  VariantProps<typeof buttonVariants> {
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, leftIcon, rightIcon, children, disabled, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {!loading && leftIcon && <span className="mr-2">{leftIcon}</span>}
        {children}
        {!loading && rightIcon && <span className="ml-2">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button, buttonVariants };
