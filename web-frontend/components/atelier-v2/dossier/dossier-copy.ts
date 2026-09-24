/**
 * WP-82 — «Votre dossier» follows the one language rule.
 *
 * Every sentence the page writes about the learner model — the level's source,
 * the capability states, the errata counters, the forecast, the claim panel,
 * the buttons — is chrome: the learner's language up to A2, French from B1
 * (`chromeLanguage`, `lib/language-rule.ts`). What the server sends as content
 * (`title_fr`, an erratum's label and sentences, a claim's `prompt_fr`) stays
 * French whatever this table says. Place names (Dossier, L’Atelier, Relevé)
 * are French in every column.
 *
 * Every table has the same keys and the same `{placeholders}` (the language
 * test proves it); `fill` fills them.
 */

import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export type DossierCopy = {
  // capability states (the rubric)
  cap_not_tried: string;
  cap_with_support: string;
  cap_independent_once: string;
  cap_used_again_later: string;
  cap_unknown: string;
  // errata states and counters
  err_open: string;
  err_repairing: string;
  err_mastered: string;
  counter_open: string;
  counter_repairing: string;
  counter_mastered: string;
  // the level
  src_declared: string;
  src_placement: string;
  src_measured: string;
  src_fallback: string;
  level_none: string;
  level_unreadable: string;
  basis_declared: string;
  basis_placement: string;
  basis_answers: string;
  basis_one_test: string;
  basis_measured: string;
  source_none: string;
  source_declared: string;
  source_placement: string;
  source_placement_dated: string;
  source_measured: string;
  ladder_measured: string;
  ladder_placement: string;
  ladder_basis_answers: string;
  ladder_basis_one_test: string;
  ladder_declared: string;
  row_units: string;
  row_words: string;
  row_checkpoint: string;
  row_value: string;
  coverage_rule: string;
  cp_ready: string;
  cp_failed_dated: string;
  cp_failed: string;
  cp_passed: string;
  cp_credited: string;
  cp_locked: string;
  span_days: string;
  span_days_range: string;
  span_months: string;
  span_months_range: string;
  forecast_capped: string;
  forecast_prior: string;
  forecast_measured: string;
  // WP-S8 — the rules held, measured
  rules_speed: string;
  rules_speed_count: string;
  unit_day: string;
  unit_days: string;
  // evidence
  evref_one: string;
  evref_two: string;
  errata_total_none: string;
  errata_total_one: string;
  errata_total_many: string;
  vocab_unreadable: string;
  vocab_unit: string;
  vocab_acquired: string;
  confidence_none: string;
  confidence_high: string;
  confidence_medium: string;
  confidence_low: string;
  verified_yes: string;
  verified_no: string;
  ev_journey_dated: string;
  ev_journey: string;
  ev_placement_dated: string;
  ev_placement: string;
  ev_declaration_dated: string;
  ev_declaration: string;
  ev_counters_dated: string;
  ev_counters: string;
  ev_erratum: string;
  ev_schedule_dated: string;
  ev_schedule: string;
  cap_evidence: string;
  modality_voice: string;
  modality_written: string;
  because_example: string;
  because: string;
  no_journey: string;
  vocab_sentence: string;
  vocab_rule: string;
  // the screen
  eyebrow: string;
  headline: string;
  level_title: string;
  level_rows: string;
  open_placement: string;
  caps_title: string;
  caps_intro: string;
  errata_title: string;
  errata_unreadable: string;
  errata_rule: string;
  show_detail: string;
  hide_detail: string;
  next_repair: string;
  next_repair_sentence: string;
  not_scheduled: string;
  claim: string;
  vocab_title: string;
  claim_word: string;
  today_title: string;
  today_no_because: string;
  today_ref: string;
  back_to_dossier: string;
  claim_title: string;
  claim_unverifiable: string;
  claim_heading: string;
  claim_terms: string;
  question: string;
  verifying: string;
  verify: string;
  cancel: string;
  back_to_atelier: string;
  unavailable: string;
  // the page
  page_title: string;
  page_label: string;
  load_failed: string;
  generic_failure: string;
};

