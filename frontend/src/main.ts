// Тонкий клиент: рендер таблицы метрик, сетки графиков, панели фильтров + live по WS.
import { createChart, ColorType, type IChartApi, type ISeriesApi } from "lightweight-charts";
import {
  getMetrics,
  getOhlcv,
  runScreener,
  openLiveSocket,
  type MetricRow,
  type Candle,
  type ScreenerFilter,
} from "./api";

// --- Конфиг таблицы: колонки и форматирование ---
const COLUMNS: { key: string; label: string; fmt: (v: any) => string; pct?: boolean }[] = [
  { key: "symbol", label: "Символ", fmt: (v) => v },
  { key: "price", label: "Цена", fmt: (v) => fmtNum(v, 4) },
  { key: "ret_5m", label: "5м %", fmt: fmtPct, pct: true },
  { key: "ret_1h", label: "1ч %", fmt: fmtPct, pct: true },
  { key: "ret_24h", label: "24ч %", fmt: fmtPct, pct: true },
  { key: "volume_zscore", label: "Объём z", fmt: (v) => fmtNum(v, 2) },
  { key: "volatility", label: "Волат.", fmt: (v) => fmtNum(v, 4) },
  { key: "funding_rate", label: "Funding", fmt: (v) => fmtPct(v) },
  { key: "funding_zscore", label: "Funding z", fmt: (v) => fmtNum(v, 2) },
  { key: "oi_change_24h", label: "ΔOI 24ч", fmt: fmtPct, pct: true },
  { key: "vol_percentile", label: "Vol %ile", fmt: (v) => fmtNum(v, 2) },
];

// --- Доступные фильтры скрининга ---
const FILTER_DEFS: { field: string; op: string; label: string; placeholder: string }[] = [
  { field: "volume_zscore", op: ">", label: "Объём z-score >", placeholder: "3" },
  { field: "ret_1h", op: ">", label: "Доходность 1ч >", placeholder: "0.05" },
  { field: "ret_24h", op: ">", label: "Доходность 24ч >", placeholder: "0.1" },
  { field: "funding_zscore", op: ">", label: "Funding z-score >", placeholder: "2" },
  { field: "vol_percentile", op: ">", label: "Vol перцентиль >", placeholder: "0.8" },
];

let sortKey = "vol_percentile";
let lastHits = new Set<string>();
const priceBySymbol = new Map<string, number>();

function fmtNum(v: any, d = 2): string {
  if (v === null || v === undefined) return "—";
  return Number(v).toFixed(d);
}
function fmtPct(v: any): string {
  if (v === null || v === undefined) return "—";
  return (Number(v) * 100).toFixed(2) + "%";
}

// ---------------- Таблица метрик ----------------
function renderFilters() {
  const root = document.getElementById("filters")!;
  root.innerHTML = "";
  for (const f of FILTER_DEFS) {
    const row = document.createElement("div");
    row.className = "filter-row";
    row.innerHTML = `<label>${f.label}</label><input data-field="${f.field}" data-op="${f.op}" placeholder="${f.placeholder}" />`;
    root.appendChild(row);
  }
}

function collectFilters(): ScreenerFilter[] {
  const inputs = document.querySelectorAll<HTMLInputElement>("#filters input");
  const filters: ScreenerFilter[] = [];
  inputs.forEach((inp) => {
    const raw = inp.value.trim();
    if (raw === "") return;
    const value = Number(raw);
    if (Number.isNaN(value)) return;
    filters.push({ field: inp.dataset.field!, op: inp.dataset.op!, value });
  });
  return filters;
}

function renderTable(rows: MetricRow[]) {
  const thead = document.querySelector("#metrics-table thead")!;
  const tbody = document.querySelector("#metrics-table tbody")!;

  thead.innerHTML =
    "<tr>" +
    COLUMNS.map(
      (c) => `<th data-key="${c.key}">${c.label}${sortKey === c.key ? " ▼" : ""}</th>`
    ).join("") +
    "</tr>";

  thead.querySelectorAll("th").forEach((th) =>
    th.addEventListener("click", () => {
      sortKey = (th as HTMLElement).dataset.key!;
      refreshMetrics();
    })
  );

  tbody.innerHTML = rows
    .map((r) => {
      const cells = COLUMNS.map((c) => {
        const v = r[c.key];
        let cls = "";
        if (c.pct && v !== null && v !== undefined) cls = Number(v) >= 0 ? "pos" : "neg";
        if (c.key === "symbol") cls = "sym";
        return `<td class="${cls}">${c.fmt(v)}</td>`;
      }).join("");
      const hitCls = lastHits.has(r.symbol) ? "hit" : "";
      return `<tr class="${hitCls}">${cells}</tr>`;
    })
    .join("");
}

async function refreshMetrics() {
  const rows = await getMetrics(sortKey);
  renderTable(rows);
  return rows;
}

// ---------------- Сетка графиков ----------------
interface ChartHandle {
  symbol: string;
  series: ISeriesApi<"Candlestick">;
  chart: IChartApi;
  last?: Candle;
}
const charts: ChartHandle[] = [];

