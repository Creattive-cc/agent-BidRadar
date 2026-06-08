import { useEffect, useState } from "react";
import { fetchStats, fetchLogs } from "../services/api";

function formatValue(v) {
  if (!v) return "R$ 0";
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `R$ ${(v / 1_000).toFixed(0)}k`;
  return `R$ ${v.toFixed(0)}`;
}

const EVENT_LABELS = {
  detection: { label: "Detecção", color: "bg-blue-100 text-blue-700" },
  ai_processing: { label: "IA Processando", color: "bg-amber-100 text-amber-700" },
  high_match: { label: "Alta Compatibilidade", color: "bg-green-100 text-green-700" },
  human_review: { label: "Revisão Humana", color: "bg-violet-100 text-violet-700" },
  auto_discard: { label: "Descarte Automático", color: "bg-red-100 text-red-600" },
};

const EVENT_ICONS = {
  detection: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  ),
  ai_processing: <span className="text-xs font-bold">IA</span>,
  high_match: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
  human_review: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  ),
  auto_discard: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
};

const EVENT_DOT_COLOR = {
  detection: "bg-blue-500",
  ai_processing: "bg-amber-500",
  high_match: "bg-green-500",
  human_review: "bg-violet-500",
  auto_discard: "bg-red-500",
};

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

function FunnelBar({ label, value, max, color, highlight }) {
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

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetchStats().then(setStats).catch(console.error);
    fetchLogs(5).then(setLogs).catch(console.error);
  }, []);

  const funnel = stats?.funnel ?? {};
  const max = funnel.captured || 1;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Visão Geral</h1>
        <p className="text-sm text-gray-500 mt-0.5">Bem-vindo (a) à plataforma</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { icon: KPI_ICONS.bids, label: "Editais Monitorados", value: stats?.total_bids?.toLocaleString("pt-BR") ?? "—" },
          { icon: KPI_ICONS.hours, label: "Horas de Leitura Poupadas", value: stats ? `${stats.hours_saved}h` : "—" },
          { icon: KPI_ICONS.opps, label: "Oportunidades Reais", value: stats?.opportunities?.toLocaleString("pt-BR") ?? "—" },
          { icon: KPI_ICONS.value, label: "Valor Total em Jogo", value: stats ? formatValue(stats.total_value) : "—" },
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
        {/* Funil */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-100 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Análise de Funil</h2>
          <div className="space-y-2">
            <FunnelBar label="Total Captado" value={funnel.captured ?? 0} max={max} />
            <FunnelBar label="Filtrado Automaticamente" value={funnel.filtered ?? 0} max={max} />
            <FunnelBar label="Analisado pela IA" value={funnel.analyzed ?? 0} max={max} />
            <FunnelBar label="Oportunidades Quentes" value={funnel.hot ?? 0} max={max} highlight />
          </div>
        </div>

        {/* Logs recentes */}
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
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${meta.color}`}>
                          {meta.label}
                        </span>
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
    </div>
  );
}