const FR: DossierCopy = {
  cap_not_tried: 'Pas encore tenté',
  cap_with_support: 'Avec de l’aide',
  cap_independent_once: 'Seul, une fois',
  cap_used_again_later: 'Refait un autre jour',
  cap_unknown: 'Aide non enregistrée',
  err_open: 'À reprendre',
  err_repairing: 'En cours de reprise',
  err_mastered: 'Acquis',
  counter_open: 'ouvertes',
  counter_repairing: 'en réparation',
  counter_mastered: 'maîtrisées',
  src_declared: 'Niveau déclaré',
  src_placement: 'Niveau estimé (bilan)',
  src_measured: 'Niveau mesuré dans l’application',
  src_fallback: 'Niveau estimé',
  level_none: 'Niveau non évalué pour l’instant.',
  level_unreadable: 'Nous ne pouvons pas lire cette estimation pour l’instant.',
  basis_declared: 'Vous nous l’avez indiqué à l’inscription. Nous n’avons encore rien vérifié.',
  basis_placement: 'Mesuré par le bilan de niveau, sur {answers}. {confidence}',
  basis_answers: '{n} réponses corrigées',
  basis_one_test: 'un bilan corrigé',
  basis_measured:
    'Calculé sur votre travail dans l’application : notions tenues, mots connus et l’épreuve de chaque niveau.',
  source_none: 'rien de mesuré pour l’instant',
  source_declared: 'déclaré à l’inscription · non vérifié',
  source_placement: 'estimé (bilan) · non vérifié',
  source_placement_dated: 'estimé (bilan du {date}) · non vérifié',
  source_measured: 'mesuré sur vos réponses en séance',
  ladder_measured: 'Mesuré sur {counted} réponses corrigées en séance, {required} au minimum.',
  ladder_placement: 'Estimé par le bilan, {basis}. Il deviendra « mesuré » après {required} réponses en séance.',
  ladder_basis_answers: 'sur {n} réponses corrigées',
  ladder_basis_one_test: 'sur un bilan corrigé',
  ladder_declared:
    'Le niveau devient « estimé » après le bilan, et « mesuré » après {required} réponses en séance.',
  row_units: 'Notions tenues',
  row_words: 'Mots connus',
  row_checkpoint: 'Épreuve',
  row_value: '{have} / {required} (sur {total})',
  coverage_rule:
    'Pour passer {band} : tenir 85 % de ses notions, connaître 80 % de ses mots, puis réussir l’épreuve de fin de niveau dans l’histoire.',
  cp_ready: 'prête — elle arrive dans l’histoire',
  cp_failed_dated: 'à repasser à partir du {date}',
  cp_failed: 'à repasser après une semaine de consolidation',
  cp_passed: 'réussie',
  cp_credited: 'validée',
  cp_locked: 'après la couverture du niveau',
  span_days: '{n} jours',
  span_days_range: '{low} à {high} jours',
  span_months: '{n} mois',
  span_months_range: '{low} à {high} mois',
  forecast_capped:
    'Estimation : à votre rythme actuel, {target} demanderait plus de deux ans. Un peu de régularité change vite ce chiffre.',
  forecast_prior:
    'Estimation avant mesure, d’après votre rythme : {target} dans {span}. Elle sera recalculée sur votre propre rythme après sept jours actifs.',
  forecast_measured: 'Estimation sur vos quatorze derniers jours : {target} dans {span}, épreuve comprise.',
  rules_speed: 'Vos règles : {n} tenues, {days} en médiane pour en tenir une. Mesuré sur votre propre pratique.',
  rules_speed_count: 'Vos règles : {n} tenues. Mesuré sur votre propre pratique.',
  unit_day: '{n} jour',
  unit_days: '{n} jours',
  evref_one: 'séance du {date}',
  evref_two: 'séances des {first} et {last}',
  errata_total_none: 'Aucune faute notée pour l’instant.',
  errata_total_one: 'Une faute notée en tout.',
  errata_total_many: '{n} fautes notées en tout.',
  vocab_unreadable: 'Nous ne pouvons pas chiffrer votre stock de mots pour l’instant.',
  vocab_unit: 'mots supposés connus à votre niveau · {acquired}',
  vocab_acquired: '{n} acquis par vos révisions',
  confidence_none: 'Aucune confiance chiffrée : rien n’a été mesuré.',
  confidence_high: 'Confiance élevée ({percent} %).',
  confidence_medium: 'Confiance moyenne ({percent} %).',
  confidence_low: 'Confiance faible ({percent} %).',
  verified_yes: 'Vérifié par vos compteurs dans l’application.',
  verified_no: 'Vos compteurs dans l’application sont encore à zéro : ce niveau reste une estimation.',
  ev_journey_dated: 'Séance du {date}',
  ev_journey: 'Séance du jour',
  ev_placement_dated: 'Bilan du {date}',
  ev_placement: 'Bilan de niveau',
  ev_declaration_dated: 'Déclaré à l’inscription, le {date}',
  ev_declaration: 'Déclaré à l’inscription',
  ev_counters_dated: 'Compteurs arrêtés le {date}',
  ev_counters: 'Compteurs de l’application',
  ev_erratum: 'Relevé',
  ev_schedule_dated: 'Prochaine révision le {date}',
  ev_schedule: 'Dans votre file de révision',
  cap_evidence: 'Séance du {date}, {modality}',
  modality_voice: 'à l’oral',
  modality_written: 'à l’écrit',
  because_example: 'Cette scène reprend une faute notée : {label} ({example}).',
  because: 'Cette scène reprend une faute notée : {label}.',
  no_journey: 'Pas encore de scène aujourd’hui.',
  vocab_sentence:
    '{known} mots supposés connus : {nailed} acquis par vos révisions, {core} supposés par votre niveau.',
  vocab_rule: 'Un mot compte comme acquis quand nous estimons que vous le retrouveriez à {percent} % aujourd’hui.',
  eyebrow: 'L’Atelier · Votre dossier',
  headline: 'Ce que nous croyons savoir de vous',
  level_title: 'Votre niveau',
  level_rows: 'Ce que compte le niveau',
  open_placement: 'Faire le bilan de niveau',
  caps_title: 'Vos capacités',
  caps_intro:
    'Ce que vous savez faire, en quatre états — du jamais tenté au refait un autre jour. Ils viennent de vos séances, jamais d’une note recalculée ici.',
  errata_title: 'Vos fautes notées',
  errata_unreadable: 'Cette partie de votre dossier est illisible pour l’instant.',
  errata_rule: 'Une faute quitte le relevé après {n} reprises justes, à des jours différents.',
  show_detail: 'Voir le détail',
  hide_detail: 'Masquer le détail',
  next_repair: 'Prochaine reprise le {date}',
  next_repair_sentence: 'Prochaine reprise le {date}.',
  not_scheduled: 'Pas encore programmée',
  claim: 'Je connais déjà',
  vocab_title: 'Vos mots',
  claim_word: 'Je connais déjà un mot…',
  today_title: 'La scène du jour',
  today_no_because: 'Cette scène ne reprend aucune faute notée en particulier.',
  today_ref: 'séance du jour',
  back_to_dossier: 'Revenir au dossier',
  claim_title: 'Votre déclaration',
  claim_unverifiable: 'Nous ne pouvons pas vérifier cette déclaration.',
  claim_heading: 'Deux questions, puis c’est réglé',
  claim_terms:
    'Si les deux réponses sont justes, nous avançons l’échéance. Si elles ne le sont pas, rien n’est retiré et rien n’est ajouté.',
  question: 'Question {n}',
  verifying: 'Vérification…',
  verify: 'Vérifier',
  cancel: 'Annuler',
  back_to_atelier: 'Revenir à l’Atelier',
  unavailable: 'Dossier indisponible',
  page_title: 'Votre dossier · L’Atelier',
  page_label: 'Votre dossier',
  load_failed: 'Le dossier n’a pas pu être ouvert. Réessayez dans un instant.',
  generic_failure: 'Cette action n’a pas abouti. Réessayez dans un instant.',
};

