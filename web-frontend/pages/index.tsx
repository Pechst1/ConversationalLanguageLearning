import { getSession, useSession } from 'next-auth/react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowRight, BookOpen, Clock3, MessageCircle, Newspaper, Target } from 'lucide-react';
import EditorialMasthead from '@/components/layout/EditorialMasthead';

export default function HomePage() {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === 'authenticated') {
      router.push('/atelier');
    }
  }, [status, router]);

  if (status === 'loading') {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--app-paper)]">
        <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
          Opening Atelier
        </div>
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>Atelier · Learning Hub</title>
      </Head>
      <EditorialMasthead
        active="home"
        brandHref="/"
        trailing={(
          <>
            <Link href="/auth/signin">Sign in</Link>
            <Link className="public-start" href="/auth/signup">Start</Link>
          </>
        )}
      />
      <main className="hub-page">
        <section className="hub-top">
          <div>
            <div className="hub-kicker">Home</div>
            <h1>Learning hub</h1>
          </div>
          <div className="hub-session-status">
            <span>No learner loaded</span>
            <strong>Sign in to load today&apos;s queue.</strong>
          </div>
        </section>

        <section className="hub-grid" aria-label="Learning hub">
          <article className="hub-primary">
            <div className="hub-section-head">
              <span><Clock3 size={14} /> Next session</span>
              <small>~15 min</small>
            </div>
            <h2>Continue from the strongest signal.</h2>
            <p>Conversation first, then repair the errors that appear.</p>
            <div className="hub-actions">
              <Link className="hub-button primary" href="/auth/signin">
                Sign in <ArrowRight size={16} />
              </Link>
              <Link className="hub-button" href="/auth/signup">Create account</Link>
            </div>
          </article>

          <aside className="hub-queue" aria-label="Queue snapshot">
            <div className="hub-section-head">
              <span>Queue</span>
              <small>locked</small>
            </div>
            <QueueRow icon={<MessageCircle size={16} />} label="Conversation" value="Next prompt" />
            <QueueRow icon={<Target size={16} />} label="Repairs" value="Needs account" />
            <QueueRow icon={<BookOpen size={16} />} label="Notebook" value="Reference" />
            <QueueRow icon={<Newspaper size={16} />} label="Feuilleton" value="After practice" />
          </aside>
        </section>
      </main>
      <style jsx global>{`
        .public-start {
          color: var(--app-ink) !important;
        }
        .hub-page {
          width: min(1120px, 100%);
          margin: 0 auto;
          padding: clamp(26px, 5vw, 58px) clamp(22px, 4vw, 48px) 76px;
          color: var(--app-ink);
        }
        .hub-top {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 28px;
          border-bottom: 4px solid var(--app-ink);
          padding-bottom: 22px;
        }
        .hub-kicker,
        .hub-section-head,
        .hub-session-status span {
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .14em;
          text-transform: uppercase;
          color: var(--app-ink-2);
        }
        .hub-top h1 {
          margin: 8px 0 0;
          font-family: var(--app-serif);
          font-size: clamp(44px, 6.4vw, 88px);
          font-style: italic;
          font-weight: 600;
          line-height: .9;
          letter-spacing: 0;
        }
        .hub-session-status {
          min-width: min(360px, 100%);
          border: 1px solid var(--app-ink);
          background: var(--app-paper-2);
          padding: 16px 18px;
        }
        .hub-session-status strong {
          display: block;
          margin-top: 8px;
          font-size: 16px;
          line-height: 1.35;
        }
        .hub-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(320px, 390px);
          gap: 28px;
          margin-top: 30px;
        }
        .hub-primary,
        .hub-queue {
          border: 1px solid var(--app-ink);
          background: var(--app-sheet);
        }
        .hub-primary {
          min-height: 370px;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          padding: clamp(24px, 4vw, 40px);
          background:
            linear-gradient(90deg, rgba(20, 17, 13, .055) 1px, transparent 1px),
            linear-gradient(180deg, rgba(20, 17, 13, .055) 1px, transparent 1px),
            var(--app-sheet);
          background-size: 34px 34px;
        }
        .hub-section-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          border-bottom: 1px solid var(--app-ink);
          padding-bottom: 12px;
        }
        .hub-section-head span {
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }
        .hub-section-head small {
          font: inherit;
          color: var(--app-ink-3);
        }
        .hub-primary h2 {
          max-width: 680px;
          margin: auto 0 14px;
          font-size: clamp(34px, 4.2vw, 58px);
          line-height: .94;
          letter-spacing: 0;
        }
        .hub-primary p {
          margin: 0;
          max-width: 500px;
          color: var(--app-ink-2);
          font-size: 18px;
          line-height: 1.45;
        }
        .hub-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          margin-top: 28px;
        }
        .hub-button {
          min-height: 48px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          border: 1px solid var(--app-ink);
          padding: 0 18px;
          color: var(--app-ink);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .13em;
          text-decoration: none;
          text-transform: uppercase;
        }
        .hub-button.primary {
          background: var(--app-ink);
          color: var(--app-paper);
        }
        .hub-button:hover {
          background: var(--app-blue);
          border-color: var(--app-blue);
          color: var(--app-paper);
        }
        .hub-queue {
          display: grid;
          align-content: start;
          background: var(--app-paper-2);
        }
        .queue-row {
          display: grid;
          grid-template-columns: 28px minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
          min-height: 68px;
          border-bottom: 1px solid rgba(20, 17, 13, .32);
          padding: 0 18px;
          font-weight: 900;
        }
        .hub-queue .hub-section-head {
          padding: 17px 18px;
          background: var(--app-sheet);
        }
        .queue-row:last-child {
          border-bottom: 0;
        }
        .queue-row span:last-child {
          color: var(--app-ink-3);
          font-size: 10px;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        @media (max-width: 860px) {
          .hub-top,
          .hub-grid {
            grid-template-columns: 1fr;
            display: grid;
          }
          .hub-top {
            align-items: start;
          }
          .hub-session-status {
            min-width: 0;
          }
        }
      `}</style>
    </>
  );
}

function QueueRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="queue-row">
      {icon}
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

export async function getServerSideProps(context: any) {
  const session = await getSession(context);

  if (session) {
    return {
      redirect: {
        destination: '/atelier',
        permanent: false,
      },
    };
  }

  return {
    props: {},
  };
}
