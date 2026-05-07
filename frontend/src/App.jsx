import { useEffect, useState } from "react";
import { fetchBids, runAgentOnce } from "./services/api";
import BidsTable from "./components/BidsTable";
import ProfileEditor from "./components/ProfileEditor";

export default function App() {
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedJustification, setSelectedJustification] = useState("");

  async function refreshBids() {
    setLoading(true);
    try {
      const data = await fetchBids();
      setBids(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshBids().catch(console.error);
  }, []);

  async function handleRunAgent() {
    await runAgentOnce();
    await refreshBids();
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">BidRadar</h1>
          <p className="text-slate-600">Dashboard de licitacoes e aderencia com IA</p>
        </div>
        <button
          onClick={handleRunAgent}
          className="rounded bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-500"
        >
          Rodar agente agora
        </button>
      </header>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Licitacoes analisadas</h2>
        {loading ? <p>Carregando...</p> : <BidsTable bids={bids} onSeeJustification={setSelectedJustification} />}
      </section>

      {selectedJustification && (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-lg font-semibold">Justificativa completa da IA</h3>
          <p className="text-slate-700">{selectedJustification}</p>
        </section>
      )}

      <section>
        <ProfileEditor />
      </section>
    </main>
  );
}