const EN: DossierCopy = {
  cap_not_tried: 'Not tried yet',
  cap_with_support: 'With help',
  cap_independent_once: 'On your own, once',
  cap_used_again_later: 'Done again another day',
  cap_unknown: 'Help not recorded',
  err_open: 'To redo',
  err_repairing: 'Being repaired',
  err_mastered: 'Mastered',
  counter_open: 'open',
  counter_repairing: 'in repair',
  counter_mastered: 'mastered',
  src_declared: 'Declared level',
  src_placement: 'Estimated level (placement test)',
  src_measured: 'Level measured in the app',
  src_fallback: 'Estimated level',
  level_none: 'Level not assessed yet.',
  level_unreadable: 'We can’t read this estimate right now.',
  basis_declared: 'You told us when you signed up. We haven’t checked anything yet.',
  basis_placement: 'Measured by the placement test, on {answers}. {confidence}',
  basis_answers: '{n} marked answers',
  basis_one_test: 'one marked test',
  basis_measured: 'Calculated from your work in the app: rules held, words known and each level’s test.',
  source_none: 'nothing measured yet',
  source_declared: 'declared at sign-up · not verified',
  source_placement: 'estimated (placement test) · not verified',
  source_placement_dated: 'estimated (placement test of {date}) · not verified',
  source_measured: 'measured on your answers in sessions',
  ladder_measured: 'Measured on {counted} marked answers in sessions, {required} at minimum.',
  ladder_placement:
    'Estimated by the placement test, {basis}. It becomes “measured” after {required} answers in sessions.',
  ladder_basis_answers: 'on {n} marked answers',
  ladder_basis_one_test: 'on one marked test',
  ladder_declared:
    'The level becomes “estimated” after the placement test, and “measured” after {required} answers in sessions.',
  row_units: 'Rules held',
  row_words: 'Words known',
  row_checkpoint: 'Level test',
  row_value: '{have} / {required} (of {total})',
  coverage_rule:
    'To pass {band}: hold 85% of its rules, know 80% of its words, then pass the end-of-level test in the story.',
  cp_ready: 'ready — it comes up in the story',
  cp_failed_dated: 'retake from {date}',
  cp_failed: 'retake after a week of consolidation',
  cp_passed: 'passed',
  cp_credited: 'credited',
  cp_locked: 'once the level is covered',
  span_days: '{n} days',
  span_days_range: '{low} to {high} days',
  span_months: '{n} months',
  span_months_range: '{low} to {high} months',
  forecast_capped:
    'Estimate: at your current pace, {target} would take more than two years. A little regularity changes this number fast.',
  forecast_prior:
    'Estimate before measuring, from your chosen pace: {target} in {span}. It is recalculated on your own pace after seven active days.',
  forecast_measured: 'Estimate from your last fourteen days: {target} in {span}, level test included.',
  rules_speed: 'Your rules: {n} held, a median of {days} to hold one. Measured on your own practice.',
  rules_speed_count: 'Your rules: {n} held. Measured on your own practice.',
  unit_day: '{n} day',
  unit_days: '{n} days',
  evref_one: 'session of {date}',
  evref_two: 'sessions of {first} and {last}',
  errata_total_none: 'No mistakes noted yet.',
  errata_total_one: 'One mistake noted in all.',
  errata_total_many: '{n} mistakes noted in all.',
  vocab_unreadable: 'We can’t count your words right now.',
  vocab_unit: 'words assumed known at your level · {acquired}',
  vocab_acquired: '{n} learned through your reviews',
  confidence_none: 'No confidence figure: nothing has been measured.',
  confidence_high: 'High confidence ({percent}%).',
  confidence_medium: 'Medium confidence ({percent}%).',
  confidence_low: 'Low confidence ({percent}%).',
  verified_yes: 'Verified by your counters in the app.',
  verified_no: 'Your counters in the app are still at zero: this level is still an estimate.',
  ev_journey_dated: 'Session of {date}',
  ev_journey: 'Today’s session',
  ev_placement_dated: 'Placement test of {date}',
  ev_placement: 'Placement test',
  ev_declaration_dated: 'Declared at sign-up, on {date}',
  ev_declaration: 'Declared at sign-up',
  ev_counters_dated: 'Counters as of {date}',
  ev_counters: 'App counters',
  ev_erratum: 'Relevé',
  ev_schedule_dated: 'Next review on {date}',
  ev_schedule: 'In your review queue',
  cap_evidence: 'Session of {date}, {modality}',
  modality_voice: 'spoken',
  modality_written: 'written',
  because_example: 'This scene revisits a noted mistake: {label} ({example}).',
  because: 'This scene revisits a noted mistake: {label}.',
  no_journey: 'No scene yet today.',
  vocab_sentence: '{known} words assumed known: {nailed} learned through your reviews, {core} assumed from your level.',
  vocab_rule: 'A word counts as learned when we estimate you would recall it with {percent}% certainty today.',
  eyebrow: 'L’Atelier · Your Dossier',
  headline: 'What we think we know about you',
  level_title: 'Your level',
  level_rows: 'What the level counts',
  open_placement: 'Take the placement test',
  caps_title: 'Your abilities',
  caps_intro:
    'What you can do, in four states — from never tried to done again another day. They come from your sessions, never from a score recalculated here.',
  errata_title: 'Your noted mistakes',
  errata_unreadable: 'This part of your Dossier can’t be read right now.',
  errata_rule: 'A mistake leaves the list after {n} correct repairs, on different days.',
  show_detail: 'Show details',
  hide_detail: 'Hide details',
  next_repair: 'Next repair on {date}',
  next_repair_sentence: 'Next repair on {date}.',
  not_scheduled: 'Not scheduled yet',
  claim: 'I already know this',
  vocab_title: 'Your words',
  claim_word: 'I already know a word…',
  today_title: 'Today’s scene',
  today_no_because: 'This scene does not revisit any particular noted mistake.',
  today_ref: 'today’s session',
  back_to_dossier: 'Back to the Dossier',
  claim_title: 'Your claim',
  claim_unverifiable: 'We can’t check this claim.',
  claim_heading: 'Two questions, and it’s settled',
  claim_terms:
    'If both answers are right, we move the review date forward. If they aren’t, nothing is taken away and nothing is added.',
  question: 'Question {n}',
  verifying: 'Checking…',
  verify: 'Check',
  cancel: 'Cancel',
  back_to_atelier: 'Back to L’Atelier',
  unavailable: 'Dossier unavailable',
  page_title: 'Your Dossier · L’Atelier',
  page_label: 'Your Dossier',
  load_failed: 'Your Dossier could not be opened. Please try again in a moment.',
  generic_failure: 'That didn’t work. Please try again in a moment.',
};

