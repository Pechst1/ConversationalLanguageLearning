/* Reader model — pure derivation of the paged Feuilleton reader from one scene.
 *
 * Nothing here fetches, mutates or infers. Every value comes from a field the
 * server actually sent; when a field is missing the model says so ('missing',
 * empty string, null) instead of inventing a panel, a line or a completion.
 *
 * Kept free of React so it can be unit-tested with `node --test`.
 */

export type ReaderScene = {
  id: string;
  status?: string;
  title?: string;
  episode_index?: number | null;
  serial_thread_id?: string | null;
  panels?: ReaderPanelSource[] | null;
  script_payload?: Record<string, any> | null;
  source_snapshot?: Record<string, any> | null;
  hook?: Record<string, any> | null;
  recap?: Record<string, any> | null;
  attempts?: Array<Record<string, any>> | null;
};

export type ReaderPanelSource = {
  id: string;
  panel_index?: number;
  title?: string;
  beat?: string;
  image_url?: string | null;
  image_payload?: Record<string, any> | null;
  overlay_payload?: Record<string, any> | null;
  generation_metadata?: Record<string, any> | null;
};

export type ReaderTask = Record<string, any> & { id?: string; task_type?: string };

export type ReaderLine = {
  key: string;
  who: string;
  fr: string;
  en: string;
  character: string;
};

export type ReaderArtStatus = 'ready' | 'printing' | 'missing';

export type ReaderPanelStage = {
  kind: 'panel';
  key: string;
  ordinal: number;
  panelId: string;
  panelIndex: number;
  title: string;
  beat: string;
  imageUrl: string;
  artStatus: ReaderArtStatus;
  character: string;
  lines: ReaderLine[];
  caption: string;
  tasks: ReaderTask[];
};

export type ReaderResolutionStage = {
  kind: 'resolution';
  key: string;
  ordinal: number;
  character: string;
  hookQuestion: string;
  hookBeat: string;
  tasks: ReaderTask[];
};

export type ReaderStage = ReaderPanelStage | ReaderResolutionStage;

/* The seven world-bible accents. A speaker is identified by colour before any
   name label is read, so the key must resolve from whatever the payload holds. */
export const READER_CHARACTER_KEYS = [
  'romy',
  'marin',
  'lila',
  'gus',
  'margaux',
  'marchand',
  'toi',
] as const;

export type ReaderCharacterKey = (typeof READER_CHARACTER_KEYS)[number] | '';

export function readerCharacterKey(value: unknown): ReaderCharacterKey {
  const text = String(value || '').toLowerCase();
  if (!text) return '';
  if (text.includes('marchand') || text.includes('landlord') || text.includes('propriétaire')) return 'marchand';
  if (text.includes('marin')) return 'marin';
  if (text.includes('lila')) return 'lila';
  if (text.includes('gus') || text.includes('augustin')) return 'gus';
  if (text.includes('margaux')) return 'margaux';
  if (text.includes('romy') || text.includes('romane')) return 'romy';
  if (
    text.includes('toi')
    || text.includes('vous')
    || text.includes('you')
    || text.includes('user')
    || text.includes('protagonist')
  ) return 'toi';
  return '';
}

/* Standalone editions are not cast from the serial world bible: their speakers
   come back as "Clerk", "Supervisor", "Bystander". Those still need to be
   distinguishable by colour without reading a name, so an unknown speaker is
   given one of the same seven accents, deterministically by name — the same
   speaker keeps the same colour across panels and across reloads. Nothing is
   claimed about who they are; only that they are not each other. */
const UNNAMED_ACCENTS: ReaderCharacterKey[] = ['marin', 'lila', 'gus', 'margaux', 'marchand', 'romy'];

export function speakerAccentKey(...seeds: unknown[]): ReaderCharacterKey {
  for (const seed of seeds) {
    const known = readerCharacterKey(seed);
    if (known) return known;
  }
  const label = seeds.map((seed) => String(seed || '').trim()).find(Boolean) || '';
  if (!label) return '';
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) {
    hash = (hash * 31 + label.charCodeAt(i)) % 100000;
  }
  return UNNAMED_ACCENTS[hash % UNNAMED_ACCENTS.length];
}

/* The generator writes "Romane « Romy » Tremblay" into speaker fields; the
   reader never prints more than the short name. */
