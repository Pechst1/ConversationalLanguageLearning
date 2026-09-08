const PREFERRED_AUDIO_MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/mp4;codecs=mp4a.40.2',
  'audio/webm',
  'audio/mp4',
] as const;

const AUDIO_EXTENSION_BY_MIME: Record<string, string> = {
  'audio/aac': 'aac',
  'audio/flac': 'flac',
  'audio/m4a': 'm4a',
  'audio/mp3': 'mp3',
  'audio/mp4': 'mp4',
  'audio/mpeg': 'mp3',
  'audio/ogg': 'ogg',
  'audio/wav': 'wav',
  'audio/webm': 'webm',
  'audio/x-flac': 'flac',
  'audio/x-m4a': 'm4a',
  'audio/x-wav': 'wav',
};

function baseMimeType(value: string | undefined): string {
  return String(value || '').split(';', 1)[0].trim().toLowerCase();
}

export function createAudioMediaRecorder(stream: MediaStream): MediaRecorder {
  if (typeof MediaRecorder === 'undefined') {
    throw new Error('Audio recording is not supported on this device.');
  }

  if (typeof MediaRecorder.isTypeSupported === 'function') {
    for (const mimeType of PREFERRED_AUDIO_MIME_TYPES) {
      if (!MediaRecorder.isTypeSupported(mimeType)) continue;
      try {
        return new MediaRecorder(stream, { mimeType });
      } catch {
        // Some WebViews report support but reject the constructor option.
      }
    }
  }

  return new MediaRecorder(stream);
}

export function recordedAudioBlob(chunks: Blob[], recorder: MediaRecorder): Blob {
  const mimeType = recorder.mimeType || chunks.find((chunk) => chunk.type)?.type || 'audio/webm';
  return new Blob(chunks, { type: mimeType });
}

export function audioUploadFilename(blob: Blob, stem = 'audio'): string {
  const extension = AUDIO_EXTENSION_BY_MIME[baseMimeType(blob.type)] || 'webm';
  const safeStem = stem.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '') || 'audio';
  return `${safeStem}.${extension}`;
}
