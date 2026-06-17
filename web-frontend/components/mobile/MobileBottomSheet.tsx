import React from 'react';
import { cn } from '@/lib/utils';

export interface MobileBottomSheetProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  as?: 'section' | 'aside' | 'div';
  ariaLabel?: string;
  labelledBy?: string;
  onClose: () => void;
  eyebrow?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  closeContent?: React.ReactNode;
  closeLabel?: string;
  showClose?: boolean;
  showHandle?: boolean;
  displayTitle?: boolean;
  sheetClassName?: string;
  bodyClassName?: string;
  backdropClassName?: string;
}

const MobileBottomSheet = React.forwardRef<HTMLElement, MobileBottomSheetProps>(
  (
    {
      as: Component = 'section',
      ariaLabel,
      labelledBy,
      onClose,
      eyebrow,
      title,
      description,
      action,
      closeContent = 'Close',
      closeLabel = 'Close sheet',
      showClose = true,
      showHandle = true,
      displayTitle = true,
      sheetClassName,
      bodyClassName,
      backdropClassName,
      className,
      children,
      ...props
    },
    ref
  ) => {
    const SheetComponent = Component as React.ElementType;
    return (
      <div className={cn('mobile-bottom-sheet-layer', className)} role="presentation" {...props}>
        <button className={cn('mobile-bottom-sheet-backdrop', backdropClassName)} type="button" aria-label={closeLabel} onClick={onClose} />
        <SheetComponent
          ref={ref}
          className={cn('mobile-bottom-sheet', sheetClassName)}
          role="dialog"
          aria-modal="true"
          aria-label={ariaLabel}
          aria-labelledby={labelledBy}
        >
          {showHandle && <div className="mobile-bottom-sheet-handle" aria-hidden="true" />}
          {(eyebrow || title || description || action || showClose) && (
            <header className="mobile-bottom-sheet-head">
              <div className="mobile-bottom-sheet-copy">
                {eyebrow && <span className="mobile-bottom-sheet-eyebrow">{eyebrow}</span>}
                {title && <h2 className={cn('mobile-bottom-sheet-title', displayTitle && 'display')}>{title}</h2>}
                {description && <p className="mobile-bottom-sheet-description">{description}</p>}
              </div>
              {(action || showClose) && (
                <div className="mobile-bottom-sheet-actions">
                  {action}
                  {showClose && (
                    <button type="button" className="mobile-bottom-sheet-close" aria-label={closeLabel} onClick={onClose}>
                      {closeContent}
                    </button>
                  )}
                </div>
              )}
            </header>
          )}
          <div className={cn('mobile-bottom-sheet-body', bodyClassName)}>{children}</div>
        </SheetComponent>
        <style jsx>{`
          .mobile-bottom-sheet-layer {
            --sheet-paper: var(--app-paper, var(--paper, #f1ece1));
            --sheet-surface: var(--app-sheet, var(--paper-2, #f8f3e8));
            --sheet-ink: var(--app-ink, var(--ink, #14110d));
            --sheet-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --sheet-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
            position: fixed;
            inset: 0;
            z-index: 120;
          }
          .mobile-bottom-sheet-backdrop {
            position: absolute;
            inset: 0;
            border: 0;
            background: rgba(20, 17, 13, .42);
          }
          .mobile-bottom-sheet {
            position: absolute;
            right: 0;
            bottom: 0;
            left: 0;
            max-height: min(88vh, 760px);
            overflow: auto;
            border: 1px solid var(--sheet-ink);
            border-bottom: 0;
            background: var(--sheet-paper);
            color: var(--sheet-ink);
            padding: 12px 16px calc(20px + env(safe-area-inset-bottom));
            box-shadow: 0 -18px 42px rgba(20, 17, 13, .18);
            animation: mobile-bottom-sheet-up 240ms ease-out both;
          }
          .mobile-bottom-sheet-handle {
            width: 48px;
            height: 4px;
            margin: 0 auto 16px;
            border-radius: 999px;
            background: var(--sheet-ink-3);
          }
          .mobile-bottom-sheet-head {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 16px;
            align-items: start;
            border-bottom: 1px solid var(--sheet-ink);
            padding-bottom: 14px;
          }
          .mobile-bottom-sheet-copy {
            min-width: 0;
          }
          .mobile-bottom-sheet-eyebrow {
            display: block;
            color: var(--sheet-ink-3);
            font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
            letter-spacing: .12em;
            text-transform: uppercase;
          }
          .mobile-bottom-sheet-title {
            margin: 6px 0 0;
            color: var(--sheet-ink);
            font-size: 24px;
            line-height: 1.08;
            overflow-wrap: anywhere;
          }
          .mobile-bottom-sheet-title.display {
            font-family: var(--app-serif, "EB Garamond", Garamond, "Times New Roman", serif);
            font-size: clamp(36px, 10vw, 66px);
            font-style: italic;
            font-weight: 500;
            letter-spacing: 0;
            line-height: .96;
          }
          .mobile-bottom-sheet-description {
            margin: 7px 0 0;
            color: var(--sheet-ink-2);
            font-size: 13px;
            line-height: 1.35;
          }
          .mobile-bottom-sheet-actions {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
          }
          .mobile-bottom-sheet-close {
            min-height: 44px;
            border: 1px solid var(--sheet-ink);
            background: var(--sheet-surface);
            padding: 0 14px;
            color: var(--sheet-ink);
            font: inherit;
            font-weight: 800;
          }
          .mobile-bottom-sheet-body {
            padding-top: 14px;
          }
          @keyframes mobile-bottom-sheet-up {
            from {
              opacity: 0;
              transform: translateY(24px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}</style>
      </div>
    );
  }
);

MobileBottomSheet.displayName = 'MobileBottomSheet';

export { MobileBottomSheet };
