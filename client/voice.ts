/** Real microphone PCM and Gemini Live audio through a server-owned WebSocket. */
export type VoiceState = "idle" | "connecting" | "live" | "failed";
type Options = {
  onState: (state: VoiceState, detail: string) => void;
  onTranscript: (role: "user" | "assistant", text: string) => void;
  onEvent: (sessionId: number, state: string, detail: string) => void;
  connectionTimeoutMs?: number;
  maxDurationMs?: number;
};

export class RealtimeVoice {
  private options: Options;
  private audio: HTMLAudioElement;
  private socket: WebSocket | null = null;
  private context: AudioContext | null = null;
  private destination: MediaStreamAudioDestinationNode | null = null;
  private microphone: MediaStreamAudioSourceNode | null = null;
  private worklet: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  private playhead = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private duration: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;
  private sessionId: number | null = null;
  private connecting = false;

  constructor(audio: HTMLAudioElement, options: Options) {
    this.audio = audio;
    this.options = options;
  }

  private clearPlayback() {
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {
        /* Already ended. */
      }
    }
    this.sources.clear();
    this.playhead = 0;
  }

  stop(detail = "Voice session ended", event = "ended", failed = false) {
    this.generation++;
    this.connecting = false;
    if (this.timer) clearTimeout(this.timer);
    if (this.duration) clearTimeout(this.duration);
    this.timer = this.duration = null;
    if (this.socket) {
      this.socket.onclose = this.socket.onerror = this.socket.onmessage = null;
      if (this.socket.readyState === WebSocket.OPEN)
        this.socket.send(JSON.stringify({ type: "end" }));
      this.socket.close();
    }
    this.socket = null;
    if (this.worklet) this.worklet.port.onmessage = null;
    this.worklet?.disconnect();
    this.microphone?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.clearPlayback();
    const context = this.context;
    this.context = null;
    this.destination = null;
    this.worklet = null;
    this.microphone = null;
    this.stream = null;
    if (context) void context.close().catch(() => {});
    this.audio.pause();
    this.audio.srcObject = null;
    if (this.sessionId !== null)
      this.options.onEvent(this.sessionId, event, detail);
    this.sessionId = null;
    this.options.onState(failed ? "failed" : "idle", detail);
  }

  injectFailure() {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify({ type: "inject_failure" }));
    this.stop(
      "Injected audio interruption; microphone released. Reconnect to recover.",
      "injected_failure",
      true,
    );
  }

  private play(buffer: ArrayBuffer) {
    const context = this.context,
      destination = this.destination;
    if (!context || !destination) return;
    if (buffer.byteLength % 2 || buffer.byteLength > 256000) {
      this.stop("Invalid audio output. Reconnect to recover.", "failure", true);
      return;
    }
    const count = buffer.byteLength / 2;
    if (!count) return;
    const audio = context.createBuffer(1, count, 24000),
      values = audio.getChannelData(0),
      view = new DataView(buffer);
    for (let i = 0; i < count; i++)
      values[i] = view.getInt16(i * 2, true) / 32768;
    const source = context.createBufferSource();
    source.buffer = audio;
    source.connect(destination);
    this.playhead = Math.max(context.currentTime + 0.02, this.playhead);
    if (this.playhead - context.currentTime > 30) {
      this.stop(
        "Audio playback fell behind. Reconnect to recover.",
        "failure",
        true,
      );
      return;
    }
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);
    source.start(this.playhead);
    this.playhead += audio.duration;
  }

  async start(symbol: string) {
    if (this.socket || this.connecting) return;
    const generation = ++this.generation;
    this.connecting = true;
    this.options.onState(
      "connecting",
      "Requesting microphone and connecting to Gemini Live…",
    );
    this.timer = setTimeout(() => {
      if (this.generation === generation)
        this.stop(
          "Audio connection timed out. Reconnect to try again.",
          "failure",
          true,
        );
    }, this.options.connectionTimeoutMs ?? 25000);
    try {
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices?.getUserMedia ||
        typeof AudioContext === "undefined" ||
        typeof AudioWorkletNode === "undefined"
      )
        throw new Error(
          "Microphone streaming is unavailable in this browser. Use Chrome on localhost.",
        );
      const context = new AudioContext();
      this.context = context;
      await context.resume();
      if (this.generation !== generation) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      if (this.generation !== generation) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      this.stream = stream;
      await context.audioWorklet.addModule(
        new URL("./audio-worklet.js", import.meta.url),
      );
      if (this.generation !== generation) return;
      this.destination = context.createMediaStreamDestination();
      this.audio.srcObject = this.destination.stream;
      this.microphone = context.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(context, "market-pcm16");
      this.worklet = worklet;
      this.microphone.connect(worklet);
      worklet.connect(context.destination);
      const socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/ai/voice?symbol=${encodeURIComponent(symbol)}`,
      );
      this.socket = socket;
      socket.binaryType = "arraybuffer";
      worklet.port.onmessage = (event) => {
        if (
          this.generation !== generation ||
          this.sessionId === null ||
          socket.readyState !== WebSocket.OPEN
        )
          return;
        if (socket.bufferedAmount > 64000) {
          this.stop(
            "The audio upload is too slow. Reconnect to recover.",
            "failure",
            true,
          );
          return;
        }
        socket.send(event.data);
      };
      socket.onmessage = (event) => {
        if (this.generation !== generation) return;
        if (event.data instanceof ArrayBuffer) {
          this.play(event.data);
          return;
        }
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ready") {
            if (
              !Number.isInteger(data.sessionId) ||
              data.sessionId < 1 ||
              data.inputRate !== 16000 ||
              data.outputRate !== 24000
            )
              throw new Error("Invalid voice setup");
            this.sessionId = data.sessionId;
            this.connecting = false;
            if (this.timer) clearTimeout(this.timer);
            this.timer = null;
            this.options.onState(
              "live",
              "Listening. Speak naturally; Gemini replies through live streamed audio.",
            );
            this.options.onEvent(
              data.sessionId,
              "connected",
              "Browser connected to the server-owned Gemini Live audio stream",
            );
            void this.audio.play().catch(() => {
              if (this.generation === generation)
                this.options.onState(
                  "live",
                  "Connected. Press Play on the audio control to hear the assistant.",
                );
            });
            this.duration = setTimeout(
              () =>
                this.stop(
                  "Two-minute session limit reached. Reconnect for a fresh snapshot.",
                ),
              this.options.maxDurationMs ?? 120000,
            );
          } else if (
            data.type === "transcript" &&
            ["user", "assistant"].includes(data.role) &&
            typeof data.text === "string"
          ) {
            this.options.onTranscript(data.role, data.text);
          } else if (data.type === "interrupted") this.clearPlayback();
          else if (data.type === "error")
            this.stop(
              String(data.detail ?? "Live audio provider failed").slice(0, 300),
              "failure",
              true,
            );
          else if (data.type === "ended")
            this.stop(String(data.detail ?? "Voice session ended"));
        } catch {
          this.stop(
            "Audio protocol failed. Reconnect to try again.",
            "failure",
            true,
          );
        }
      };
      socket.onerror = () => {
        if (this.generation === generation)
          this.stop(
            "Live audio connection failed. Reconnect to try again.",
            "failure",
            true,
          );
      };
      socket.onclose = () => {
        if (this.generation === generation)
          this.stop(
            "Live audio connection closed. Microphone released; reconnect to recover.",
            "failure",
            true,
          );
      };
    } catch (error) {
      if (this.generation === generation)
        this.stop(
          error instanceof Error
            ? error.message
            : "Audio session failed. Reconnect to try again.",
          "failure",
          true,
        );
    }
  }
}
