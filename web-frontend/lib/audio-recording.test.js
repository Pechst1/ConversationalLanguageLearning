const assert = require('node:assert/strict');
const fs = require('fs');
const Module = require('module');
const path = require('path');
const { test } = require('node:test');
const ts = require('typescript');

function load() {
  const helperPath = path.join(__dirname, 'audio-recording.ts');
  const source = fs.readFileSync(helperPath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019 },
  });
  const helperModule = new Module(helperPath);
  helperModule._compile(compiled.outputText, helperPath);
  return helperModule.exports;
}

function withRecorder(FakeRecorder, run) {
  const previous = globalThis.MediaRecorder;
  globalThis.MediaRecorder = FakeRecorder;
  try {
    return run();
  } finally {
    globalThis.MediaRecorder = previous;
  }
}

// The server sizes a recording at 4,000 bytes per second (transcription_cost.py).
const SERVER_ASSUMED_BYTES_PER_SECOND = 4000;

test('the recorder asks for the bit rate the server prices and caps by', () => {
  const { createAudioMediaRecorder, RECORDER_AUDIO_BITS_PER_SECOND } = load();
  assert.equal(RECORDER_AUDIO_BITS_PER_SECOND / 8, SERVER_ASSUMED_BYTES_PER_SECOND);
  const seen = [];
  class FakeRecorder {
    static isTypeSupported(type) {
      return type === 'audio/webm;codecs=opus';
    }
    constructor(stream, options) {
      seen.push(options);
    }
  }
  withRecorder(FakeRecorder, () => createAudioMediaRecorder({}));
  assert.deepEqual(seen, [
    { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: RECORDER_AUDIO_BITS_PER_SECOND },
  ]);
});

test('a WebView without isTypeSupported still asks for the bit rate, and falls back if refused', () => {
  const { createAudioMediaRecorder, RECORDER_AUDIO_BITS_PER_SECOND } = load();
  const seen = [];
  class PickyRecorder {
    constructor(stream, options) {
      seen.push(options);
      if (options) throw new Error('NotSupportedError');
    }
  }
  const recorder = withRecorder(PickyRecorder, () => createAudioMediaRecorder({}));
  assert.ok(recorder instanceof PickyRecorder);
  assert.deepEqual(seen, [{ audioBitsPerSecond: RECORDER_AUDIO_BITS_PER_SECOND }, undefined]);
});