function makeChart(container: HTMLElement, symbol: string): ChartHandle {
  const cell = document.createElement("div");
  cell.className = "chart-cell";
  cell.innerHTML = `<div class="chart-head"><b>${symbol}</b><span id="price-${symbol}"></span></div><div class="chart-body" id="body-${symbol}"></div>`;
  container.appendChild(cell);

  const chart = createChart(cell.querySelector(`#body-${symbol}`) as HTMLElement, {
    layout: { background: { type: ColorType.Solid, color: "#161b22" }, textColor: "#8b949e" },
    grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
    timeScale: { timeVisible: true, borderColor: "#30363d" },
    rightPriceScale: { borderColor: "#30363d" },
    height: 220,
  });
  const series = chart.addCandlestickSeries({
    upColor: "#2ea043", downColor: "#f85149",
    borderVisible: false, wickUpColor: "#2ea043", wickDownColor: "#f85149",
  });
  return { symbol, series, chart };
}

function toBarTime(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000);
}

async function buildCharts(symbols: string[]) {
  const container = document.getElementById("charts")!;
  container.innerHTML = "";
  charts.length = 0;
  for (const sym of symbols) {
    const handle = makeChart(container, sym);
    const candles = await getOhlcv(sym, "5m");
    handle.series.setData(
      candles.map((c) => ({
        time: toBarTime(c.bucket) as any,
        open: c.open, high: c.high, low: c.low, close: c.close,
      }))
    );
    handle.last = candles.at(-1);
    charts.push(handle);
  }
}

// ---------------- Live по WebSocket ----------------
function setupLive() {
  const statusEl = document.getElementById("status")!;
  const ws = openLiveSocket((kind, payload) => {
    statusEl.textContent = "●  live";
    statusEl.classList.add("live");
    if (kind === "kline") {
      priceBySymbol.set(payload.symbol, payload.close);
      const tag = document.getElementById(`price-${payload.symbol}`);
      if (tag) tag.textContent = Number(payload.close).toFixed(4);
      const handle = charts.find((c) => c.symbol === payload.symbol);
      if (handle) {
        // Live-апдейт текущей 5m-свечи (агрегируем 1m в бар 5m по времени).
        const t = Math.floor(toBarTime(payload.bucket) / 300) * 300;
        handle.series.update({
          time: t as any,
          open: payload.open, high: payload.high, low: payload.low, close: payload.close,
        });
      }
    }
  });
  ws.onclose = () => {
    statusEl.textContent = "●  переподключение…";
    statusEl.classList.remove("live");
    setTimeout(setupLive, 2000); // авто-реконнект
  };
}

// ---------------- Bootstrap ----------------
async function main() {
  renderFilters();
  document.getElementById("run-screener")!.addEventListener("click", async () => {
    try {
      const filters = collectFilters();
      const res = await runScreener(filters);
      lastHits = new Set(res.hits.map((h: any) => h.symbol));
      document.getElementById("screener-result")!.textContent =
        `Прогон #${res.run_id}: ${res.count} совпадений (сохранён в БД)`;
      await refreshMetrics();
    } catch (e) {
      document.getElementById("screener-result")!.textContent = `Ошибка: ${e}`;
    }
  });

  // Метрики грузим отдельно от графиков/WS — падение одного не глушит остальное.
  let rows: MetricRow[] = [];
  try {
    rows = await refreshMetrics();
    if (rows.length === 0) {
      setNote(
        "API отвечает, но данных пока нет — ingestion ещё качает историю с Binance. " +
          "Подождите 1–2 минуты, таблица обновится сама."
      );
    } else {
      setNote("");
    }
  } catch (e) {
    setNote(
      `Не удаётся достучаться до API (${e}). Проверьте, что контейнер api поднят: ` +
        `http://localhost:8000/health должен вернуть {\"status\":\"ok\"}.`,
      true
    );
  }

  try {
    const top = rows.slice(0, 6).map((r) => r.symbol);
    if (top.length) await buildCharts(top);
  } catch (e) {
    console.warn("charts:", e);
  }

  setupLive(); // WS подключается независимо; если упадёт — сам переподключится

  // Периодически освежаем таблицу метрик (метрики считает БД).
  setInterval(() => refreshMetrics().catch(() => {}), 15_000);
}

// Показываем человекочитаемую подсказку/ошибку под таблицей метрик.
function setNote(text: string, isError = false) {
  let el = document.getElementById("metrics-note");
  if (!el) {
    el = document.createElement("div");
    el.id = "metrics-note";
    el.style.cssText = "padding:10px;margin-top:8px;font-size:13px;border-radius:6px;";
    document.querySelector("#metrics-table")!.parentElement!.appendChild(el);
  }
  el.textContent = text;
  el.style.display = text ? "block" : "none";
  el.style.color = isError ? "#f85149" : "#8b949e";
}

main().catch((e) => {
  const s = document.getElementById("status");
  if (s) s.textContent = "● ошибка: " + e;
});
