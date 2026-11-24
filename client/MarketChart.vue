<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  ColorType,
  LineStyle,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  Time,
  UTCTimestamp,
} from "lightweight-charts";
import type { Observation } from "./types";
import { calculateIndicators } from "./indicators";
const props = defineProps<{
  candles: Observation[];
  symbol: string;
  fitKey: number;
  fast?: number;
  slow?: number;
}>();
const element = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let price: ISeriesApi<"Candlestick"> | null = null;
let volume: ISeriesApi<"Histogram"> | null = null;
let shortSma: ISeriesApi<"Line"> | null = null;
let longSma: ISeriesApi<"Line"> | null = null;
let markers: ISeriesMarkersPluginApi<Time> | null = null;
let previous: Observation[] = [];
let previousSymbol = "";
function captureImage() {
  if (!chart || !previous.length)
    throw new Error("Wait for the market chart to load before capturing it.");
  const screenshot = chart.takeScreenshot();
  const scale = Math.min(1, 1536 / screenshot.width, 1000 / screenshot.height);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(screenshot.width * scale);
  canvas.height = Math.round(screenshot.height * scale);
  canvas
    .getContext("2d")!
    .drawImage(screenshot, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}
defineExpose({ captureImage });
function showRecent() {
  if (!chart || !previous.length) return;
  const end = previous.length - 1;
  const visibleBars = Math.max(
    20,
    Math.min(100, Math.floor(element.value!.clientWidth / 7)),
  );
  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, end - visibleBars + 1),
    to: end + 5,
  });
}
function render() {
  if (!chart || !price || !volume) return;
  const changedSymbol = previousSymbol !== props.symbol;
  if (changedSymbol) previous = [];
  const sorted = [...props.candles].sort((a, b) => a.sourceTime - b.sourceTime);
  const p = (o: Observation) => ({
    time: (o.sourceTime / 1000) as UTCTimestamp,
    open: o.open!,
    high: o.high!,
    low: o.low!,
    close: o.close!,
  });
  const v = (o: Observation) =>
    o.volume === null
      ? { time: (o.sourceTime / 1000) as UTCTimestamp }
      : {
          time: (o.sourceTime / 1000) as UTCTimestamp,
          value: o.volume ?? 0,
          color: o.close! >= o.open! ? "#b8ea8245" : "#ec8b7b45",
        };
  const incremental =
    previous.length > 0 &&
    sorted.length >= previous.length &&
    previous.at(-1)!.sourceTime === sorted[previous.length - 1]?.sourceTime &&
    previous.every(
      (o, i) => i === previous.length - 1 || o.id === sorted[i]?.id,
    );
  if (incremental) {
    for (let i = previous.length - 1; i < sorted.length; i++) {
      if (previous[i]?.id === sorted[i].id) continue;
      price.update(p(sorted[i]));
      volume.update(v(sorted[i]));
    }
  } else {
    price.setData(sorted.map(p));
    volume.setData(sorted.map(v));
  }
  const resetRange = !previous.length;
  previous = sorted;
  previousSymbol = props.symbol;
  const points = calculateIndicators(sorted, props.fast, props.slow);
  shortSma?.setData(
    points
      .filter((p) => p.fast !== null)
      .map((p) => ({ time: (p.time / 1000) as UTCTimestamp, value: p.fast! })),
  );
  longSma?.setData(
    points
      .filter((p) => p.slow !== null)
      .map((p) => ({ time: (p.time / 1000) as UTCTimestamp, value: p.slow! })),
  );
  markers?.setMarkers(
    points
      .filter((p) => p.signal)
      .map((p) => ({
        time: (p.time / 1000) as UTCTimestamp,
        position: p.signal === "buy" ? "belowBar" : "aboveBar",
        color: p.signal === "buy" ? "#a6dfff" : "#f0b879",
        shape: p.signal === "buy" ? "arrowUp" : "arrowDown",
      })),
  );
  if (resetRange) showRecent();
}
onMounted(() => {
  chart = createChart(element.value!, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: "#111714" },
      textColor: "#7e8a82",
      fontFamily: '"SFMono-Regular", Consolas, monospace',
      fontSize: 10,
      attributionLogo: true,
    },
    grid: { vertLines: { color: "#1b241f" }, horzLines: { color: "#1b241f" } },
    crosshair: {
      vertLine: { color: "#7b8f7e", style: LineStyle.Dashed },
      horzLine: { color: "#7b8f7e", style: LineStyle.Dashed },
    },
    rightPriceScale: {
      borderColor: "#263229",
      scaleMargins: { top: 0.12, bottom: 0.3 },
    },
    timeScale: {
      borderColor: "#263229",
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 5,
    },
    localization: { locale: "en-US" },
  });
  price = chart.addSeries(CandlestickSeries, {
    upColor: "#b8ea82",
    downColor: "#ec8b7b",
    wickUpColor: "#b8ea82",
    wickDownColor: "#ec8b7b",
    borderVisible: false,
    priceFormat: { type: "price", precision: 2, minMove: 0.01 },
  });
  volume = chart.addSeries(HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
    lastValueVisible: false,
    priceLineVisible: false,
  });
  shortSma = chart.addSeries(LineSeries, {
    color: "#8bd0fb",
    lineWidth: 2,
    title: "Fast SMA",
    priceLineVisible: false,
  });
  longSma = chart.addSeries(LineSeries, {
    color: "#edba78",
    lineWidth: 2,
    title: "Slow SMA",
    priceLineVisible: false,
  });
  markers = createSeriesMarkers(price, []);
  chart.priceScale("volume").applyOptions({
    scaleMargins: { top: 0.79, bottom: 0 },
    borderVisible: false,
  });
  render();
});
watch(() => [props.candles, props.symbol, props.fast, props.slow], render, {
  flush: "post",
});
watch(
  () => props.fitKey,
  () => chart?.timeScale().fitContent(),
  { flush: "post" },
);
onUnmounted(() => {
  chart?.remove();
  chart = null;
});
</script>
<template>
  <div
    class="chart-canvas"
    ref="element"
    role="img"
    :aria-label="`${symbol} one-minute candlestick chart with corresponding Yahoo volume, SMA ${fast ?? 9}, SMA ${slow ?? 21}, and crossover arrows; UTC time axis`"
  />
</template>
