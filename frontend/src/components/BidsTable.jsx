import { Fragment, useState } from "react";

function scoreClass(score) {
  if (score >= 75) return "bg-emerald-100 text-emerald-800";
  if (score >= 45) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

function BidDetails({ bid }) {
  return (
    <div className="px-4 py-4 bg-slate-50 space-y-3">
      {bid.justification && (
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{bid.justification}</p>
      )}

      {bid.datas_prazos?.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Linha do Tempo
          </p>
          <div className="space-y-0">
            {bid.datas_prazos.map((d, i) => (
              <div key={i} className="relative pl-5 pb-3 last:pb-0">
                {i < bid.datas_prazos.length - 1 && (
                  <span className="absolute left-[3px] top-2.5 bottom-0 w-px bg-violet-200" />
                )}
                <span className="absolute left-0 top-1.5 w-1.5 h-1.5 rounded-full bg-violet-500" />
                <p className="text-sm">
                  <span className="font-medium text-gray-900">{d.tipo}</span>
                  <span className="text-gray-600"> — {d.data}</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {bid.itens_poc?.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
            Itens de Prova de Conceito / Amostra
          </p>
          <div className="space-y-2">
            {bid.itens_poc.map((item, i) => (
              <div key={i} className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                <p className="text-sm font-medium text-gray-900">{item.descricao}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Ano escolar: {item.ano_escolar} • Quantidade: {item.quantidade}
                </p>
                {item.observacao && item.observacao !== "não aplicável" && (
                  <p className="text-xs text-gray-500 italic mt-1">{item.observacao}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {bid.checklist_documentos?.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
            Checklist de Documentos Obrigatórios
          </p>
          <div className="space-y-2">
            {bid.checklist_documentos.map((doc, i) => (
              <div key={i} className="flex items-start gap-2">
                {doc.exigido_no_edital === true ? (
                  <svg className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-gray-300 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900">{doc.nome}</p>
                  {doc.observacao && (
                    <p className="text-xs text-gray-400">{doc.observacao}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BidsTable({ bids }) {
  const [expandedId, setExpandedId] = useState(null);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left">
          <tr>
            <th className="px-4 py-3">Titulo</th>
            <th className="px-4 py-3">Orgao / Origem</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Conteudo</th>
            <th className="px-4 py-3">Tempo (busca + analise)</th>
            <th className="px-4 py-3">Link</th>
            <th className="px-4 py-3">IA</th>
          </tr>
        </thead>
        <tbody>
          {bids.map((bid) => (
            <Fragment key={bid.id}>
              <tr className="border-t border-slate-100">
                <td className="px-4 py-3">{bid.title}</td>
                <td className="px-4 py-3">{bid.agency} ({bid.source_site})</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${scoreClass(bid.score)}`}>
                    {bid.score}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  {bid.envolve_producao_conteudo === true && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                      Produção de Conteúdo
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {(bid.find_time_seconds + bid.analysis_time_seconds).toFixed(3)}s
                </td>
                <td className="px-4 py-3">
                  <a className="text-blue-600 hover:underline" href={bid.url} target="_blank" rel="noreferrer">
                    Abrir
                  </a>
                </td>
                <td className="px-4 py-3">
                  <button
                    className="rounded bg-slate-900 px-3 py-1 text-white hover:bg-slate-700"
                    onClick={() => setExpandedId(expandedId === bid.id ? null : bid.id)}
                  >
                    {expandedId === bid.id ? "Fechar" : "Ver justificativa"}
                  </button>
                </td>
              </tr>
              {expandedId === bid.id && (
                <tr className="border-t border-slate-100">
                  <td colSpan={7} className="p-0">
                    <BidDetails bid={bid} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