const DE: DossierCopy = {
  cap_not_tried: 'Noch nicht versucht',
  cap_with_support: 'Mit Hilfe',
  cap_independent_once: 'Allein, einmal',
  cap_used_again_later: 'An einem anderen Tag wiederholt',
  cap_unknown: 'Hilfe nicht erfasst',
  err_open: 'Zu wiederholen',
  err_repairing: 'In Überarbeitung',
  err_mastered: 'Gemeistert',
  counter_open: 'offen',
  counter_repairing: 'in Reparatur',
  counter_mastered: 'gemeistert',
  src_declared: 'Angegebenes Niveau',
  src_placement: 'Geschätztes Niveau (Einstufungstest)',
  src_measured: 'In der App gemessenes Niveau',
  src_fallback: 'Geschätztes Niveau',
  level_none: 'Niveau noch nicht bewertet.',
  level_unreadable: 'Wir können diese Schätzung gerade nicht lesen.',
  basis_declared: 'Sie haben es bei der Anmeldung angegeben. Wir haben noch nichts geprüft.',
  basis_placement: 'Gemessen im Einstufungstest, anhand von {answers}. {confidence}',
  basis_answers: '{n} korrigierten Antworten',
  basis_one_test: 'einem korrigierten Test',
  basis_measured:
    'Berechnet aus Ihrer Arbeit in der App: sichere Regeln, bekannte Wörter und die Prüfung jedes Niveaus.',
  source_none: 'noch nichts gemessen',
  source_declared: 'bei der Anmeldung angegeben · nicht geprüft',
  source_placement: 'geschätzt (Einstufungstest) · nicht geprüft',
  source_placement_dated: 'geschätzt (Einstufungstest vom {date}) · nicht geprüft',
  source_measured: 'gemessen an Ihren Antworten in den Übungen',
  ladder_measured: 'Gemessen an {counted} korrigierten Antworten in den Übungen, mindestens {required}.',
  ladder_placement:
    'Geschätzt im Einstufungstest, {basis}. Nach {required} Antworten in den Übungen gilt es als „gemessen“.',
  ladder_basis_answers: 'anhand von {n} korrigierten Antworten',
  ladder_basis_one_test: 'anhand eines korrigierten Tests',
  ladder_declared:
    'Nach dem Einstufungstest gilt das Niveau als „geschätzt“, nach {required} Antworten in den Übungen als „gemessen“.',
  row_units: 'Sichere Regeln',
  row_words: 'Bekannte Wörter',
  row_checkpoint: 'Niveauprüfung',
  row_value: '{have} / {required} (von {total})',
  coverage_rule:
    'Um {band} abzuschließen: 85 % der Regeln sicher beherrschen, 80 % der Wörter kennen und dann die Abschlussprüfung in der Geschichte bestehen.',
  cp_ready: 'bereit — sie kommt in der Geschichte',
  cp_failed_dated: 'Wiederholung ab {date}',
  cp_failed: 'Wiederholung nach einer Woche Festigung',
  cp_passed: 'bestanden',
  cp_credited: 'anerkannt',
  cp_locked: 'sobald das Niveau abgedeckt ist',
  span_days: '{n} Tagen',
  span_days_range: '{low} bis {high} Tagen',
  span_months: '{n} Monaten',
  span_months_range: '{low} bis {high} Monaten',
  forecast_capped:
    'Schätzung: Bei Ihrem aktuellen Tempo würde {target} mehr als zwei Jahre dauern. Etwas Regelmäßigkeit ändert diese Zahl schnell.',
  forecast_prior:
    'Schätzung vor der Messung, nach Ihrem Rhythmus: {target} in {span}. Nach sieben aktiven Tagen wird sie nach Ihrem eigenen Tempo neu berechnet.',
  forecast_measured: 'Schätzung aus Ihren letzten vierzehn Tagen: {target} in {span}, Prüfung inbegriffen.',
  rules_speed: 'Ihre Regeln: {n} sitzen, im Median {days} bis eine sitzt. Gemessen an Ihrer eigenen Übung.',
  rules_speed_count: 'Ihre Regeln: {n} sitzen. Gemessen an Ihrer eigenen Übung.',
  unit_day: '{n} Tag',
  unit_days: '{n} Tage',
  evref_one: 'Übung vom {date}',
  evref_two: 'Übungen vom {first} und {last}',
  errata_total_none: 'Noch keine Fehler notiert.',
  errata_total_one: 'Insgesamt ein Fehler notiert.',
  errata_total_many: 'Insgesamt {n} Fehler notiert.',
  vocab_unreadable: 'Wir können Ihren Wortschatz gerade nicht beziffern.',
  vocab_unit: 'Wörter, die auf Ihrem Niveau als bekannt gelten · {acquired}',
  vocab_acquired: '{n} durch Ihre Wiederholungen gelernt',
  confidence_none: 'Keine bezifferte Sicherheit: Es wurde nichts gemessen.',
  confidence_high: 'Hohe Sicherheit ({percent} %).',
  confidence_medium: 'Mittlere Sicherheit ({percent} %).',
  confidence_low: 'Geringe Sicherheit ({percent} %).',
  verified_yes: 'Durch Ihre Zähler in der App geprüft.',
  verified_no: 'Ihre Zähler in der App stehen noch auf null: Dieses Niveau bleibt eine Schätzung.',
  ev_journey_dated: 'Übung vom {date}',
  ev_journey: 'Heutige Übung',
  ev_placement_dated: 'Einstufungstest vom {date}',
  ev_placement: 'Einstufungstest',
  ev_declaration_dated: 'Bei der Anmeldung angegeben, am {date}',
  ev_declaration: 'Bei der Anmeldung angegeben',
  ev_counters_dated: 'Zählerstand vom {date}',
  ev_counters: 'Zähler der App',
  ev_erratum: 'Relevé',
  ev_schedule_dated: 'Nächste Wiederholung am {date}',
  ev_schedule: 'In Ihrer Wiederholungsliste',
  cap_evidence: 'Übung vom {date}, {modality}',
  modality_voice: 'mündlich',
  modality_written: 'schriftlich',
  because_example: 'Diese Szene greift einen notierten Fehler auf: {label} ({example}).',
  because: 'Diese Szene greift einen notierten Fehler auf: {label}.',
  no_journey: 'Heute noch keine Szene.',
  vocab_sentence:
    '{known} Wörter gelten als bekannt: {nailed} durch Ihre Wiederholungen gelernt, {core} aufgrund Ihres Niveaus angenommen.',
  vocab_rule:
    'Ein Wort gilt als gelernt, wenn wir schätzen, dass Sie es heute mit {percent} % Wahrscheinlichkeit abrufen würden.',
  eyebrow: 'L’Atelier · Ihr Dossier',
  headline: 'Was wir über Sie zu wissen glauben',
  level_title: 'Ihr Niveau',
  level_rows: 'Was das Niveau zählt',
  open_placement: 'Einstufungstest machen',
  caps_title: 'Ihre Fähigkeiten',
  caps_intro:
    'Was Sie können, in vier Stufen — von nie versucht bis an einem anderen Tag wiederholt. Sie stammen aus Ihren Übungen, nie aus einer hier neu berechneten Note.',
  errata_title: 'Ihre notierten Fehler',
  errata_unreadable: 'Dieser Teil Ihres Dossiers ist gerade nicht lesbar.',
  errata_rule: 'Ein Fehler verlässt die Liste nach {n} richtigen Wiederholungen an verschiedenen Tagen.',
  show_detail: 'Details anzeigen',
  hide_detail: 'Details ausblenden',
  next_repair: 'Nächste Wiederholung am {date}',
  next_repair_sentence: 'Nächste Wiederholung am {date}.',
  not_scheduled: 'Noch nicht geplant',
  claim: 'Kenne ich schon',
  vocab_title: 'Ihre Wörter',
  claim_word: 'Ich kenne ein Wort schon…',
  today_title: 'Die Szene des Tages',
  today_no_because: 'Diese Szene greift keinen bestimmten notierten Fehler auf.',
  today_ref: 'heutige Übung',
  back_to_dossier: 'Zurück zum Dossier',
  claim_title: 'Ihre Angabe',
  claim_unverifiable: 'Wir können diese Angabe nicht prüfen.',
  claim_heading: 'Zwei Fragen, dann ist es erledigt',
  claim_terms:
    'Sind beide Antworten richtig, ziehen wir den Termin vor. Sind sie es nicht, wird nichts abgezogen und nichts hinzugefügt.',
  question: 'Frage {n}',
  verifying: 'Wird geprüft…',
  verify: 'Prüfen',
  cancel: 'Abbrechen',
  back_to_atelier: 'Zurück zum Atelier',
  unavailable: 'Dossier nicht verfügbar',
  page_title: 'Ihr Dossier · L’Atelier',
  page_label: 'Ihr Dossier',
  load_failed: 'Ihr Dossier konnte nicht geöffnet werden. Bitte versuchen Sie es gleich noch einmal.',
  generic_failure: 'Das hat nicht geklappt. Bitte versuchen Sie es gleich noch einmal.',
};

