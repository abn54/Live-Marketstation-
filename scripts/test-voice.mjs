// Browser API doubles exercise the actual voice controller, not a live provider.
import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { RealtimeVoice } from "../client/voice.ts";

const originals = Object.fromEntries(
  ["navigator", "RTCPeerConnection", "fetch"].map((key) => [
    key,
    Object.getOwnPropertyDescriptor(globalThis, key),
  ]),
);
const controllers = [];
afterEach(() => {
  for (const controller of controllers.splice(0)) controller.stop();
  for (const [key, value] of Object.entries(originals)) {
    if (value) Object.defineProperty(globalThis, key, value);
    else delete globalThis[key];
  }
});
function setup() {
  const states = [],
    transcripts = [],
    events = [],
    peers = [];
  const track = {
    stopped: 0,
    stop() {
      this.stopped++;
    },
  };
  const stream = { getTracks: () => [track] };
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { mediaDevices: { getUserMedia: async () => stream } },
  });
  globalThis.RTCPeerConnection = class {
    connectionState = "new";
    closed = false;
    channel = { close() {}, send() {} };
    constructor() {
      peers.push(this);
    }
    addTrack() {}
    createDataChannel() {
      return this.channel;
    }
    async createOffer() {
      return { type: "offer", sdp: "v=0\r\nm=audio 9 RTP/AVP 0\r\n" };
    }
    async setLocalDescription() {}
    async setRemoteDescription() {
      this.connectionState = "connected";
      this.onconnectionstatechange?.();
    }
    close() {
      this.closed = true;
      this.connectionState = "closed";
    }
  };
  globalThis.fetch = async () =>
    new Response("v=0\r\nm=audio 9 RTP/AVP 0\r\n", {
      headers: { "X-Audio-Session": "7" },
    });
  const audio = { srcObject: null, play: async () => {} };
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
    peers,
    track,
    stream,
    audio,
  };
}

test("WebRTC success receives transcripts; End releases microphone and transport", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "live");
  assert.equal(s.events[0][1], "connected");
  s.peers[0].channel.onmessage({
    data: JSON.stringify({
      type: "conversation.item.input_audio_transcription.completed",
      transcript: "Explain my simulated account.",
    }),
  });
  s.peers[0].channel.onmessage({
    data: JSON.stringify({
      type: "response.output_audio_transcript.done",
      transcript: "The account is simulated.",
    }),
  });
  assert.deepEqual(
    s.transcripts.map((x) => x.role),
    ["user", "assistant"],
  );
  s.controller.stop();
  assert.equal(s.track.stopped, 1);
  assert.equal(s.peers[0].closed, true);
  assert.equal(s.audio.srcObject, null);
});

test("microphone denial reports failure before contacting provider", async () => {
  const s = setup();
  navigator.mediaDevices.getUserMedia = async () => {
    throw new Error("Microphone permission denied");
  };
  let requests = 0;
  globalThis.fetch = async () => {
    requests++;
    return new Response();
  };
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "failed");
  assert.match(s.states.at(-1).detail, /permission denied/);
  assert.equal(requests, 0);
});

test("provider outage stops acquired microphone and permits reconnect", async () => {
  const s = setup();
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "Injected provider outage" }), {
      status: 503,
    });
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.track.stopped, 1);
  assert.equal(s.peers[0].closed, true);
  globalThis.fetch = async () =>
    new Response("v=0\r\nm=audio", { headers: { "X-Audio-Session": "8" } });
  await s.controller.start("BTC-USD");
  assert.equal(s.states.at(-1).state, "live");
});

test("connection loss and injected failure are distinguishable", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  s.peers[0].connectionState = "disconnected";
  s.peers[0].onconnectionstatechange();
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.events.at(-1)[1], "failure");
  await s.controller.start("BTC-USD");
  s.controller.injectFailure();
  assert.equal(s.events.at(-1)[1], "injected_failure");
  assert.equal(s.track.stopped, 2);
});

test("End during microphone prompt cleans up a late granted stream", async () => {
  const s = setup();
  let grant;
  navigator.mediaDevices.getUserMedia = () =>
    new Promise((resolve) => {
      grant = resolve;
    });
  const starting = s.controller.start("BTC-USD");
  s.controller.stop("User ended before permission resolved");
  grant(s.stream);
  await starting;
  assert.equal(s.track.stopped, 1);
  assert.equal(s.peers.length, 0);
  assert.equal(s.states.at(-1).state, "idle");
});

test("audio setup timeout cannot revive a canceled session", async () => {
  const s = setup();
  let grant;
  navigator.mediaDevices.getUserMedia = () =>
    new Promise((resolve) => {
      grant = resolve;
    });
  const starting = s.controller.start("BTC-USD");
  await delay(50);
  assert.equal(s.states.at(-1).state, "failed");
  assert.match(s.states.at(-1).detail, /timed out/);
  grant(s.stream);
  await starting;
  assert.equal(s.track.stopped, 1);
  assert.equal(s.peers.length, 0);
});

test("a late autoplay rejection cannot revive an ended session", async () => {
  const s = setup();
  let rejectPlayback;
  s.audio.play = () =>
    new Promise((resolve, reject) => {
      rejectPlayback = reject;
    });
  await s.controller.start("BTC-USD");
  s.peers[0].ontrack({ streams: [s.stream], track: s.track });
  s.controller.stop();
  rejectPlayback(new Error("Autoplay denied after End"));
  await Promise.resolve();
  assert.equal(s.states.at(-1).state, "idle");
  assert.equal(s.track.stopped, 1);
});

test("a failed provider response ends the live session and releases the microphone", async () => {
  const s = setup();
  await s.controller.start("BTC-USD");
  s.peers[0].channel.onmessage({
    data: JSON.stringify({
      type: "response.done",
      response: { status: "failed" },
    }),
  });
  assert.equal(s.states.at(-1).state, "failed");
  assert.equal(s.track.stopped, 1);
});
