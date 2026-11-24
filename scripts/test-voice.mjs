// Browser API doubles exercise the actual Gemini PCM voice controller; no live provider.
import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { RealtimeVoice } from "../client/voice.ts";
import { pcm16 } from "../client/audio-worklet.js";
const keys = [
  "navigator",
  "AudioContext",
  "AudioWorkletNode",
  "WebSocket",
  "location",
];
const originals = Object.fromEntries(
  keys.map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]),
);
const controllers = [];
afterEach(() => {
  for (const c of controllers.splice(0)) c.stop();
  for (const [key, value] of Object.entries(originals)) {
    if (value) Object.defineProperty(globalThis, key, value);
    else delete globalThis[key];
  }
});
function setup() {
  const states = [],
    transcripts = [],
    events = [],
    sockets = [],
    contexts = [],
    worklets = [];
  const track = {
      stopped: 0,
      stop() {
        this.stopped++;
      },
    },
    stream = { getTracks: () => [track] };
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { mediaDevices: { getUserMedia: async () => stream } },
  });
  globalThis.location = { protocol: "http:", host: "localhost:3000" };
  globalThis.AudioContext = class {
    currentTime = 0;
    closed = false;
    destination = {};
    audioWorklet = { addModule: async () => {} };
    constructor() {
      contexts.push(this);
    }
    async resume() {}
    async close() {
      this.closed = true;
    }
    createMediaStreamDestination() {
      return { stream: { mock: true } };
    }
    createMediaStreamSource() {
      return { connect() {}, disconnect() {} };
    }
    createBuffer(channels, length, rate) {
      return {
        duration: length / rate,
        getChannelData: () => new Float32Array(length),
      };
    }
    createBufferSource() {
      return { connect() {}, start() {}, stop() {}, buffer: null };
    }
  };
  globalThis.AudioWorkletNode = class {
    port = { onmessage: null };
    constructor() {
      worklets.push(this);
    }
    connect() {}
    disconnect() {}
  };
  globalThis.WebSocket = class {
    static OPEN = 1;
    readyState = 1;
    bufferedAmount = 0;
    sent = [];
    closed = false;
    constructor(url) {
      this.url = url;
      sockets.push(this);
      queueMicrotask(() =>
        this.onmessage?.({
          data: JSON.stringify({
            type: "ready",
            sessionId: 7,
            inputRate: 16000,
            outputRate: 24000,
          }),
        }),
      );
    }
    send(data) {
      this.sent.push(data);
    }
    close() {
      this.closed = true;
      this.readyState = 3;
      this.onclose?.();
    }
  };
  const audio = { srcObject: null, play: async () => {}, pause() {} };
  const controller = new RealtimeVoice(audio, {
    onState: (state, detail) => states.push({ state, detail }),
    onTranscript: (role, text) => transcripts.push({ role, text }),
    onEvent: (...args) => events.push(args),
    connectionTimeoutMs: 30,
    maxDurationMs: 10000,
  });
  controllers.push(controller);
  return {
    controller,
    states,
    transcripts,
    events,
    sockets,
    contexts,
    worklets,
    track,
    stream,
    audio,
  };
}
test("Live socket setup receives transcripts; End releases microphone, playback and transport", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "live");
  assert.equal(s.events[0][1], "connected");
  s.sockets[0].onmessage({
    data: JSON.stringify({
      type: "transcript",
      role: "user",
      text: "Explain my simulated account.",
    }),
  });
  s.sockets[0].onmessage({
    data: JSON.stringify({
      type: "transcript",
      role: "assistant",
      text: "The account is simulated.",
    }),
  });
  assert.deepEqual(
    s.transcripts.map((x) => x.role),
    ["user", "assistant"],
  );
  s.worklets[0].port.onmessage({ data: new ArrayBuffer(3200) });
  assert(s.sockets[0].sent.some((x) => x instanceof ArrayBuffer));
  s.controller.stop();
  assert.equal(s.track.stopped, 1);
  assert(s.sockets[0].closed);
  assert(s.contexts[0].closed);
  assert.equal(s.audio.srcObject, null);
});
test("microphone denial reports failure before contacting provider", async () => {
  const s = setup();
  navigator.mediaDevices.getUserMedia = async () => {
    throw new Error("Microphone permission denied");
  };
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.sockets.length, 0);
  assert(s.contexts[0].closed);
});
test("provider outage stops microphone and permits reconnect", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  s.sockets[0].onmessage({
    data: JSON.stringify({ type: "error", detail: "Injected provider outage" }),
  });
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.track.stopped, 1);
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "live");
});
test("connection loss and injected failure are distinguishable", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  s.sockets[0].onclose();
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.events.at(-1)[1], "failure");
  await s.controller.start("BTC-USD");
  s.controller.injectFailure();
  assert.equal(s.events.at(-1)[1], "injected_failure");
  assert.equal(s.track.stopped, 2);
});
test("End during permission prompt cleans up a late granted stream", async () => {
  const s = setup();
  let grant;
  navigator.mediaDevices.getUserMedia = () =>
    new Promise((resolve) => {
      grant = resolve;
    });
  const starting = s.controller.start("BTC-USD");
  await Promise.resolve();
  s.controller.stop();
  grant(s.stream);
  await starting;
  assert.equal(s.track.stopped, 1);
  assert.equal(s.sockets.length, 0);
  assert.equal(s.states.at(-1).state, "idle");
});
test("setup timeout cannot revive a canceled session", async () => {
  const s = setup();
  let grant;
  navigator.mediaDevices.getUserMedia = () =>
    new Promise((resolve) => {
      grant = resolve;
    });
  const starting = s.controller.start("BTC-USD");
  await delay(50);
  assert.equal(s.states.at(-1).state, "failed");
  grant(s.stream);
  await starting;
  assert.equal(s.track.stopped, 1);
  assert.equal(s.sockets.length, 0);
});
test("late autoplay rejection cannot revive an ended session", async () => {
  const s = setup();
  let rejectPlayback;
  s.audio.play = () =>
    new Promise((resolve, reject) => {
      rejectPlayback = reject;
    });
  await s.controller.start("BTC-USD");
  s.controller.stop();
  rejectPlayback(new Error("Autoplay denied after End"));
  await Promise.resolve();
  assert.equal(s.states.at(-1).state, "idle");
});
test("slow audio upload fails safely and stops the microphone", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  s.sockets[0].bufferedAmount = 100000;
  s.worklets[0].port.onmessage({ data: new ArrayBuffer(3200) });
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.track.stopped, 1);
});
test("PCM resampling preserves duration, silence, clipping and speech-band frequency", () => {
  for (const rate of [44100, 48000]) {
    const input = Float32Array.from({ length: rate / 10 }, (_, i) =>
      Math.sin((2 * Math.PI * 1000 * i) / rate),
    );
    const output = new Int16Array(pcm16(input, rate));
    assert.equal(output.length, 1600);
    let crosses = 0;
    for (let i = 1; i < output.length; i++)
      if (output[i] > 0 != output[i - 1] > 0) crosses++;
    assert(Math.abs(crosses - 200) < 3);
  }
  assert(
    [...new Int16Array(pcm16(new Float32Array(4800), 48000))].every(
      (x) => x === 0,
    ),
  );
  assert.equal(
    new Int16Array(pcm16(new Float32Array(4800).fill(2), 48000))[0],
    32767,
  );
  assert.equal(
    new Int16Array(pcm16(new Float32Array(4800).fill(-2), 48000))[0],
    -32768,
  );
});
