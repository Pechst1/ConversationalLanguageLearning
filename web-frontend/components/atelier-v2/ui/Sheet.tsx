/**
 * Bottom sheet and dialog (WP-01).
 *
 * The design gives every sheet one handle (40×5, `#d8cdb6`), one scrim
 * (`rgba(20,17,13,.35)`), a 28px top radius, one title scale and one
 * safe-area rhythm. That is a single component, not a per-screen treatment.
 *
 * What the artboard cannot show, and what most of this file is:
 *
 *   * focus moves into the sheet on open and returns to the trigger on close;
 *   * Tab and Shift+Tab cycle inside the sheet and cannot escape it;
 *   * Escape closes it, from anywhere inside;
 *   * the page behind does not scroll while it is open;
 *   * it is announced as a dialog, with its own title as the accessible name.
 */

import React, { useCallback, useEffect, useId, useRef } from 'react';

import { useAtelierCopy } from './AtelierV2Root';
import { CrossIcon } from './Shapes';
import { IconAction } from './Action';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Trap focus inside `ref`, restore it on unmount, and close on Escape.
 *
 * Focus is restored to whatever was focused *before* the overlay opened, which
 * is nearly always the control that opened it — so a keyboard learner is put
 * back exactly where they were rather than at the top of the document.
 */
function useOverlayFocus(
  ref: React.RefObject<HTMLElement>,
  open: boolean,
  onClose: () => void,
) {
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open || typeof document === 'undefined') return undefined;

    restoreRef.current = document.activeElement as HTMLElement | null;

    const node = ref.current;
    const first = node?.querySelector<HTMLElement>(FOCUSABLE);
    // Fall back to the container itself (it carries tabIndex={-1}) so focus is
    // never left behind on the page underneath, even for a sheet of pure text.
    (first ?? node)?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !node) return;

      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (element) => element.offsetParent !== null || element === node,
      );
      if (items.length === 0) {
        event.preventDefault();
        node.focus();
        return;
      }
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === firstItem || active === node)) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && active === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      restoreRef.current?.focus?.();
    };
  }, [open, onClose, ref]);
}

export type BottomSheetProps = {
  open: boolean;
  /** The sheet's accessible name. Rendered as the Garamond-italic headline. */
  title: string;
  /** Small label above the title. */
  eyebrow?: React.ReactNode;
  onClose: () => void;
  /** Hide the close control for a sheet that must be answered. Escape still works. */
  dismissible?: boolean;
  children: React.ReactNode;
};

export function BottomSheet({
  open,
  title,
  eyebrow,
  onClose,
  dismissible = true,
  children,
}: BottomSheetProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const copy = useAtelierCopy();
  const close = useCallback(() => onClose(), [onClose]);
  useOverlayFocus(ref, open, close);

  if (!open) return null;

  return (
    <div className="av2-sheet-layer">
      <button type="button" className="av2-sheet__scrim" aria-label={copy.close} onClick={close} />
      <div
        ref={ref}
        className="av2-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="av2-sheet__handle" aria-hidden="true" />
        <div className="av2-sheet__head">
          <div style={{ minWidth: 0 }}>
            {eyebrow && <p className="av2-label">{eyebrow}</p>}
            <h2 id={titleId} className="av2-headline">
              {title}
            </h2>
          </div>
          {dismissible && (
            <IconAction label={copy.close} onClick={close}>
              <CrossIcon size={16} />
            </IconAction>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

export type DialogProps = {
  open: boolean;
  title: string;
  /** The question. Kept short: a dialog interrupts, so it must be worth it. */
  body?: React.ReactNode;
  onClose: () => void;
  /** Actions, in reading order. Exactly one should be the primary. */
  actions: React.ReactNode;
};

/**
 * The same overlay, centred, for a decision that must be answered before the
 * learner can go on. Uses the identical focus, Escape and scrim behaviour so
 * there is one modal contract in the app rather than two.
 */
export function Dialog({ open, title, body, onClose, actions }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const bodyId = useId();
  const close = useCallback(() => onClose(), [onClose]);
  useOverlayFocus(ref, open, close);
  const copy = useAtelierCopy();

  if (!open) return null;

  return (
    <div className="av2-sheet-layer av2-dialog-layer">
      <button type="button" className="av2-sheet__scrim" aria-label={copy.close} onClick={close} />
      <div
        ref={ref}
        className="av2-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={body ? bodyId : undefined}
        tabIndex={-1}
      >
        <h2 id={titleId} className="av2-headline">
          {title}
        </h2>
        {body && (
          <p id={bodyId} className="av2-body av2-body--lg" style={{ marginTop: 8 }}>
            {body}
          </p>
        )}
        <div className="av2-dialog__actions">{actions}</div>
      </div>
    </div>
  );
}
