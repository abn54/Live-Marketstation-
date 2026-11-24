// Pure resampling is exported for independent deterministic Node tests.
export function pcm16(samples, fromRate, toRate = 16000) {
  const length = Math.floor((samples.length * toRate) / fromRate);
  const buffer = new ArrayBuffer(length * 2);
  const view = new DataView(buffer);
  const ratio = fromRate / toRate;
  for (let i = 0; i < length; i++) {
    const start = i * ratio,
      end = Math.min(samples.length, (i + 1) * ratio);
    let sum = 0,
      weight = 0;
    for (let j = Math.floor(start); j < Math.ceil(end); j++) {
      const part = Math.min(end, j + 1) - Math.max(start, j);
      sum += samples[j] * part;
      weight += part;
    }
    const value = Math.max(-1, Math.min(1, weight ? sum / weight : 0));
    view.setInt16(
      i * 2,
      Math.round(value < 0 ? value * 32768 : value * 32767),
      true,
    );
  }
  return buffer;
}

if (typeof AudioWorkletProcessor !== "undefined") {
  class MarketPcm extends AudioWorkletProcessor {
    pending = [];
    process(inputs, outputs) {
      for (const channel of outputs[0] ?? []) channel.fill(0);
      const input = inputs[0]?.[0];
      if (input) {
        this.pending.push(...input);
        const frames = Math.round(sampleRate / 10);
        while (this.pending.length >= frames) {
          const block = this.pending.splice(0, frames);
          const output = pcm16(block, sampleRate);
          this.port.postMessage(output, [output]);
        }
      }
      return true;
    }
  }
  registerProcessor("market-pcm16", MarketPcm);
}