export function shortSpeakerName(value: unknown): string {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const nickname = raw.match(/[«"“']\s*([^»"”']+?)\s*[»"”']/);
  if (nickname) return nickname[1].trim();
  const cleaned = raw.replace(/\s+/g, ' ');
  const known: Array<[string, string]> = [
    ['romane', 'Romy'], ['romy', 'Romy'], ['marin', 'Marin'], ['lila', 'Lila'],
    ['augustin', 'Gus'], ['gus', 'Gus'], ['margaux', 'Margaux'], ['marchand', 'M. Marchand'],
  ];
  const lowered = cleaned.toLowerCase();
  const match = known.find(([needle]) => lowered.includes(needle));
  if (match) return match[1];
  return cleaned.split(' ')[0];
}

export function normalizeReaderText(value: unknown): string {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function panelArtUrl(panel: ReaderPanelSource): string {
  const direct = typeof panel?.image_url === 'string' ? panel.image_url.trim() : '';
  if (direct) return direct;
  const payload = panel?.image_payload?.url;
  return typeof payload === 'string' && payload.trim() ? payload.trim() : '';
}

/* An honest art state. "printing" only when the server says the image is still
   queued/running; otherwise a panel with no art simply has none. */
export function panelArtStatus(panel: ReaderPanelSource): ReaderArtStatus {
  if (panelArtUrl(panel)) return 'ready';
  const status = String(panel?.generation_metadata?.image_status || '').toLowerCase();
  if (status === 'queued' || status === 'running' || status === 'pending') return 'printing';
  return 'missing';
}

export function panelLines(panel: ReaderPanelSource): ReaderLine[] {
  const bubbles = Array.isArray(panel?.overlay_payload?.bubbles) ? panel.overlay_payload!.bubbles : [];
  return (bubbles as Array<Record<string, any>>)
    .filter((bubble) => bubble && String(bubble.fr || '').trim())
    .map((bubble, index) => {
      const who = shortSpeakerName(bubble.speaker);
      const character = speakerAccentKey(bubble.speaker_id, bubble.speaker);
      return {
        key: `${panel.id}-line-${index}`,
        who,
        fr: String(bubble.fr).trim(),
        en: String(bubble.en || '').trim(),
        character,
      };
    });
}

/* The caption prints only when it adds something the dialogue does not. */
export function panelCaption(panel: ReaderPanelSource, lines: ReaderLine[]): string {
  const caption = String(panel?.overlay_payload?.caption?.fr || '').trim();
  if (!caption) return lines.length ? '' : String(panel?.beat || '').trim();
  const spoken = lines.map((line) => normalizeReaderText(line.fr));
  return spoken.includes(normalizeReaderText(caption)) ? '' : caption;
}

export function panelTasks(panel: ReaderPanelSource): ReaderTask[] {
  const tasks = panel?.overlay_payload?.tasks;
  return Array.isArray(tasks) ? (tasks as ReaderTask[]).filter((task) => task && task.id) : [];
}

export function panelCharacter(panel: ReaderPanelSource, lines: ReaderLine[]): ReaderCharacterKey {
  const spoken = lines.map((line) => line.character).find(Boolean);
  if (spoken) return spoken as ReaderCharacterKey;
  return readerCharacterKey(`${panel?.title || ''} ${panel?.beat || ''}`);
}

/* The speaker's display name for a whole panel, used by the help sheet. */
export function panelSpeakerName(lines: ReaderLine[]): string {
  return lines.map((line) => line.who).find(Boolean) || '';
}

export function sceneHook(scene: ReaderScene): Record<string, any> {
  return (scene?.hook || scene?.script_payload?.hook || scene?.recap?.hook || {}) as Record<string, any>;
}

/* The scene-level closing task, when the payload carries one that is not
   already attached to a panel. */
export function finalSceneTask(scene: ReaderScene, panelTaskIds: Set<string>): ReaderTask | null {
  // The server's closing action lives at script_payload.final_prompt; the other
  // keys are tolerated shapes, never invented ones.
  const candidates = [
    scene?.script_payload?.final_prompt,
    scene?.script_payload?.final_task,
    scene?.script_payload?.closing_task,
  ];
  for (const candidate of candidates) {
    if (candidate && typeof candidate === 'object') {
      const id = String((candidate as ReaderTask).id || '');
      if (id && !panelTaskIds.has(id)) return candidate as ReaderTask;
    }
  }
  return null;
}

/* A "reward" edition is read, not worked: the server sends no learner tasks and
   the reader must not surface any. */
export function isRewardEdition(scene: ReaderScene | null | undefined): boolean {
  return scene?.script_payload?.experience_mode === 'reward';
}

export function readerPanels(scene: ReaderScene | null | undefined): ReaderPanelSource[] {
  const panels = Array.isArray(scene?.panels) ? scene!.panels!.filter(Boolean) : [];
  return [...panels].sort((left, right) => Number(left.panel_index || 0) - Number(right.panel_index || 0));
}

/* Ordered stages: every panel the server sent, then one resolution stage that
   carries the cliffhanger and the closing action. The resolution stage exists
   only when the episode has something to close with — it is never invented to
   pad the progression. */
export function buildReaderStages(scene: ReaderScene | null | undefined): ReaderStage[] {
  if (!scene) return [];
  const panels = readerPanels(scene);
  const rewardMode = isRewardEdition(scene);
  const panelTaskIds = new Set<string>();
  const stages: ReaderStage[] = panels.map((panel, index) => {
    const lines = panelLines(panel);
    const tasks = rewardMode ? [] : panelTasks(panel);
    tasks.forEach((task) => panelTaskIds.add(String(task.id)));
    return {
      kind: 'panel',
      key: `panel:${panel.id}`,
      ordinal: index + 1,
      panelId: panel.id,
      panelIndex: Number(panel.panel_index || index + 1),
      title: String(panel.title || '').trim(),
      beat: String(panel.beat || '').trim(),
      imageUrl: panelArtUrl(panel),
      artStatus: panelArtStatus(panel),
      character: panelCharacter(panel, lines),
      lines,
      caption: panelCaption(panel, lines),
      tasks,
    };
  });

  const hook = sceneHook(scene);
  const hookQuestion = String(hook?.unresolved_question || hook?.teaser || '').trim();
  const hookBeat = String(hook?.text || '').trim();
  const closing = rewardMode ? null : finalSceneTask(scene, panelTaskIds);

  if (!stages.length && !closing && !hookQuestion && !hookBeat) return stages;

  stages.push({
    kind: 'resolution',
    key: `resolution:${scene.id}`,
    ordinal: stages.length + 1,
    character: readerCharacterKey(hook?.speaker) || 'toi',
    hookQuestion,
    hookBeat: hookBeat && hookBeat !== hookQuestion ? hookBeat : '',
    tasks: closing ? [closing] : [],
  });
  return stages;
}

export function stageTaskIds(stage: ReaderStage): string[] {
  return stage.tasks.map((task) => String(task.id || '')).filter(Boolean);
}

export function attemptsByTaskId(scene: ReaderScene | null | undefined): Record<string, Record<string, any>> {
  const map: Record<string, Record<string, any>> = {};
  (scene?.attempts || []).forEach((attempt) => {
    const id = String(attempt?.task_id || '');
    if (id) map[id] = attempt;
  });
  return map;
}

/* Reading order of every answerable task; the "live" one is the first without
   a recorded attempt. Only that one accepts a submission — every other task on
   a revisited panel is read-only, so browsing never replays a choice. */
export function readerTaskOrder(stages: ReaderStage[]): string[] {
  return stages.flatMap(stageTaskIds);
}

export function liveTaskId(
  stages: ReaderStage[],
  attempts: Record<string, Record<string, any>>,
): string | null {
  return readerTaskOrder(stages).find((id) => !attempts[id]) || null;
}

export type StageReadState = 'read' | 'current' | 'ahead';

/* Visibly separates browsing from acting: a stage whose ordinal is at or below
   the furthest reached point, and that holds no live task, is a revisit. */
export function stageReadState(
  stage: ReaderStage,
  options: { furthestOrdinal: number; liveTaskId: string | null },
): StageReadState {
  if (options.liveTaskId && stageTaskIds(stage).includes(options.liveTaskId)) return 'current';
  if (stage.ordinal < options.furthestOrdinal) return 'read';
  if (stage.ordinal === options.furthestOrdinal) return 'current';
  return 'ahead';
}

export function stageIsRevisit(
  stage: ReaderStage,
  options: { furthestOrdinal: number; liveTaskId: string | null },
): boolean {
  return stageReadState(stage, options) === 'read';
}

/* The scene is answerable-complete when every task the server sent has an
   attempt. The reader never derives completion from navigation. */
export function allTasksAnswered(
  stages: ReaderStage[],
  attempts: Record<string, Record<string, any>>,
): boolean {
  const order = readerTaskOrder(stages);
  return order.every((id) => Boolean(attempts[id]));
}

export function readerEpisodeLabel(scene: ReaderScene | null | undefined): string {
  if (!scene) return '';
  if (typeof scene.episode_index === 'number') return `Épisode ${scene.episode_index + 1}`;
  return 'Édition du jour';
}

export function readerLocation(scene: ReaderScene | null | undefined): string {
  const source = scene?.source_snapshot || {};
  const serialContext = scene?.script_payload?.serial_context || {};
  const brief = scene?.script_payload?.episode_brief || scene?.script_payload?.brief_payload || {};
  const candidates = [
    source.location_name,
    source.location,
    serialContext.location,
    brief.location,
    brief.setting,
    scene?.script_payload?.location,
  ];
  for (const value of candidates) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

export function readerPreviously(scene: ReaderScene | null | undefined): string {
  const serialContext = scene?.script_payload?.serial_context || {};
  const hookFromPrevious = serialContext.hook_from_previous || scene?.script_payload?.hook_from_previous || {};
  const source = scene?.source_snapshot || {};
  const candidates = [hookFromPrevious.text, hookFromPrevious.teaser, source.previously, source.previous_hook];
  for (const value of candidates) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

/* ---------------------------------------------------------------------------
   Task presentation — pure readings of what the server returned. None of these
   decide an outcome; they only choose how an outcome the server already sent is
   printed.
   ------------------------------------------------------------------------- */

export type ChoiceOptionView = { value: string; label: string; text: string; en: string };

export function choiceOptionView(option: unknown): ChoiceOptionView | null {
  if (typeof option === 'string') {
    const text = option.trim();
    if (!text) return null;
    const match = text.match(/^([A-Da-d])\s*[:.)-]\s*(.+)$/);
    if (match) {
      return { value: match[1].toUpperCase(), label: match[1].toUpperCase(), text: match[2].trim(), en: '' };
    }
    return { value: text, label: text.length <= 3 ? text : '', text, en: '' };
  }
  if (!option || typeof option !== 'object') return null;
  const record = option as Record<string, any>;
  const value = String(record.value || record.id || record.label || '').trim();
  const label = String(record.label || value).trim();
  const text = String(record.fr || record.text || record.line || label || value).trim();
  if (!value || !text) return null;
  return { value, label, text, en: String(record.en || record.translation || '').trim() };
}

export function choiceOptions(task: ReaderTask): ChoiceOptionView[] {
  if (!Array.isArray(task?.options)) return [];
  return task.options.map(choiceOptionView).filter(Boolean) as ChoiceOptionView[];
}

/* A narrative branch is authorship, never a wrong answer. */
export function correctionIsBranch(correction: Record<string, any> | null | undefined): boolean {
  return correction?.verdict === 'branch' || correction?.grading_mode === 'branch';
}

export function correctionIsPositive(correction: Record<string, any> | null | undefined): boolean {
  return (
    correction?.verdict === 'correct'
    || correction?.verdict === 'accepted'
    || correction?.verdict === 'branch'
  );
}

export function correctionLine(correction: Record<string, any> | null | undefined): string {
  if (!correction) return '';
  if (correctionIsBranch(correction) || correctionIsPositive(correction)) {
    return String(correction.why || '').trim();
  }
  return String(correction.corrected_answer || correction.repair || correction.why || '').trim();
}

export function taskPromptLine(task: ReaderTask): string {
  const prompt = String(task?.prompt || '').trim();
  if (prompt) return prompt;
  const instruction = String(task?.instruction || '').trim();
  return instruction || 'Complétez la tâche.';
}

export function taskPromptTranslation(task: ReaderTask): string {
  return String(task?.prompt_translation || task?.translation || task?.prompt_en || '').trim();
}

export function taskIsChoice(task: ReaderTask): boolean {
  return task?.task_type === 'choice';
}

export function taskIsClosed(task: ReaderTask): boolean {
  return task?.task_type === 'cloze' || taskIsChoice(task);
}
