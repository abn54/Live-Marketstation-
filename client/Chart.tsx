import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  ColorType,
  LineStyle,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import type { Observation } from "./types";

export function MarketChart({
  candles,
  symbol,
  fitKey,
}: {
  candles: Observation[];
  symbol: string;
  fitKey: number;
}) {
  const element = useRef<HTMLDivElement>(null),
    chart = useRef<IChartApi | null>(null),
    price = useRef<ISeriesApi<"Candlestick"> | null>(null),
    volume = useRef<ISeriesApi<"Histogram"> | null>(null);
  const previous = useRef<Observation[]>([]);
  useEffect(() => {
    if (!element.current) return;
    const c = createChart(element.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#111714" },
        textColor: "#7e8a82",
        fontFamily: '"SFMono-Regular", Consolas, monospace',
        fontSize: 10,
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: "#1b241f" },
        horzLines: { color: "#1b241f" },
      },
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
    price.current = c.addSeries(CandlestickSeries, {
      upColor: "#b8ea82",
      downColor: "#ec8b7b",
      wickUpColor: "#b8ea82",
      wickDownColor: "#ec8b7b",
      borderVisible: false,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    volume.current = c.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    c.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.79, bottom: 0 },
      borderVisible: false,
    });
    chart.current = c;
    return () => {
      c.remove();
      chart.current = null;
      previous.current = [];
    };
  }, []);
  useEffect(() => {
    if (!price.current || !volume.current) return;
    const sorted = [...candles].sort((a, b) => a.sourceTime - b.sourceTime);
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
    const old = previous.current;
    const canUpdate =
      old.length > 0 &&
      sorted.length >= old.length &&
      old.every((o, i) => i === old.length - 1 || o.id === sorted[i]?.id);
    if (canUpdate) {
      for (let i = old.length - 1; i < sorted.length; i++) {
        price.current.update(p(sorted[i]));
        volume.current.update(v(sorted[i]));
      }
    } else {
      price.current.setData(sorted.map(p));
      volume.current.setData(sorted.map(v));
      if (!old.length) chart.current?.timeScale().fitContent();
    }
    previous.current = sorted;
  }, [candles]);
  useEffect(() => {
    previous.current = [];
  }, [symbol]);
  useEffect(() => {
    chart.current?.timeScale().fitContent();
  }, [fitKey]);
  return (
    <div
      className="chart-canvas"
      ref={element}
      role="img"
      aria-label={`${symbol} one-minute candlestick chart with corresponding Yahoo volume; UTC time axis`}
    />
  );
}
