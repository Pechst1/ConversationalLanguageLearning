import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-none text-sm font-bold ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border-2 border-brutal-black shadow-brutal hover:shadow-none hover:translate-x-[4px] hover:translate-y-[4px] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px_#000000]',
  {
    variants: {
      variant: {
        default: 'bg-bauhaus-blue text-white hover:bg-bauhaus-blue/90',
        destructive: 'bg-bauhaus-red text-white hover:bg-bauhaus-red/90',
        outline: 'bg-white text-brutal-black hover:bg-brutal-gray',
        secondary: 'bg-bauhaus-yellow text-brutal-black hover:bg-bauhaus-yellow/90',
        ghost: 'border-transparent shadow-none hover:bg-brutal-gray hover:shadow-none hover:translate-none',
        link: 'text-primary-600 underline-offset-4 hover:underline border-none shadow-none hover:translate-none',
        success: 'bg-green-600 text-white hover:bg-green-700',
      },
      size: {
        default: 'h-12 px-6 py-3',
        sm: 'h-10 rounded-none px-4',
        lg: 'h-14 rounded-none px-10 text-lg',
        icon: 'h-12 w-12',
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
