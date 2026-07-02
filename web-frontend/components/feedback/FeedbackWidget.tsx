import { FormEvent, useEffect, useMemo, useState } from 'react';
import { MessageSquarePlus, Send, X } from 'lucide-react';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import apiService, { type FeedbackCategory } from '@/services/api';
import { resolveProductSection, resolveProductTitle } from '@/lib/product-shell';

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

  const productSection = useMemo(() => resolveProductSection(router.pathname), [router.pathname]);
  const screen = useMemo(
    () => resolveProductTitle(productSection, router.pathname),
    [productSection, router.pathname],
  );

  useEffect(() => {
    setOpen(false);
  }, [router.asPath]);

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

  return (
    <div className="fixed bottom-[calc(var(--phone-bottom-nav-space)+8px)] right-3 z-[80] sm:bottom-5 sm:right-5">
      {open && (
        <form
          onSubmit={submitFeedback}
          role="dialog"
          aria-label="Send feedback"
          className="fixed inset-x-3 bottom-[calc(var(--phone-bottom-nav-space)+56px)] z-[81] max-h-[calc(100vh-128px)] overflow-y-auto border border-[var(--app-ink)] bg-[var(--app-paper)] p-3 sm:inset-x-auto sm:bottom-16 sm:right-5 sm:w-80"
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
                Feedback
              </div>
              <div className="mt-1 text-sm font-black text-[var(--app-ink)]">What is off?</div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="grid h-8 w-8 place-items-center border border-[var(--app-ink)] bg-[var(--app-paper)] text-[var(--app-ink)]"
              aria-label="Close feedback"
            >
              <X size={15} strokeWidth={2.6} />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {FEEDBACK_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setCategory(option.value)}
                className={`min-h-[36px] border px-2 py-2 text-left font-mono text-[10px] font-black uppercase tracking-[0.08em] transition ${
                  category === option.value
                    ? 'border-[var(--app-ink)] bg-[var(--accent-action)] text-white'
                    : 'border-[rgba(20,17,13,0.32)] bg-[rgba(255,255,255,0.24)] text-[var(--app-ink)]'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <label className="mt-3 block">
            <span className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-[var(--app-ink-3)]">
              Note
            </span>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value.slice(0, 1000))}
              maxLength={1000}
              rows={3}
              placeholder="Optional detail"
              className="mt-1 w-full resize-none border border-[rgba(20,17,13,0.34)] bg-[rgba(255,255,255,0.32)] px-3 py-2 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-ink)]"
            />
          </label>

          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="font-mono text-[9px] font-black uppercase tracking-[0.12em] text-[var(--app-ink-3)]">
              {screen}
            </div>
            <button
              type="submit"
              disabled={!category || submitting}
              className="inline-flex min-h-[36px] items-center gap-2 border-2 border-[var(--app-ink)] bg-[var(--app-ink)] px-3 py-2 font-mono text-[10px] font-black uppercase tracking-[0.12em] text-[var(--app-paper)] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {submitting ? 'Sending' : 'Send'}
              <Send size={13} strokeWidth={2.6} />
            </button>
          </div>
        </form>
      )}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        title="Send feedback"
        className="grid h-9 w-9 place-items-center border border-[var(--app-ink)] bg-[var(--app-paper)] text-[var(--app-ink)] transition hover:bg-[var(--app-sheet)] focus:outline-none focus:ring-2 focus:ring-[var(--app-blue)] sm:h-10 sm:w-10"
        aria-label="Send feedback"
        aria-expanded={open}
      >
        <MessageSquarePlus size={17} strokeWidth={2.6} />
      </button>
    </div>
  );
}
