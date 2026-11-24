/** A real WebRTC microphone/audio session. Explanations never have order tools. */
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
  private peer: RTCPeerConnection | null = null;
  private channel: RTCDataChannel | null = null;
  private stream: MediaStream | null = null;
  private abort: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private duration: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;
  private sessionId: number | null = null;
  private connecting = false;

  constructor(audio: HTMLAudioElement, options: Options) {
    this.audio = audio;
    this.options = options;
  }

  stop(detail = "Voice session ended", event = "ended", failed = false) {
    this.generation++;
    this.connecting = false;
    if (this.timer) clearTimeout(this.timer);
    if (this.duration) clearTimeout(this.duration);
    this.timer = this.duration = null;
    this.abort?.abort();
    this.abort = null;
    if (this.peer) this.peer.onconnectionstatechange = null;
    this.channel?.close();
    this.peer?.close();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.peer = null;
    this.channel = null;
    this.stream = null;
    this.audio.srcObject = null;
    if (this.sessionId !== null)
      this.options.onEvent(this.sessionId, event, detail);
    this.sessionId = null;
    this.options.onState(failed ? "failed" : "idle", detail);
  }

  injectFailure() {
    this.stop(
      "Injected audio interruption; microphone released. Reconnect to recover.",
      "injected_failure",
      true,
    );
  }

  async start(symbol: string) {
    if (this.peer || this.connecting) return;
    const generation = ++this.generation;
    this.connecting = true;
    this.options.onState(
      "connecting",
      "Requesting microphone and negotiating a live session…",
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
        typeof RTCPeerConnection === "undefined"
      ) {
        throw new Error(
          "Microphone/WebRTC is unavailable in this browser. Use Chrome on localhost.",
        );
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (this.generation !== generation) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      this.stream = stream;
      const peer = new RTCPeerConnection();
      this.peer = peer;
      stream.getTracks().forEach((track) => peer.addTrack(track, stream));
      peer.ontrack = (event) => {
        if (this.generation !== generation) return;
        this.audio.srcObject =
          event.streams[0] ?? new MediaStream([event.track]);
        void this.audio.play().catch(() => {
          if (this.generation === generation)
            this.options.onState(
              "live",
              "Connected. Press Play on the audio control to hear the assistant.",
            );
        });
      };
      peer.onconnectionstatechange = () => {
        if (this.generation !== generation) return;
        if (peer.connectionState === "connected") {
          if (this.timer) clearTimeout(this.timer);
          this.timer = null;
          this.connecting = false;
          this.options.onState(
            "live",
            "Listening. Speak naturally; the assistant replies through live audio.",
          );
          if (this.sessionId !== null)
            this.options.onEvent(
              this.sessionId,
              "connected",
              "Browser reports connected microphone/audio WebRTC transport",
            );
          this.duration = setTimeout(
            () =>
              this.stop(
                "Two-minute session limit reached. Reconnect for a fresh snapshot.",
              ),
            this.options.maxDurationMs ?? 120000,
          );
        } else if (["failed", "disconnected"].includes(peer.connectionState)) {
          this.stop(
            "Audio connection lost. Microphone released; reconnect to recover.",
            "failure",
            true,
          );
        }
      };
      const channel = peer.createDataChannel("oai-events");
      this.channel = channel;
      channel.onopen = () => {
        if (this.generation !== generation) return;
        channel.send(
          JSON.stringify({
            type: "response.create",
            response: {
              instructions:
                "Greet the user in one sentence with the snapshot symbol and simulated account equity if available. Explain that they can ask a question aloud.",
            },
          }),
        );
      };
      channel.onmessage = (event) => {
        if (this.generation !== generation) return;
        try {
          const data = JSON.parse(event.data);
          if (
            data.type ===
            "conversation.item.input_audio_transcription.completed"
          )
            this.options.onTranscript("user", data.transcript);
          if (
            [
              "response.output_audio_transcript.done",
              "response.audio_transcript.done",
            ].includes(data.type)
          )
            this.options.onTranscript("assistant", data.transcript);
          if (
            data.type === "error" ||
            (data.type === "response.done" &&
              data.response?.status === "failed")
          )
            this.stop(
              "The live audio provider reported an error. Reconnect to recover.",
              "failure",
              true,
            );
        } catch {
          /* Ignore unrelated/malformed telemetry; never execute it. */
        }
      };
      channel.onerror = () => {
        if (this.generation === generation)
          this.stop(
            "Audio event channel failed. Reconnect to recover.",
            "failure",
            true,
          );
      };
      channel.onclose = () => {
        if (this.generation === generation)
          this.stop(
            "Audio event channel closed. Reconnect to recover.",
            "failure",
            true,
          );
      };
      this.abort = new AbortController();
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      if (this.generation !== generation) return;
      const response = await fetch(
        `/api/ai/realtime?symbol=${encodeURIComponent(symbol)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/sdp" },
          body: offer.sdp,
          signal: this.abort.signal,
        },
      );
      if (this.generation !== generation) return;
      if (!response.ok) {
        let detail = "Live audio provider is unavailable";
        try {
          const data = await response.json();
          detail = data.error ?? data.detail ?? detail;
        } catch {
          /* Bounded generic error. */
        }
        throw new Error(String(detail).slice(0, 300));
      }
      const answer = await response.text();
      if (this.generation !== generation) return;
      const id = Number(response.headers.get("X-Audio-Session"));
      this.sessionId = Number.isInteger(id) && id > 0 ? id : null;
      await peer.setRemoteDescription({ type: "answer", sdp: answer });
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
