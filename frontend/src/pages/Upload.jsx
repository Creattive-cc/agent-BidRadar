import { useRef, useState } from "react";
import { uploadAnalyzeBid } from "../services/api";

function ScoreBadge({ score }) {
  const s = Math.round(score);
  const color =
    s >= 75
      ? { ring: "ring-green-400", text: "text-green-600", bg: "bg-green-50" }
      : s >= 50
      ? { ring: "ring-amber-400", text: "text-amber-600", bg: "bg-amber-50" }
      : { ring: "ring-red-400", text: "text-red-500", bg: "bg-red-50" };
  return (
    <div
      className={`flex flex-col items-center justify-center w-20 h-20 rounded-full ring-2 ${color.ring} ${color.bg} flex-shrink-0`}
    >
      <span className={`text-2xl font-bold leading-none ${color.text}`}>{s}%</span>
      <span className={`text-[9px] font-semibold uppercase tracking-wide ${color.text}`}>match</span>
    </div>
  );
}

export default function Upload() {
  const fileInputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [agency, setAgency] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  function handleFile(f) {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Apenas arquivos PDF são aceitos.");
      return;
    }
    setError(null);
    setResult(null);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.pdf$/i, "").replace(/[_-]/g, " "));
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    handleFile(f);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) { setError("Selecione um arquivo PDF."); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const bid = await uploadAnalyzeBid({ file, title, agency, url });
      setResult(bid);
    } catch (err) {
      setError(err.message || "Erro ao analisar o PDF.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setFile(null);
    setTitle("");
    setAgency("");
    setUrl("");
    setResult(null);
    setError(null);
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Analisar Edital por PDF</h1>
        <p className="text-sm text-gray-500 mt-1">
          Envie o PDF de qualquer edital e o Gemini avalia a aderência ao perfil da empresa.
        </p>
      </div>

      {!result && (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              dragging
                ? "border-violet-400 bg-violet-50"
                : file
                ? "border-green-400 bg-green-50"
                : "border-gray-200 bg-gray-50 hover:border-violet-300 hover:bg-violet-50/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <svg className="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm font-medium text-green-700">{file.name}</p>
                <p className="text-xs text-green-500">{(file.size / 1024).toFixed(0)} KB</p>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); reset(); }}
                  className="text-xs text-gray-400 hover:text-red-500 underline mt-1"
                >
                  Remover
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <svg className="w-10 h-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-sm text-gray-500">
                  Arraste o PDF aqui ou <span className="text-violet-600 font-medium">clique para selecionar</span>
                </p>
                <p className="text-xs text-gray-400">Máx. 20 MB</p>
              </div>
            )}
          </div>

          {/* Campos opcionais */}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Título do edital</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Preenchido automaticamente pelo nome do arquivo"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-300"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Órgão / Entidade</label>
                <input
                  type="text"
                  value={agency}
                  onChange={(e) => setAgency(e.target.value)}
                  placeholder="Ex: Prefeitura de São Paulo"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">URL do edital (opcional)</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-300"
                />
              </div>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-4 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full py-2.5 rounded-lg bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analisando com Gemini...
              </>
            ) : (
              "Analisar Edital"
            )}
          </button>
        </form>
      )}

      {/* Resultado */}
      {result && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <ScoreBadge score={result.score} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900 leading-snug">{result.title}</p>
                <p className="text-sm text-gray-500 mt-0.5">{result.agency}</p>
                {result.url && !result.url.startsWith("upload://") && (
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-violet-600 hover:underline mt-0.5 block truncate"
                  >
                    {result.url}
                  </a>
                )}
                {result.word_count && (
                  <p className="text-xs text-gray-400 mt-1">{result.word_count.toLocaleString("pt-BR")} palavras extraídas do PDF</p>
                )}
              </div>
            </div>

            {result.resumo && (
              <div className="mt-4 bg-blue-50 border border-blue-100 rounded-lg p-3">
                <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1">Resumo</p>
                <p className="text-sm text-blue-900 leading-relaxed">{result.resumo}</p>
              </div>
            )}

            {result.justification && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Análise Detalhada</p>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{result.justification}</p>
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={reset}
              className="flex-1 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Analisar outro PDF
            </button>
            <a
              href="/oportunidades"
              className="flex-1 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium text-center hover:bg-violet-700 transition-colors"
            >
              Ver em Oportunidades
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
