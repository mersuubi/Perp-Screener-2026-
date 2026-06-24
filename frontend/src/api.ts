// Тонкий клиент к API. Никакой бизнес-логики — только запросы.

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";

export interface MetricRow {
  symbol: string;
  price: number | null;
  ret_5m: number | null;
  ret_1h: number | null;
  ret_24h: number | null;
  vol_24h: number | null;
  volatility: number | null;
  volume_zscore: number | null;
  funding_rate: number | null;
  funding_zscore: number | null;
  oi_change_24h: number | null;
  vol_percentile: number | null;
  [k: string]: number | string | null;
}

export interface Candle {
  bucket: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ScreenerFilter {
  field: string;
  op: string;
  value: number;
}

export async function getMetrics(sort = "vol_percentile"): Promise<MetricRow[]> {
  const r = await fetch(`${API_BASE}/metrics?sort=${sort}&desc=true&limit=200`);
  return r.json();
}

export async function getOhlcv(symbol: string, timeframe = "5m"): Promise<Candle[]> {
  const r = await fetch(`${API_BASE}/ohlcv/${symbol}?timeframe=${timeframe}&limit=300`);
  return r.json();
}

export async function runScreener(filters: ScreenerFilter[]) {
  const r = await fetch(`${API_BASE}/screener/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filters }),
  });
  return r.json();
}

export function openLiveSocket(onMessage: (kind: string, payload: any) => void): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/live`);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      onMessage(msg.type, JSON.parse(msg.data));
    } catch {
      /* игнорируем мусор */
    }
  };
  return ws;
}
