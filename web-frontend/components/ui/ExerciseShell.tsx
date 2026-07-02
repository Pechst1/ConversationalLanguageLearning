import React from 'react';
import { cn } from '@/lib/utils';

export interface ExerciseShellProps extends React.HTMLAttributes<HTMLElement> {
  eyebrow?: string;
  title?: string;
  action?: React.ReactNode;
}

export function ExerciseShell({ eyebrow, title, action, className, children, ...props }: ExerciseShellProps) {
  return (
    <section className={cn('atelier-exercise-shell', className)} {...props}>
      {(eyebrow || title || action) && (
        <header>
          <div>
            {eyebrow && <span>{eyebrow}</span>}
            {title && <h2>{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className="atelier-exercise-shell-body">{children}</div>
    </section>
  );
}
