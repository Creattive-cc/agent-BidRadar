import { useEffect, useState } from "react";
import {
  fetchDocuments, createDocument, updateDocument, deleteDocument,
  fetchProducts, createProduct, updateProduct, deleteProduct,
  reprocessBids,
} from "../services/api";

// ── Document Card ─────────────────────────────────────────────────────────────

function DocumentCard({ doc, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(doc.name);
  const [content, setContent] = useState(doc.content);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(doc.id, { name, content });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setEditing(false);
    setName(doc.name);
    setContent(doc.content);
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 gap-4">
        {editing ? (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 text-sm font-semibold text-gray-900 border-b border-violet-400 outline-none bg-transparent"
          />
        ) : (
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-900">{doc.name}</p>
            <p className="text-[11px] text-gray-400 font-mono">{doc.filename}</p>
          </div>
        )}
        <div className="flex gap-2 flex-shrink-0">
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Salvando…" : "Salvar"}
              </button>
              <button
                onClick={handleCancel}
                className="text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancelar
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Editar
              </button>
              <button
                onClick={() => onDelete(doc.id, doc.name)}
                className="text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
              >
                Excluir
              </button>
            </>
          )}
        </div>
      </div>

      {editing ? (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full text-sm font-mono text-gray-700 p-4 outline-none resize-none bg-gray-50"
          rows={20}
        />
      ) : (
        <div className="px-4 py-3">
          <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap line-clamp-4 overflow-hidden">
            {doc.content.slice(0, 400)}{doc.content.length > 400 ? "\n…" : ""}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── New Document Modal ────────────────────────────────────────────────────────

function NewDocumentModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    if (!name.trim() || !filename.trim()) {
      setError("Nome e filename são obrigatórios.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const doc = await createDocument({
        name: name.trim(),
        filename: filename.trim(),
        content,
      });
      onCreated(doc);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Novo Documento</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Nome do documento</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex: Diferenciais Competitivos"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Filename</label>
            <input
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder="ex: diferenciais.md"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-violet-400"
            />
            <p className="text-[11px] text-gray-400 mt-1">Extensão .md será adicionada automaticamente se omitida.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Conteúdo (Markdown)</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={14}
              placeholder="Descreva o conteúdo do documento. Este texto será lido pelo Gemini ao avaliar licitações."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-violet-400 resize-none"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
          >
            Cancelar
          </button>
          <button
            onClick={handleCreate}
            disabled={saving}
            className="px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
          >
            {saving ? "Criando…" : "Criar Documento"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Reprocess Modal ──────────────────────────────────────────────────────────

function ReprocessModal({ onClose }) {
  const [minScore, setMinScore] = useState(0);
  const [status, setStatus] = useState("idle"); // idle | running | done

  async function handleReprocess() {
    setStatus("running");
    await reprocessBids(minScore);
    setStatus("done");
  }

  if (status === "done") {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center">
          <div className="w-14 h-14 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-base font-semibold text-gray-900 mb-1">Reprocessamento iniciado</h2>
          <p className="text-sm text-gray-500 mb-6">
            O Gemini 2.5 Pro está reavaliando os editais em segundo plano. Os resultados aparecerão em Oportunidades conforme forem processados.
          </p>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700"
          >
            Fechar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Reprocessar Editais</h2>
          {status === "idle" && (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
          )}
        </div>

        <div className="p-6 space-y-5">
          <p className="text-sm text-gray-600">
            O Gemini 2.5 Pro reavaliará todos os editais salvos usando o perfil e os produtos atuais. Pode levar vários minutos dependendo do volume.
          </p>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">
              Reprocessar apenas editais com score ≥ <span className="text-violet-600 font-bold">{minScore}%</span>
            </label>
            <input
              type="range"
              min={0}
              max={90}
              step={5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full accent-violet-600"
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-1">
              <span>0% (todos)</span>
              <span>50% (acima da média)</span>
              <span>90%</span>
            </div>
          </div>

          {minScore === 0 && (
            <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <svg className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <p className="text-xs text-amber-700">Reprocessará 100% dos editais. Prefira filtrar por score ≥ 50% para focar nos mais relevantes.</p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100">
          {status === "idle" && (
            <button onClick={onClose} className="px-4 py-2 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">
              Cancelar
            </button>
          )}
          <button
            onClick={handleReprocess}
            disabled={status === "running"}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-60"
          >
            {status === "running" ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Processando…
              </>
            ) : (
              "Reprocessar Editais"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Product Row ───────────────────────────────────────────────────────────────

function ProductRow({ product, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(product.name);
  const [description, setDescription] = useState(product.description);
  const [tagsRaw, setTagsRaw] = useState((product.tags || []).join(", "));
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const tags = tagsRaw.split(",").map((t) => t.trim()).filter(Boolean);
      await onSave(product.id, { name, description, tags });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setEditing(false);
    setName(product.name);
    setDescription(product.description);
    setTagsRaw((product.tags || []).join(", "));
  }

  if (editing) {
    return (
      <div className="bg-white border border-violet-200 rounded-xl p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Nome</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tags (separadas por vírgula)</label>
            <input
              value={tagsRaw}
              onChange={(e) => setTagsRaw(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Descrição</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-400 resize-none"
          />
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={handleCancel} className="text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">Cancelar</button>
          <button onClick={handleSave} disabled={saving} className="text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50">
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-start gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-semibold text-gray-900">{product.name}</p>
          {!product.is_active && (
            <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">inativo</span>
          )}
        </div>
        <p className="text-xs text-gray-500 mb-2">{product.description}</p>
        <div className="flex flex-wrap gap-1">
          {(product.tags || []).map((tag) => (
            <span key={tag} className="text-[10px] px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full font-medium">
              {tag}
            </span>
          ))}
        </div>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button onClick={() => setEditing(true)} className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">Editar</button>
        <button onClick={() => onDelete(product.id, product.name)} className="text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100">Excluir</button>
      </div>
    </div>
  );
}

function NewProductForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagsRaw, setTagsRaw] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true);
    setError("");
    try {
      const tags = tagsRaw.split(",").map((t) => t.trim()).filter(Boolean);
      const p = await createProduct({ name: name.trim(), description, tags });
      onCreated(p);
      setName(""); setDescription(""); setTagsRaw("");
      setOpen(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:border-violet-300 hover:text-violet-600 transition-colors"
      >
        + Adicionar Produto
      </button>
    );
  }

  return (
    <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 space-y-3">
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Nome</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-400 bg-white" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Tags (separadas por vírgula)</label>
          <input value={tagsRaw} onChange={(e) => setTagsRaw(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono outline-none focus:ring-2 focus:ring-violet-400 bg-white" />
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Descrição</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-400 resize-none bg-white" />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={() => setOpen(false)} className="text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">Cancelar</button>
        <button onClick={handleCreate} disabled={saving} className="text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50">
          {saving ? "Criando…" : "Criar"}
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Profile() {
  const [docs, setDocs] = useState([]);
  const [products, setProducts] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [showNewDoc, setShowNewDoc] = useState(false);
  const [showReprocess, setShowReprocess] = useState(false);
  const [docsError, setDocsError] = useState("");

  useEffect(() => {
    fetchDocuments()
      .then(setDocs)
      .catch(() => setDocsError("Erro ao carregar documentos."))
      .finally(() => setLoadingDocs(false));
    fetchProducts()
      .then(setProducts)
      .catch(() => {})
      .finally(() => setLoadingProducts(false));
  }, []);

  async function handleSaveDoc(id, data) {
    const updated = await updateDocument(id, data);
    setDocs((prev) => prev.map((d) => (d.id === id ? updated : d)));
  }

  async function handleDeleteDoc(id, name) {
    if (!window.confirm(`Excluir o documento "${name}"? Esta ação não pode ser desfeita.`)) return;
    await deleteDocument(id);
    setDocs((prev) => prev.filter((d) => d.id !== id));
  }

  async function handleSaveProduct(id, data) {
    const updated = await updateProduct(id, data);
    setProducts((prev) => prev.map((p) => (p.id === id ? updated : p)));
  }

  async function handleDeleteProduct(id, name) {
    if (!window.confirm(`Excluir o produto "${name}"?`)) return;
    await deleteProduct(id);
    setProducts((prev) => prev.filter((p) => p.id !== id));
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 p-4 md:p-6 space-y-10">

      {/* ── Documentos do Perfil ── */}
      <section>
        <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Perfil da Empresa</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Documentos lidos pelo Gemini para avaliar aderência de cada licitação.
            </p>
          </div>
          <div className="flex gap-2 flex-shrink-0 flex-wrap">
            <button
              onClick={() => setShowReprocess(true)}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 transition-colors"
              title="Reavaliar editais salvos com o perfil atual via Gemini"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reprocessar Editais
            </button>
            <button
              onClick={() => setShowNewDoc(true)}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700 transition-colors"
            >
              + Novo Documento
            </button>
          </div>
        </div>

        {docsError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-4">{docsError}</p>
        )}

        {loadingDocs ? (
          <p className="text-sm text-gray-400">Carregando documentos…</p>
        ) : docs.length === 0 ? (
          <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-xl">
            <p className="text-sm text-gray-400">Nenhum documento encontrado.</p>
            <button onClick={() => setShowNewDoc(true)} className="mt-2 text-sm text-violet-600 hover:underline">
              Criar primeiro documento
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {docs.map((doc) => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                onSave={handleSaveDoc}
                onDelete={handleDeleteDoc}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Produtos / Serviços ── */}
      <section>
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Produtos / Serviços</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Usados para calcular cobertura de tags nas oportunidades.
          </p>
        </div>

        {loadingProducts ? (
          <p className="text-sm text-gray-400">Carregando produtos…</p>
        ) : (
          <div className="space-y-3">
            {products.map((p) => (
              <ProductRow
                key={p.id}
                product={p}
                onSave={handleSaveProduct}
                onDelete={handleDeleteProduct}
              />
            ))}
            <NewProductForm onCreated={(p) => setProducts((prev) => [...prev, p])} />
          </div>
        )}
      </section>

      {showNewDoc && (
        <NewDocumentModal
          onClose={() => setShowNewDoc(false)}
          onCreated={(doc) => setDocs((prev) => [...prev, doc])}
        />
      )}

      {showReprocess && (
        <ReprocessModal onClose={() => setShowReprocess(false)} />
      )}
    </div>
  );
}
