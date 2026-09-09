/**
 * The pilot feedback control.
 *
 * WP-20 D-9: this used to be the last off-system element in the product — a
 * 36 × 36 neo-brutal box on paper, below the 44 px target floor, drawn on every
 * authenticated screen including the immersive reader, where it sat directly on
 * top of the reader's own action bar. It now speaks the av2 system, meets the
 * tap floor, and stands down while an immersive surface owns the screen.
 */

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import {
  Action,
  AtelierV2Root,
  Chip,
  CrossIcon,
  IconAction,
  SendIcon,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import { useImmersiveSurface } from '@/lib/immersive-surface';
import { resolveProductSection, resolveProductTitle } from '@/lib/product-shell';
import apiService, { type FeedbackCategory } from '@/services/api';

const FEEDBACK_OPTIONS: Array<{ value: FeedbackCategory; label: string }> = [
  { value: 'bug', label: 'Bug' },
  { value: 'broken_link', label: 'Broken link' },
  { value: 'content', label: 'Text/content' },
  { value: 'layout', label: 'Layout' },
  { value: 'slow_loading', label: 'Slow/loading' },
  { value: 'suggestion', label: 'Suggestion' },
  { value: 'other', label: 'Other' },
];

export default function FeedbackWidget() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory | null>(null);
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const immersive = useImmersiveSurface();
  // How far the bottom navigation intrudes into the viewport right now (WP-20 D-17).
  const [navIntrusion, setNavIntrusion] = useState(0);

  const productSection = useMemo(() => resolveProductSection(router.pathname), [router.pathname]);
  const screen = useMemo(
    () => resolveProductTitle(productSection, router.pathname),
    [productSection, router.pathname],
  );

  useEffect(() => {
    setOpen(false);
  }, [router.asPath]);

  // A reader that has taken over the screen draws its own action bar at the
  // bottom right; a floating control there is one more thing over it.
  useEffect(() => {
    if (immersive) setOpen(false);
  }, [immersive]);

  /**
   * Sit above the bottom navigation, wherever it actually is.
   *
   * The tab bar is `fixed` on some routes and `embedded` — in normal flow at the end
   * of the page — on others, Home included. A constant offset therefore cannot be
   * right for both: anchored to `--phone-bottom-nav-space` this control sat on top of
   * the «Cahier» tab on a real device (WP-20 D-17). Measuring the bar's on-screen top
   * edge is correct in every case: a fixed bar always intrudes by its own height, an
   * embedded one only while it is scrolled into view, and none at all when there is
   * no bar.
   */
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    let frame = 0;

    const measure = () => {
      frame = 0;
      const nav = document.querySelector('.phone-product-nav');
      if (!nav) {
        setNavIntrusion(0);
        return;
      }
      const { top } = nav.getBoundingClientRect();
      setNavIntrusion(Math.max(0, Math.round(window.innerHeight - top)));
    };

    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(measure);
    };

    measure();
    // Capture phase, on the document: the shell scrolls an inner element on some
    // routes, and a scroll event does not bubble, so a listener on `window` never
    // hears it and the offset stays frozen at whatever the first paint measured.
    document.addEventListener('scroll', schedule, { capture: true, passive: true });
    window.addEventListener('resize', schedule);
    // The bar's own height changes with the text-size setting and the keyboard.
    const observer =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(schedule);
    const nav = document.querySelector('.phone-product-nav');
    if (observer && nav) observer.observe(nav);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      document.removeEventListener('scroll', schedule, { capture: true });
      window.removeEventListener('resize', schedule);
      observer?.disconnect();
    };
  }, [router.asPath, immersive]);

  async function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!category || submitting) return;

    const clientTimestamp = new Date().toISOString();
    const viewport = typeof window === 'undefined'
      ? {}
      : {
          width: window.innerWidth,
          height: window.innerHeight,
          devicePixelRatio: window.devicePixelRatio,
        };

    setSubmitting(true);
    try {
      await apiService.submitFeedbackReport({
        category,
        message: message.trim() || undefined,
        route: router.pathname || router.asPath || '/',
        url: typeof window === 'undefined' ? router.asPath : window.location.href,
        screen,
        viewport,
        user_agent: typeof navigator === 'undefined' ? undefined : navigator.userAgent,
        context_payload: {
          pathname: router.pathname,
          asPath: router.asPath,
          query: router.query,
          productSection,
          clientTimestamp,
        },
      });
      toast.success('Feedback sent.');
      setCategory(null);
      setMessage('');
      setOpen(false);
    } catch (error) {
      console.error(error);
      toast.error('Could not send feedback.');
    } finally {
      setSubmitting(false);
    }
  }

  if (immersive) return null;

  return (
    <AtelierV2Root
      as="div"
      className="fb-scope"
      style={{ ['--fb-nav-intrusion' as string]: `${navIntrusion}px` }}
    >
      {open && (
        <form onSubmit={submitFeedback} role="dialog" aria-label="Send feedback" className="fb-panel">
          <div className="fb-panel__head">
            <div>
              <p className="av2-label">Feedback</p>
              <p className="fb-panel__title">What is off?</p>
            </div>
            <IconAction label="Close feedback" onClick={() => setOpen(false)}>
              <CrossIcon size={16} />
            </IconAction>
          </div>

          <div className="fb-options" role="group" aria-label="What is off?">
            {FEEDBACK_OPTIONS.map((option) => (
              <Chip
                key={option.value}
                tone={category === option.value ? 'story' : 'plain'}
                aria-pressed={category === option.value}
                onClick={() => setCategory(option.value)}
              >
                {option.label}
              </Chip>
            ))}
          </div>

          {textAnswerField({
            label: 'Note',
            value: message,
            rows: 3,
            placeholder: 'Optional detail',
            onChange: (next) => setMessage(next.slice(0, 1000)),
          })}

          <div className="fb-panel__foot">
            <span className="av2-label">{screen}</span>
            <Action
              tone="primary"
              type="submit"
              disabled={!category}
              pending={submitting}
              pendingLabel="Sending"
              icon={<SendIcon size={15} />}
            >
              Send
            </Action>
          </div>
        </form>
      )}

      <div className="fb-launcher">
        <IconAction
          label="Send feedback"
          pressable
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <SendIcon size={17} />
        </IconAction>
      </div>

      <style jsx global>{`
        .av2.fb-scope {
          position: fixed;
          right: 12px;
          /* measured from the navigation actually on screen — see D-17 above */
          bottom: calc(
            var(--fb-nav-intrusion, 0px) + 8px + env(safe-area-inset-bottom, 0px)
          );
          z-index: 80;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 8px;
        }
        .av2 .fb-launcher .av2-icon-btn {
          background: var(--av2-paper);
          box-shadow: 0 var(--av2-press-md) 0 var(--av2-line-2);
        }
        .av2 .fb-panel {
          position: fixed;
          right: 12px;
          left: 12px;
          bottom: calc(
            var(--fb-nav-intrusion, 0px) + 64px + env(safe-area-inset-bottom, 0px)
          );
          z-index: 81;
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: calc(100vh - 140px);
          overflow-y: auto;
          padding: 14px;
          border-radius: var(--av2-r-card);
          background: var(--av2-paper);
          box-shadow: 0 10px 30px rgba(20, 17, 13, 0.18);
        }
        .av2 .fb-panel__head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
        }
        .av2 .fb-panel__title {
          margin: 3px 0 0;
          font-size: var(--av2-t-body-lg);
          font-weight: 700;
        }
        .av2 .fb-options {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .av2 .fb-panel__foot {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        @media (min-width: 640px) {
          .av2.fb-scope {
            right: 20px;
            bottom: 20px;
          }
          .av2 .fb-panel {
            left: auto;
            right: 20px;
            bottom: 76px;
            width: 320px;
          }
        }
      `}</style>
    </AtelierV2Root>
  );
}
