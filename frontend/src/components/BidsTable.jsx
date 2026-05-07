function scoreClass(score) {
  if (score >= 75) return "bg-emerald-100 text-emerald-800";
  if (score >= 45) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

export default function BidsTable({ bids, onSeeJustification }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left">
          <tr>
            <th className="px-4 py-3">Titulo</th>
            <th className="px-4 py-3">Orgao / Origem</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Tempo (busca + analise)</th>
            <th className="px-4 py-3">Link</th>
            <th className="px-4 py-3">IA</th>
          </tr>
        </thead>
        <tbody>
          {bids.map((bid) => (
            <tr key={bid.id} className="border-t border-slate-100">
              <td className="px-4 py-3">{bid.title}</td>
              <td className="px-4 py-3">{bid.agency} ({bid.source_site})</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${scoreClass(bid.score)}`}>
                  {bid.score}%
                </span>
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
                  onClick={() => onSeeJustification(bid.justification)}
                >
                  Ver justificativa
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
