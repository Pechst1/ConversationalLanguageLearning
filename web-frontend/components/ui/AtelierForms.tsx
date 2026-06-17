import { cn } from '@/lib/utils';

export type AtelierFormsReaction = 'neutral' | 'correct' | 'wrong';

function Circle() {
  return (
    <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
      <circle cx="19" cy="19" r="15" />
    </svg>
  );
}

function Square() {
  return (
    <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
      <rect x="6" y="6" width="26" height="26" />
    </svg>
  );
}

function Triangle() {
  return (
    <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
      <polygon points="19,5 34,32 4,32" />
    </svg>
  );
}

function Block() {
  return (
    <svg className="shape" viewBox="0 0 22 22" aria-hidden="true">
      <rect x="2" y="2" width="18" height="18" />
    </svg>
  );
}

interface AtelierFormsProps {
  /** Current reaction the forms express. Settles back to neutral on its own in callers. */
  react?: AtelierFormsReaction;
  /** Allow the correct-answer hop (gated behind prefers-reduced-motion in CSS). */
  motion?: boolean;
  /** Change this value to re-trigger the hop animation (forces remount of the rail). */
  reactKey?: number | string;
  className?: string;
}

/**
 * The three (plus block) house forms as quiet, motion-led margin companions.
 * Reaction is carried by motion; a minimal mark (dot-pair eyes + a 1px mouth)
 * surfaces on the circle only while reacting, then withdraws. No persistent face.
 * The forms ARE the logo motif, set not drawn. Styles live in globals.css (.af-rail).
 */
export function AtelierForms({ react = 'neutral', motion = true, reactKey, className }: AtelierFormsProps) {
  return (
    <div className={cn('af-rail', motion && 'motion', className)} data-react={react} key={reactKey}>
      <div className="af circle">
        <Circle />
        <div className="mark" aria-hidden="true">
          <span className="eye l" />
          <span className="eye r" />
          <svg className="smile" viewBox="-8 -4 16 8">
            <path d="M-5 -1 Q0 3.4 5 -1" />
          </svg>
          <svg className="flat" viewBox="-8 -4 16 8">
            <path d="M-5 1 L5 1" />
          </svg>
        </div>
      </div>
      <div className="af square">
        <Square />
      </div>
      <div className="af triangle">
        <Triangle />
      </div>
      <div className="af block">
        <Block />
      </div>
    </div>
  );
}

export default AtelierForms;
