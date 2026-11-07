<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  ColorType,
  LineStyle,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import type { Observation } from "./types";
const props = defineProps<{
  candles: Observation[];
  symbol: string;
  fitKey: number;
}>();
const element = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let price: ISeriesApi<"Candlestick"> | null = null;
let volume: ISeriesApi<"Histogram"> | null = null;
let previous: Observation[] = [];
let previousSymbol = "";
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
    previous.every(
      (o, i) => i === previous.length - 1 || o.id === sorted[i]?.id,
    );
  if (incremental) {
    for (let i = previous.length - 1; i < sorted.length; i++) {
      price.update(p(sorted[i]));
      volume.update(v(sorted[i]));
    }
  } else {
    price.setData(sorted.map(p));
    volume.setData(sorted.map(v));
    if (!previous.length) chart.timeScale().fitContent();
  }
  previous = sorted;
  previousSymbol = props.symbol;
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
  chart.priceScale("volume").applyOptions({
    scaleMargins: { top: 0.79, bottom: 0 },
    borderVisible: false,
  });
  render();
  requestAnimationFrame(() => chart?.timeScale().fitContent());
});
watch(() => [props.candles, props.symbol], render, { flush: "post" });
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
    :aria-label="`${symbol} one-minute candlestick chart with corresponding Yahoo volume; UTC time axis`"
  />
</template>
