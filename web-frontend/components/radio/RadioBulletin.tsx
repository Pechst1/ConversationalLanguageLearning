/**
 * WP-122 A · La Radio — the bulletin, alive: the player, the dictée, «C'est entendu».
 *
 * The player plays the lines' clips one after another (`useBulletinPlayer`): the
 * journey's authenticated line clips are fetched with the session through
 * `loadRecallClip` (cached for the session, so the dictée's replay costs nothing),
 * any other URL (the mock's silent WAVs) is played as it is. A clip that fails stops
 * the bulletin and shows the text: silence is a state, not half a bulletin.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

import { heardSource } from '@/components/atelier-v2/journey/dictation-model';
import { journeyCopy } from '@/components/atelier-v2/journey/journey-copy';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import type { RvWordEvent } from '@/components/revue';
import type { RadioClient } from '@/lib/radio-api';
import type { RadioBulletin as RadioBulletinWire, RadioDicteeResult, RadioLanguage, RadioWeek } from '@/lib/radio-types';
import { loadRecallClip } from '@/services/daily-journey';

import { radioCopy } from './radio-copy';
import { bulletinProgress, playerNext, type PlayerEvent, type PlayerPhase } from './radio-model';
import { RadioSurface } from './RadioSurface';

/** The breath between two lines, as the server's estimate assumes. */
const LINE_GAP_MS = 600;

export type BulletinPlayer = {
  phase: PlayerPhase;
  index: number;
  progress: number;
  toggle: () => void;
};

export function useBulletinPlayer(bulletin: RadioBulletinWire): BulletinPlayer {
  const [phase, setPhase] = useState<PlayerPhase>('idle');
  const [index, setIndex] = useState(0);
  const [fraction, setFraction] = useState(0);
  const phaseRef = useRef<PlayerPhase>('idle');
  const indexRef = useRef(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const runRef = useRef(0);
  const timerRef = useRef<number | null>(null);

  const send = useCallback((event: PlayerEvent) => {
    const next = playerNext(phaseRef.current, event);
    phaseRef.current = next;
    setPhase(next);
    return next;
  }, []);

  const release = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.ontimeupdate = null;
      audio.pause();
    }
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  useEffect(
    () => () => {
      runRef.current += 1;
      release();
    },
    [release],
  );

  const playFrom = useCallback(
    async (start: number) => {
      const run = ++runRef.current;
      release();
      const lines = bulletin.lines;
      if (start >= lines.length) {
        send('last_ended');
        return;
      }
      indexRef.current = start;
      setIndex(start);
      setFraction(0);
      send('play');
      const raw = lines[start].clipUrl;
      const source = heardSource(raw);
      if (source.kind === 'none' || typeof Audio === 'undefined') {
        send('failed');
        return;
      }
      let url: string;
      if (source.kind === 'clip') {
        const blob = await loadRecallClip(raw);
        if (runRef.current !== run) return;
        if (!blob) {
          send('failed');
          return;
        }
        url = URL.createObjectURL(blob);
        urlRef.current = url;
      } else {
        url = source.url;
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.ontimeupdate = () => {
        if (runRef.current === run && audio.duration > 0) setFraction(audio.currentTime / audio.duration);
      };
      audio.onended = () => {
        if (runRef.current !== run) return;
        setFraction(1);
        if (start + 1 >= lines.length) {
          release();
          send('last_ended');
          return;
        }
        send('line_ended');
        timerRef.current = window.setTimeout(() => {
          if (runRef.current === run) void playFrom(start + 1);
        }, LINE_GAP_MS);
      };
      audio.onerror = () => {
        if (runRef.current !== run) return;
        release();
        send('failed');
      };
      try {
        await audio.play();
        if (runRef.current === run) send('loaded');
      } catch {
        if (runRef.current === run) {
          release();
          send('failed');
        }
      }
    },
    [bulletin.lines, release, send],
  );

  const toggle = useCallback(() => {
    const current = phaseRef.current;
    if (current === 'playing' || current === 'loading') {
      audioRef.current?.pause();
      if (timerRef.current !== null) {
        // Paused in the breath between two lines: resume on the next one.
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
        indexRef.current += 1;
        setIndex(indexRef.current);
        setFraction(0);
      }
      send('pause');
      return;
    }
    if (current === 'paused' && audioRef.current) {
      const audio = audioRef.current;
      send('play');
      void audio.play().then(
        () => send('loaded'),
        () => send('failed'),
      );
      return;
    }
    if (current === 'paused') {
      void playFrom(indexRef.current);
      return;
    }
    void playFrom(current === 'failed' ? indexRef.current : 0);
  }, [playFrom, send]);

  const progress = phase === 'ended' ? 1 : bulletinProgress(bulletin.lines, index, fraction);
  return { phase, index, progress, toggle };
}

export type RadioBulletinProps = {
  bulletin: RadioBulletinWire;
  client: RadioClient;
  language: RadioLanguage;
  onExit: () => void;
  /** «C'est entendu» was recorded; the page shows its close. */
  onHeard: (week: RadioWeek | null) => void;
};

export function RadioBulletin({ bulletin, client, language, onExit, onHeard }: RadioBulletinProps) {
  const copy = radioCopy(language);
  const player = useBulletinPlayer(bulletin);
  const [readRequested, setReadRequested] = useState(false);
  const [dicteeValue, setDicteeValue] = useState('');
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<RadioDicteeResult | null>(null);
  const [donePending, setDonePending] = useState(false);
  const [word, setWord] = useState<WordHelpRequest | null>(null);

  const onCheck = useCallback(async () => {
    if (checking || result) return;
    setChecking(true);
    try {
      setResult(await client.dictee(bulletin.dossierId, dicteeValue, bulletin.band));
    } catch {
      /* the field keeps the answer; the learner may press again */
    } finally {
      setChecking(false);
    }
  }, [bulletin.band, bulletin.dossierId, checking, client, dicteeValue, result]);

  const onDone = useCallback(async () => {
    setDonePending(true);
    try {
      onHeard(await client.heard(bulletin.dossierId, { band: bulletin.band, dictee: result?.outcome ?? null }));
    } catch {
      onHeard(null);
    }
  }, [bulletin.band, bulletin.dossierId, client, onHeard, result]);

  const onWord = useCallback((event: RvWordEvent) => {
    const term = event.word.toLowerCase().replace(/^(l|d|qu|j|n|s|c)['’]/, '');
    setWord({ surface: event.word, term, sentence: event.sentence, speakerId: 'romy_tremblay' });
  }, []);

  return (
    <>
      <RadioSurface
        bulletin={bulletin}
        copy={copy}
        journeyCopy={journeyCopy(language)}
        language={language}
        phase={player.phase}
        index={player.index}
        progress={player.progress}
        readRequested={readRequested}
        onToggle={player.toggle}
        onRead={() => setReadRequested(true)}
        dicteeValue={dicteeValue}
        onDicteeChange={setDicteeValue}
        onCheck={() => void onCheck()}
        checking={checking}
        dicteeResult={result}
        onDone={() => void onDone()}
        donePending={donePending}
        onWord={onWord}
        onExit={onExit}
      />
      <WordHelpSheet request={word} onClose={() => setWord(null)} language={language} />
    </>
  );
}

export default RadioBulletin;
