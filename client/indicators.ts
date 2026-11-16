import type { Observation } from "./types";

export type IndicatorPoint = {
  time: number;
  fast: number | null;
  slow: number | null;
  signal: "buy" | "sell" | null;
};

// Completed bars only. Rebuild on a historical correction or replay seek.
export function calculateIndicators(
  candles: Observation[],
  fast = 9,
  slow = 21,
): IndicatorPoint[] {
  const values: number[] = [];
  let previous: number | null = null;
  return candles
    .filter((bar) => bar.complete)
    .map((bar) => {
      values.push(bar.close!);
      const mean = (window: number) =>
        values.length < window
          ? null
          : values.slice(-window).reduce((sum, value) => sum + value, 0) /
            window;
      const short = mean(fast),
        long = mean(slow);
      let difference = long === null ? null : short! - long;
      if (
        difference !== null &&
        Math.abs(difference) <=
          1e-12 * Math.max(Math.abs(short!), Math.abs(long!))
      )
        difference = 0;
      const signal =
        previous !== null && difference !== null
          ? previous <= 0 && difference > 0
            ? "buy"
            : previous >= 0 && difference < 0
              ? "sell"
              : null
          : null;
      previous = difference;
      return { time: bar.sourceTime, fast: short, slow: long, signal };
    });
}
