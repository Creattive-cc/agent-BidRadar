import { useEffect, useState } from "react";
import { fetchBids, fetchProducts } from "../services/api";

function daysRemaining(deadline) {
  if (!deadline) return null;
  const diff = Math.ceil((new Date(deadline) - new Date()) / 86_400_000);
  return diff;
}

function formatValue(v) {
  if (!v) return null;
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(2).replace(".", ",")}M`;
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}

function ScoreBadge({ score, onClick, clickable }) {
  const s = Math.round(score);
  const color =
    s >= 75 ? { ring: "ring-green-400", text: "text-green-600", bg: "bg-green-50" }
    : s >= 50 ? { ring: "ring-amber-400", text: "text-amber-600", bg: "bg-amber-50" }
    : { ring: "ring-red-400", text: "text-red-500", bg: "bg-red-50" };
  return (
    <div
      onClick={onClick}
      title={clickable ? "Ver análise detalhada" : undefined}
      className={`flex flex-col items-center justify-center w-16 h-16 rounded-full ring-2 ${color.ring} ${color.bg} flex-shrink-0 ${clickable ? "cursor-pointer hover:scale-105 transition-transform" : ""}`}
    >
      <span className={`text-lg font-bold leading-none ${color.text}`}>{s}%</span>
      <span className={`text-[9px] font-semibold uppercase tracking-wide ${color.text}`}>match</span>
    </div>
  );
}

function computeCoverage(bid, products) {
  const text = ((bid.title || "") + " " + (bid.agency || "")).toLowerCase();
  return products.map((p) => {
    const tags = p.tags || [];
    const matched = tags.filter((t) => text.includes(t.toLowerCase()));
    const unmatched = tags.filter((t) => !text.includes(t.toLowerCase()));
    return { ...p, matched, unmatched, hasMatch: matched.length > 0 };
  });
}

function CoverageSection({ bid, products }) {
  if (!products || products.length === 0) return null;
  const coverage = computeCoverage(bid, products);
  const covered = coverage.filter((p) => p.hasMatch);
  const notCovered = coverage.filter((p) => !p.hasMatch);

  return (
    <div className="mt-5 pt-5 border-t border-gray-100">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Cobertura por Produto
      </p>

      {covered.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
            <span className="text-[11px] font-semibold text-green-700 uppercase tracking-wide">
              O que cobrimos
            </span>
          </div>
          <div className="space-y-2">
            {covered.map((p) => (
              <div key={p.id} className="rounded-xl border border-green-200 bg-green-50 px-3 py-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-green-900">{p.name}</span>
                  <span className="text-[10px] text-green-600 font-medium">
                    {p.matched.length}/{p.tags.length} tag{p.tags.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {p.matched.map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-green-200 text-green-800">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                      {t}
                    </span>
                  ))}
                  {p.unmatched.map((t) => (
                    <span key={t} className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-green-100 text-green-500 opacity-60">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {notCovered.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-2 h-2 rounded-full bg-rose-400 flex-shrink-0" />
            <span className="text-[11px] font-semibold text-rose-500 uppercase tracking-wide">
              O que não cobrimos
            </span>
          </div>
          <div className="space-y-2">
            {notCovered.map((p) => (
              <div key={p.id} className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-rose-900">{p.name}</span>
                  <span className="text-[10px] text-rose-400 font-medium">
                    0/{p.tags.length} tag{p.tags.length !== 1 ? "s" : ""}
                  </span>
                </div>
                {p.tags.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {p.tags.map((t) => (
                      <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-rose-100 text-rose-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-300 inline-block" />
                        {t}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-rose-300 italic">Sem tags configuradas</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 mt-3 pt-2 border-t border-gray-100 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-green-400 inline-block" />
          <span className="text-[10px] text-gray-400">Tag encontrada no edital</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-green-200 inline-block" />
          <span className="text-[10px] text-gray-400">Tag do produto ausente</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-300 inline-block" />
          <span className="text-[10px] text-gray-400">Produto sem cobertura</span>
        </div>
      </div>
    </div>
  );
}

function JustificationModal({ bid, products, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl max-w-xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900 pr-4 line-clamp-2">{bid.title}</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-3 mb-4">
            <ScoreBadge score={bid.score} />
            <div>
              <p className="text-xs text-gray-500">{bid.agency}</p>
              {bid.estimated_value && (
                <p className="text-sm font-semibold text-gray-800">{formatValue(bid.estimated_value)}</p>
              )}
            </div>
          </div>

          {bid.resumo && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 mb-3">
              <p className="text-[11px] font-semibold text-blue-400 uppercase tracking-wide mb-1.5">Resumo da IA</p>
              <p className="text-sm text-blue-900 leading-relaxed">{bid.resumo}</p>
            </div>
          )}

          {bid.justification ? (
            <div className="bg-gray-50 rounded-xl px-4 py-3">
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Análise Detalhada</p>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{bid.justification}</p>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-xl px-4 py-3">
              <p className="text-sm text-gray-400 italic">Análise da IA não disponível para este edital.</p>
            </div>
          )}

          <CoverageSection bid={bid} products={products} />

          <div className="mt-4 pt-4 border-t border-gray-100">
            <a href={bid.url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-violet-600 hover:underline">
              Abrir edital original →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

const FILTERS = [
  { id: "match80", label: "Match > 80%", test: (b) => b.score >= 80 },
  { id: "highPriority", label: "Alta Prioridade", test: (b) => b.score >= 70 },
  { id: "value100k", label: "Valor > R$ 100k", test: (b) => (b.estimated_value ?? 0) >= 100_000 },
];

export default function Opportunities() {
  const [bids, setBids] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilters, setActiveFilters] = useState(new Set());
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetchBids()
      .then(setBids)
      .catch(console.error)
      .finally(() => setLoading(false));
    fetchProducts().then(setProducts).catch(console.error);
  }, []);

  function toggleFilter(id) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const filtered =
    activeFilters.size === 0
      ? bids
      : bids.filter((b) =>
          [...activeFilters].every((id) => FILTERS.find((f) => f.id === id)?.test(b))
        );

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Oportunidades Identificadas</h1>
        <p className="text-sm text-gray-500 mt-0.5">Analise os editais com maior compatibilidade com seus produtos.</p>
      </div>

      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => toggleFilter(f.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              activeFilters.has(f.id)
                ? "bg-violet-600 text-white border-violet-600"
                : "bg-white text-gray-600 border-gray-200 hover:border-violet-300"
            }`}
          >
            {f.label}
          </button>
        ))}
        {activeFilters.size > 0 && (
          <button onClick={() => setActiveFilters(new Set())} className="text-xs text-gray-400 hover:text-gray-600 underline ml-1">
            Limpar filtros
          </button>
        )}
        <span className="ml-auto text-xs text-gray-400">{filtered.length} resultado{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400 text-center py-12">Carregando oportunidades...</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-12">Nenhuma oportunidade encontrada.</p>
      ) : (
        <div className="space-y-3">
          {filtered.map((bid) => {
            const days = daysRemaining(bid.deadline);
            const urgent = days !== null && days <= 5;
            return (
              <div key={bid.id} className="bg-white border border-gray-100 rounded-xl p-5 flex items-start gap-4">
                <ScoreBadge score={bid.score} clickable onClick={() => setSelected(bid)} />

                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-gray-900">{bid.title}</h3>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{bid.agency}</p>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className="text-[11px] font-semibold bg-violet-50 text-violet-700 px-2 py-0.5 rounded uppercase tracking-wide">
                      {bid.source_site}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                    {bid.deadline && (
                      <span className={`flex items-center gap-1 ${urgent ? "text-red-500 font-medium" : ""}`}>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        {new Date(bid.deadline).toLocaleDateString("pt-BR")}
                        {days !== null && (
                          <span className={urgent ? "text-red-500" : "text-gray-400"}>
                            ({days > 0 ? `${days} dias restantes` : "Vencido"})
                          </span>
                        )}
                      </span>
                    )}
                    {bid.estimated_value && (
                      <span className="flex items-center gap-1">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                        {formatValue(bid.estimated_value)} Estimado
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <button
                    onClick={() => setSelected(bid)}
                    className="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
                  >
                    Ver Resumo da IA
                  </button>
                  <div className="flex items-center gap-2 text-gray-300">
                    <a href={bid.url} target="_blank" rel="noopener noreferrer" className="hover:text-gray-500 transition-colors">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <JustificationModal
          bid={selected}
          products={products}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