export const DOSSIER_COPY: Record<ControlLanguage, DossierCopy> = { en: EN, de: DE, fr: FR };

/** The Dossier copy table for a chrome language (regional tags and nulls normalised). */
export function dossierCopy(language: unknown): DossierCopy {
  return DOSSIER_COPY[normalizeControlLanguage(language)];
}

/** `{n}`-style placeholders filled in. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

/* ---------------------------------------------------------------------------
   Dates, from an ISO day with no timezone arithmetic. French keeps its own
   conventions («1er», «sept.»; «mars», «mai», «juin», «août» never cut).
   --------------------------------------------------------------------------- */

const MONTHS: Record<ControlLanguage, string[]> = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
};

const SHORT_MONTHS: Record<ControlLanguage, string[]> = {
  fr: ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juill.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'],
  de: ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.', 'Nov.', 'Dez.'],
};

/** The day alone: «12», «1er» (fr), «12» (en), «12.» (de). */
export function dayNumber(iso: string, language: ControlLanguage = 'fr'): string {
  const day = Number(iso.slice(8, 10));
  if (!day) return iso;
  if (language === 'fr') return day === 1 ? '1er' : String(day);
  if (language === 'de') return `${day}.`;
  return String(day);
}

/** «5 septembre», «5 September», «5. September». */
export function longDate(iso: string, language: ControlLanguage = 'fr'): string {
  const [year, month, day] = iso.slice(0, 10).split('-').map((part) => Number(part));
  if (!year || !month || !day) return iso;
  return `${dayNumber(iso, language)} ${MONTHS[language][month - 1]}`;
}

/** «12 sept.», «12 Sept», «12. Sept.». */
export function shortDate(iso: string, language: ControlLanguage = 'fr'): string {
  const month = Number(iso.slice(5, 7));
  const day = dayNumber(iso, language);
  const months = SHORT_MONTHS[language];
  if (!month || !months[month - 1] || day === iso) return iso;
  return `${day} ${months[month - 1]}`;
}
