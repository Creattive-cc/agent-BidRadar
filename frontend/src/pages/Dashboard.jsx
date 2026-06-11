import { useEffect, useRef, useState } from "react";
import { fetchStats, fetchBids, fetchProducts, fetchLogs } from "../services/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatValue(v) {
  if (!v) return "R$ 0";
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `R$ ${(v / 1_000).toFixed(0)}k`;
  return `R$ ${v.toFixed(0)}`;
}

// ── Dropdown de período (single-select) ───────────────────────────────────────

const PERIOD_OPTIONS = [
  { id: "all", label: "Todos os períodos" },
  { id: "24h", label: "Últimas 24h" },
  { id: "48h", label: "Últimas 48h" },
];

function PeriodDropdown({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const current = PERIOD_OPTIONS.find((o) => o.id === value);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:border-violet-300 transition-colors min-w-[180px]"
      >
        <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="flex-1 text-left text-gray-700">{current?.label}</span>
        <svg className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[200px] py-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => { onChange(opt.id); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-gray-50 ${value === opt.id ? "text-violet-700 font-medium" : "text-gray-700"}`}
            >
              <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${value === opt.id ? "border-violet-600" : "border-gray-300"}`}>
                {value === opt.id && <div className="w-2 h-2 rounded-full bg-violet-600" />}
              </div>
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Dropdown de produtos (multi-select com chips) ──────────────────────────────

function ProductsDropdown({ products, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function toggle(name) {
    const next = new Set(selected);
    next.has(name) ? next.delete(name) : next.add(name);
    onChange(next);
  }

  const selectedArr = [...selected];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:border-violet-300 transition-colors min-w-[200px] max-w-[420px]"
      >
        <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
        {selectedArr.length === 0 ? (
          <span className="text-gray-500 flex-1 text-left">Todos os produtos</span>
        ) : (
          <div className="flex flex-wrap gap-1 flex-1">
            {selectedArr.map((name) => (
              <span
                key={name}
                className="flex items-center gap-1 bg-violet-100 text-violet-700 text-xs font-medium px-2 py-0.5 rounded-full"
              >
                {name}
                <button
                  onClick={(e) => { e.stopPropagation(); toggle(name); }}
                  className="hover:text-violet-900 leading-none"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <svg className={`w-4 h-4 text-gray-400 flex-shrink-0 ml-auto transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[240px] py-1">
          {products.map((p) => (
            <button
              key={p.id}
              onClick={() => toggle(p.name)}
              className="w-full flex items-start gap-2.5 px-3 py-2.5 hover:bg-gray-50 text-left"
            >
              <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 mt-0.5 ${selected.has(p.name) ? "bg-violet-600 border-violet-600" : "border-gray-300"}`}>
                {selected.has(p.name) && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <div className="min-w-0">
                <p className="text-sm text-gray-800 font-medium">{p.name}</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {p.tags.map((tag) => (
                    <span key={tag} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{tag}</span>
                  ))}
                </div>
              </div>
            </button>
          ))}
          {selected.size > 0 && (
            <>
              <div className="border-t border-gray-100 mt-1" />
              <button
                onClick={() => onChange(new Set())}
                className="w-full text-xs text-gray-400 hover:text-gray-600 px-3 py-2 text-left"
              >
                Limpar seleção
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── KPI icons ─────────────────────────────────────────────────────────────────

const KPI_ICONS = {
  bids: (
    <svg className="w-5 h-5 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  ),
  hours: (
    <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  opps: (
    <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  value: (
    <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  ),
};

// ── Funil ─────────────────────────────────────────────────────────────────────

function FunnelBar({ label, value, max, highlight }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-lg ${highlight ? "bg-violet-600 text-white" : "bg-gray-100"}`}>
      <span className={`text-sm flex-1 ${highlight ? "text-white font-semibold" : "text-gray-700"}`}>{label}</span>
      <div className={`flex-shrink-0 h-2 rounded-full ${highlight ? "bg-violet-400" : "bg-gray-300"}`} style={{ width: `${Math.max(pct, 4)}%`, minWidth: 8, maxWidth: 200 }} />
      <span className={`text-sm font-semibold w-16 text-right ${highlight ? "text-white" : "text-gray-800"}`}>
        {value.toLocaleString("pt-BR")}
      </span>
    </div>
  );
}

// ── Logs ──────────────────────────────────────────────────────────────────────

const EVENT_LABELS = {
  detection: { label: "Detecção", color: "bg-blue-100 text-blue-700" },
  ai_processing: { label: "IA Processando", color: "bg-amber-100 text-amber-700" },
  high_match: { label: "Alta Compatibilidade", color: "bg-green-100 text-green-700" },
  human_review: { label: "Revisão Humana", color: "bg-violet-100 text-violet-700" },
  auto_discard: { label: "Descarte Automático", color: "bg-red-100 text-red-600" },
};

const EVENT_DOT_COLOR = {
  detection: "bg-blue-500",
  ai_processing: "bg-amber-500",
  high_match: "bg-green-500",
  human_review: "bg-violet-500",
  auto_discard: "bg-red-500",
};

// ── Score pill ────────────────────────────────────────────────────────────────

function ScorePill({ score }) {
  const s = Math.round(score);
  const cls =
    s >= 75 ? "bg-green-100 text-green-700"
    : s >= 50 ? "bg-amber-100 text-amber-700"
    : "bg-red-100 text-red-600";
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${cls}`}>{s}%</span>;
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [bids, setBids] = useState([]);
  const [products, setProducts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [dateFilter, setDateFilter] = useState("all");
  const [selectedProducts, setSelectedProducts] = useState(new Set());

  useEffect(() => {
    fetchStats().then(setStats).catch(console.error);
    fetchBids().then(setBids).catch(console.error);
    fetchLogs(5).then(setLogs).catch(console.error);
    fetchProducts().then(setProducts).catch(console.error);
  }, []);

  // ── Filtragem ───────────────────────────────────────────────────────────────
  const now = Date.now();

  const filteredBids = bids.filter((bid) => {
    if (dateFilter !== "all") {
      const hours = dateFilter === "24h" ? 24 : 48;
      if (new Date(bid.created_at).getTime() < now - hours * 3_600_000) return false;
    }
    if (selectedProducts.size > 0) {
      const matchTags = products
        .filter((p) => selectedProducts.has(p.name))
        .flatMap((p) => p.tags);
      if (matchTags.length > 0) {
        const text = (bid.title + " " + bid.agency).toLowerCase();
        if (!matchTags.some((t) => text.includes(t.toLowerCase()))) return false;
      }
    }
    return true;
  });

  // ── KPIs computados dos bids filtrados ─────────────────────────────────────
  const hasData = bids.length > 0;
  const displayStats = hasData
    ? {
        total_bids: filteredBids.length,
        hours_saved: Math.round(filteredBids.length * 0.25 * 10) / 10,
        opportunities: filteredBids.filter((b) => b.score >= 70).length,
        total_value: filteredBids.reduce((s, b) => s + (b.score >= 70 ? b.estimated_value || 0 : 0), 0),
        funnel: {
          captured: filteredBids.length,
          filtered: filteredBids.filter((b) => b.analysis_time_seconds > 0).length,
          analyzed: filteredBids.filter((b) => b.analysis_time_seconds > 0).length,
          hot: filteredBids.filter((b) => b.score >= 70).length,
        },
      }
    : stats;

  const funnel = displayStats?.funnel ?? {};
  const funnelMax = funnel.captured || 1;

  const filtersActive = dateFilter !== "all" || selectedProducts.size > 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Visão Geral</h1>
        <p className="text-sm text-gray-500 mt-0.5">Bem-vindo (a) à plataforma</p>
      </div>

      {/* Filtros */}
      <div className="flex items-center gap-3 mb-8 flex-wrap">
        <PeriodDropdown value={dateFilter} onChange={setDateFilter} />
        <ProductsDropdown
          products={products}
          selected={selectedProducts}
          onChange={setSelectedProducts}
        />
        {filtersActive && (
          <button
            onClick={() => { setDateFilter("all"); setSelectedProducts(new Set()); }}
            className="text-xs text-gray-400 hover:text-gray-600 underline"
          >
            Limpar filtros
          </button>
        )}
        {filtersActive && hasData && (
          <span className="ml-auto text-xs text-gray-400">
            {filteredBids.length} de {bids.length} editais
          </span>
        )}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { icon: KPI_ICONS.bids, label: "Editais Monitorados", value: displayStats?.total_bids?.toLocaleString("pt-BR") ?? "—" },
          { icon: KPI_ICONS.hours, label: "Horas de Leitura Poupadas", value: displayStats ? `${displayStats.hours_saved}h` : "—" },
          { icon: KPI_ICONS.opps, label: "Oportunidades Reais", value: displayStats?.opportunities?.toLocaleString("pt-BR") ?? "—" },
          { icon: KPI_ICONS.value, label: "Valor Total em Jogo", value: displayStats ? formatValue(displayStats.total_value) : "—" },
        ].map((kpi) => (
          <div key={kpi.label} className="bg-white rounded-xl border border-gray-100 p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{kpi.label}</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">{kpi.value}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center">
              {kpi.icon}
            </div>
          </div>
        ))}
      </div>

      {/* Funil + Logs */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white rounded-xl border border-gray-100 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Análise de Funil</h2>
          <div className="space-y-2">
            <FunnelBar label="Total Captado" value={funnel.captured ?? 0} max={funnelMax} />
            <FunnelBar label="Filtrado Automaticamente" value={funnel.filtered ?? 0} max={funnelMax} />
            <FunnelBar label="Analisado pela IA" value={funnel.analyzed ?? 0} max={funnelMax} />
            <FunnelBar label="Oportunidades Quentes" value={funnel.hot ?? 0} max={funnelMax} highlight />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Logs Recentes</h2>
            <a href="/logs" className="text-xs text-violet-600 hover:underline">Ver todos</a>
          </div>
          <div className="space-y-3">
            {logs.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">Nenhum log ainda</p>
            ) : (
              logs.slice(0, 5).map((log) => {
                const meta = EVENT_LABELS[log.event_type] ?? { label: log.event_type, color: "bg-gray-100 text-gray-600" };
                const dotColor = EVENT_DOT_COLOR[log.event_type] ?? "bg-gray-400";
                const time = new Date(log.timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
                return (
                  <div key={log.id} className="flex items-start gap-2">
                    <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dotColor}`} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs text-gray-400">{time}</span>
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${meta.color}`}>{meta.label}</span>
                      </div>
                      <p className="text-xs text-gray-700 mt-0.5 truncate">{log.bid_type || log.title}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Editais */}
      <div className="mt-6 bg-white rounded-xl border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">Editais Monitorados</h2>
          <span className="text-xs text-gray-400">
            {filteredBids.length} resultado{filteredBids.length !== 1 ? "s" : ""}
            {hasData && bids.length !== filteredBids.length ? ` de ${bids.length}` : ""}
          </span>
        </div>

        {filteredBids.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">
            Nenhum edital encontrado para os filtros selecionados.
          </p>
        ) : (
          <div className="divide-y divide-gray-50">
            {filteredBids.slice(0, 10).map((bid) => (
              <div key={bid.id} className="flex items-center gap-3 py-3">
                <ScorePill score={bid.score} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{bid.title}</p>
                  <p className="text-xs text-gray-400 truncate">{bid.agency}</p>
                </div>
                <span className="text-[11px] font-semibold bg-violet-50 text-violet-700 px-2 py-0.5 rounded uppercase tracking-wide flex-shrink-0">
                  {bid.source_site}
                </span>
                <span className="text-xs text-gray-400 flex-shrink-0 hidden sm:block">
                  {new Date(bid.created_at).toLocaleDateString("pt-BR")}
                </span>
                <a href={bid.url} target="_blank" rel="noopener noreferrer" className="text-xs text-violet-600 hover:underline flex-shrink-0">
                  Abrir →
                </a>
              </div>
            ))}
          </div>
        )}

        {filteredBids.length > 10 && (
          <p className="text-xs text-gray-400 text-center mt-4">
            Mostrando 10 de {filteredBids.length}.{" "}
            <a href="/opportunities" className="text-violet-600 hover:underline">Ver todos →</a>
          </p>
        )}
      </div>
    </div>
  );
}
