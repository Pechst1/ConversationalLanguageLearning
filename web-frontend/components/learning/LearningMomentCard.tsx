import React from 'react';
import type { LearningMoment } from '@/hooks/useLearningSession';
import GrammarMomentCard from './GrammarMomentCard';
import VocabMomentCard from './VocabMomentCard';

type SubmitPayload = {
  answerText?: string;
  selectedChoice?: string;
};

type Props = {
  moment?: LearningMoment | null;
  loading?: boolean;
  onSubmit: (payload: SubmitPayload) => Promise<void> | void;
  onSkip: () => Promise<void> | void;
};

export default function LearningMomentCard({
  moment,
  loading = false,
  onSubmit,
  onSkip,
}: Props) {
  if (!moment) {
    return null;
  }

  if (moment.sourceType === 'vocabulary') {
    return (
      <VocabMomentCard
        moment={moment}
        loading={loading}
        onSubmit={onSubmit}
        onSkip={onSkip}
      />
    );
  }

  return (
    <GrammarMomentCard
      moment={moment}
      loading={loading}
      onSubmit={onSubmit}
      onSkip={onSkip}
    />
  );
}
