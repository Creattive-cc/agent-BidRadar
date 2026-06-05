import { useEffect, useState } from "react";
import { fetchLogs } from "../services/api";

const EVENT_META = {
  detection: {
    label: "Detecção",
    badge: "bg-blue-50 text-blue-700",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    ),
    dot: "bg-blue-500",
    iconBg: "bg-blue-50 text-blue-600",
  },
  ai_processing: {
    label: "IA Processando",
    badge: "bg-amber-50 text-amber-700",
    icon: <span className="text-xs font-bold">IA</span>,
    dot: "bg-amber-500",
    iconBg: "bg-amber-50 text-amber-600",
  },
  high_match: {
    label: "Alta Compatibilidade",
    badge: "bg-green-50 text-green-700",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    dot: "bg-green-500",
    iconBg: "bg-green-50 text-green-600",
  },
  human_review: {
    label: "Revisão Humana",
    badge: "bg-violet-50 text-violet-700",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
    dot: "bg-violet-500",
    iconBg: "bg-violet-50 text-violet-600",
  },
  auto_discard: {
    label: "Descarte Automático",
    badge: "bg-red-50 text-red-600",
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    dot: "bg-red-500",
    iconBg: "bg-red-50 text-red-500",
  },
};

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    fetchLogs(limit)
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [limit]);

  const filtered = search
    ? logs.filter(
        (l) =>
          l.title.toLowerCase().includes(search.toLowerCase()) ||
          (l.bid_type ?? "").toLowerCase().includes(search.toLowerCase()) ||
          (l.product ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : logs;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Logs de Atividade da IA</h1>
        <p className="text-sm text-gray-500 mt-0.5">Acompanhe em tempo real as decisões tomadas pelo agente</p>
      </div>

      {/* Search */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar nos logs..."
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent"
          />
        </div>
        <span className="text-xs text-gray-400">{filtered.length} eventos</span>
      </div>

      {/* Timeline */}
      {loading ? (
        <p className="text-sm text-gray-400 text-center py-12">Carregando logs...</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-12">Nenhum log encontrado.</p>
      ) : (
        <div className="relative">
          <div className="absolute left-5 top-0 bottom-0 w-px bg-gray-200" />
          <div className="space-y-1">
            {filtered.map((log, i) => {
              const meta = EVENT_META[log.event_type] ?? {
                label: log.event_type,
                badge: "bg-gray-100 text-gray-600",
                icon: <span className="text-xs">?</span>,
                iconBg: "bg-gray-100 text-gray-500",
              };
              const time = new Date(log.timestamp).toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
              });
              return (
                <div key={log.id ?? i} className="flex items-start gap-4 pl-2 py-2">
                  {/* Icon circle */}
                  <div className={`z-10 w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${meta.iconBg}`}>
                    {meta.icon}
                  </div>
                  {/* Content */}
                  <div className="flex-1 bg-white border border-gray-100 rounded-lg px-4 py-3 flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs text-gray-400">{time}</span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${meta.badge}`}>
                          {meta.label}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-gray-800 truncate">{log.title}</p>
                    </div>
                    {log.product && (
                      <span className="text-xs text-gray-400 flex-shrink-0">{log.product}</span>
                    )}
                    {log.bid_type && (
                      <span className="text-xs font-medium text-gray-500 flex-shrink-0 border border-gray-200 px-2 py-0.5 rounded">
                        {log.bid_type.length > 30 ? log.bid_type.slice(0, 30) + "…" : log.bid_type}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Load more */}
      {!loading && filtered.length >= limit && (
        <div className="flex justify-center mt-6">
          <button
            onClick={() => setLimit((l) => l + 50)}
            className="px-6 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Carregar logs anteriores
          </button>
        </div>
      )}
    </div>
  );
}
