/**
 * F-1 gallery specimens (content program 2026-10-03): the rule card v2+ and
 * the x-ray sentence, on real authored units from A1.1 to B1.1.
 *
 *   1. the intro card, closed: example, colour key, rule, pattern, one ✗/✓
 *   2. the same card inline with «More» open: why, steps, examples, traps,
 *      «Compare with» (an untitled partner is left out)
 *   3. the Cahier's unit page body: the card open + the x-ray, per unit
 *   4. a v1 card (no v2+ fields): exactly the old card, «Why?»
 *   5. unbalanced markup: drawn as plain text
 *
 * `rule-cards.fixture.json` holds verbatim copies of the cards (partners
 * titled as the server titles them) and the units' x-ray marks.
 */

import React from 'react';

import { RuleCard } from '@/components/atelier-v2/rule/RuleCard';
import { XraySentence } from '@/components/atelier-v2/rule/XraySentence';
import type { RuleCardData, XrayPayload } from '@/lib/rule-card';
import type { ControlLanguage } from '@/types/daily-journey';

import fixture from './rule-cards.fixture.json';

type SectionComponent = React.ComponentType<{ title: string; children: React.ReactNode }>;

type FixtureUnit = {
  external_id: string;
  sub_band: string;
  title_fr: string;
  rule_card: RuleCardData;
  xray: XrayPayload;
};

const UNITS = (fixture as unknown as { units: FixtureUnit[] }).units;
const unit = (id: string) => UNITS.find((item) => item.external_id === id) ?? UNITS[0];

const V1_CARD: RuleCardData = {
  speaker: 'margaux_barman',
  example: { fr: 'Une petit[e] table blanch[e].', tr: { en: 'A small white table.', de: 'Ein kleiner weißer Tisch.' } },
  rule: { en: 'The noun decides.', de: 'Das Nomen entscheidet.', fr: 'Le nom décide.' },
  contrast: { wrong: 'Une petit table.', right: 'Une petit[e] table.' },
  more: { en: 'Adjectives take the gender of their noun.', de: 'Adjektive nehmen das Geschlecht ihres Nomens an.' },
};

const BROKEN_CARD: RuleCardData = {
  example: { fr: 'Elle [est parti{e à huit heures.' },
  rule: { en: 'Unbalanced markup is drawn as plain text, never as brackets.' },
  contrast: { wrong: 'Elle est parti.', right: 'Elle est parti[e.' },
};

const noop = () => {};

export function RuleCardGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: SectionComponent;
}) {
  const etre = unit('FR2_A21_PC_ETRE');
  return (
    <>
      <Section title="F-1 · Rule card v2+ — intro, first view (A2.1 · passé composé avec être)">
        <RuleCard card={etre.rule_card} language={language} variant="intro" conceptId={1} onDone={noop} />
      </Section>

      <Section title="F-1 · Rule card v2+ — inline, «More» open">
        <RuleCard card={etre.rule_card} language={language} variant="inline" conceptId={1} defaultOpen />
      </Section>

      {UNITS.map((item) => (
        <Section key={item.external_id} title={`F-1 · Unit page · ${item.sub_band} · ${item.title_fr}`}>
          <RuleCard card={item.rule_card} language={language} variant="inline" defaultOpen />
          <XraySentence xray={item.xray} language={language} />
        </Section>
      ))}

      <Section title="F-1 · v1 card (no v2+ fields) — unchanged, «Why?»">
        <RuleCard card={V1_CARD} language={language} variant="inline" conceptId={2} />
      </Section>

      <Section title="F-1 · Unbalanced markup — plain text, no brackets">
        <RuleCard card={BROKEN_CARD} language={language} variant="inline" />
      </Section>
    </>
  );
}

export default RuleCardGallerySections;
