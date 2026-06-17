import React from 'react';
import { Check, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface FeedbackCorrectionItem {
  title: string;
  explanation?: string;
  repair?: string;
}

export interface FeedbackSheetProps extends React.HTMLAttributes<HTMLDivElement> {
  status: 'correct' | 'wrong';
  title: string;
  explanation?: string;
  repair?: string;
  rule?: string;
  correctionItems?: FeedbackCorrectionItem[];
  onTryAgain?: () => void;
  onNext?: () => void;
  onReport?: () => void;
}

export function FeedbackSheet({
  status,
  title,
  explanation,
  repair,
  rule,
  correctionItems,
  onTryAgain,
  onNext,
  onReport,
  className,
  ...props
}: FeedbackSheetProps) {
  const hasCorrectionItems = !!correctionItems?.length;

  return (
    <aside className={cn('atelier-feedback-sheet', status, className)} {...props}>
      <div className="feedback-mark" aria-hidden="true">
        {status === 'correct' ? <Check size={18} /> : <RotateCcw size={18} />}
      </div>
      <div className="feedback-copy">
        <h3>{title}</h3>
        {explanation && <p>{explanation}</p>}
        {hasCorrectionItems ? (
          <div className="feedback-corrections">
            {correctionItems.map((item, index) => (
              <section key={`${item.title}-${index}`}>
                <b>{item.title}</b>
                {item.explanation && <p>{item.explanation}</p>}
                {item.repair && <p>{item.repair}</p>}
              </section>
            ))}
          </div>
        ) : (
          repair && <p>{repair}</p>
        )}
        {rule && <small>{rule}</small>}
      </div>
      <div className="feedback-actions">
        {onReport && (
          <button type="button" className="subtle" onClick={onReport}>Report</button>
        )}
        {status === 'wrong' && onTryAgain && (
          <button type="button" onClick={onTryAgain}>Try again</button>
        )}
        {onNext && (
          <button type="button" className="primary" onClick={onNext}>
            {status === 'correct' ? 'Next' : 'Got it, next'}
          </button>
        )}
      </div>
    </aside>
  );
}
