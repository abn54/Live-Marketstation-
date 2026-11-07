export type Observation = {
  id: number;
  logicalId: string;
  revision: number;
  source: string;
  kind: "candle" | "quote";
  symbol: string;
  interval: string;
  sourceTime: number;
  receivedAt: number;
  orderingTime: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number | null;
  complete?: boolean;
  price?: number;
  changePercent?: number | null;
};
export type Receipt = Observation & {
  receiptId: number;
  disposition: string;
  receiptTime: number;
};
export type ReplayRecord = {
  receiptId: number;
  receivedAt: number;
  disposition: string;
  applied: boolean;
  observation: Observation;
};
export type Channel = {
  state: string;
  detail: string;
  lastReceivedAt?: number;
};
export type Feed = {
  stream: Channel;
  chart: Channel;
  paused: boolean;
  pollMs: number;
  symbols: Record<
    string,
    {
      name?: string;
      exchange?: string;
      chartState?: string;
      chartError?: string;
      lastChartReceivedAt?: number;
      lastCandleSourceTime?: number;
      lastQuoteReceivedAt?: number;
      lastQuoteSourceTime?: number;
    }
  >;
};
export type Stats = {
  observations: number;
  revisions: number;
  receipts: number;
  duplicates: number;
  superseded: number;
  candles: number;
  lastReceiptId: number;
  journalMode: string;
};
export type SymbolData = {
  symbol: string;
  candles: Observation[];
  quote: Observation | null;
  receipts: Receipt[];
};
