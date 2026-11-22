/**
 * «Papier · la voix» · the printed pieces:
 *
 *  * `VxVeil` — a regular's line before it is heard: the column's lines ruled but not yet set
 *    (as on a proof waiting for its type), inking left to right while the voice speaks, with two
 *    text links in the paper's way, «Écouter» and «Lire». Tapping the ruled lines plays too.
 *  * `VxLeadListen` — the lead read by the newsroom: «▶ Écouter le chapeau», the credit in the
 *    serif italic («lu par la rédaction»), and a hairline under it that inks as it is read.
 *  * `VxFace` — the speaker's face as the replay button.
 *
 * No player chrome: no round buttons, no scrubber, no time; the paper's links and rules only.
 */

import React, { useEffect, useState } from 'react';

import { fillVoix } from './voix-copy';
import { useVoixScope, type VxLineHandle } from './VoixContext';
import { veilLines } from './voix-model';

/** The share of the line already said, on animation frames while it speaks. */
export function useSpokenShare(handle: Pick<VxLineHandle, 'speaking' | 'progress'> | null): number {
  const [share, setShare] = useState(0);
  const speaking = Boolean(handle?.speaking);
  const progress = handle?.progress;
  useEffect(() => {
    if (!speaking || !progress || typeof requestAnimationFrame === 'undefined') {
      setShare(0);
      return undefined;
    }
    let frame = 0;
    const tick = () => {
      setShare(Math.max(0, Math.min(1, progress() ?? 0)));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [progress, speaking]);
  return share;
}

export function VxVeil({ handle, textFr, name }: { handle: VxLineHandle; textFr: string; name: string }) {
  const share = useSpokenShare(handle);
  const lines = veilLines(textFr);
  const { copy } = handle;
  return (
    <div className="vx-veil" data-speaking={handle.speaking ? '' : undefined}>
      <button
        type="button"
        className="vx-veil__lines"
        aria-label={`${name} · ${copy.line_listen}`}
        onClick={handle.speaking ? undefined : handle.play}
        style={{ ['--vx-p' as string]: String(share) }}
      >
        {lines.map((width, index) => (
          <span
            key={index}
            className="vx-veil__line"
            style={{ width: `${width}%`, ['--i' as string]: String(index), ['--n' as string]: String(lines.length) }}
            aria-hidden="true"
          />
        ))}
      </button>
      <p className="vx-veil__tools">
        <button type="button" className="vx-link vx-link--play" aria-pressed={handle.speaking} onClick={handle.play}>
          <span className="vx-tri" aria-hidden="true" />
          {handle.speaking ? copy.line_playing : copy.line_listen}
        </button>
        <button type="button" className="vx-link" onClick={handle.read}>
          {copy.line_read}
        </button>
      </p>
    </div>
  );
}

/** The lead read by the newsroom; without the voice (no scope) the player's own ▶ chip. */
export function VxLeadListen({ textFr, fallback }: { textFr: string; fallback: React.ReactNode }) {
  const scope = useVoixScope();
  const key = `vx-lead|${textFr}`;
  const speaking = scope?.voice.speakingKey === key;
  const share = useSpokenShare(scope ? { speaking, progress: () => (speaking ? scope.voice.progress?.() ?? null : null) } : null);
  if (!scope) return <>{fallback}</>;
  const { copy, voice, manifest } = scope;
  return (
    <span className="vx-lead" data-speaking={speaking ? '' : undefined}>
      <button
        type="button"
        className="vx-link vx-link--play"
        aria-pressed={speaking}
        onClick={() => (speaking ? voice.stop() : voice.speak({ key, text_fr: textFr, character_id: manifest.newsreaderId }))}
      >
        <span className="vx-tri" aria-hidden="true" />
        {speaking ? copy.lead_stop : copy.lead_listen}
      </button>
      <span className="vx-lead__by">{copy.lead_by}</span>
      <span className="vx-lead__rule" aria-hidden="true" style={{ ['--vx-p' as string]: String(share) }} />
    </span>
  );
}

/** The speaker's face, as the button that says their line again (when the session may speak it). */
export function VxFace({ handle, name, children }: { handle: VxLineHandle | null; name: string; children: React.ReactNode }) {
  if (!handle) return <>{children}</>;
  return (
    <button
      type="button"
      className="vx-face"
      data-speaking={handle.speaking ? '' : undefined}
      aria-label={fillVoix(handle.copy.face_replay, { name })}
      onClick={handle.play}
    >
      {children}
    </button>
  );
}
