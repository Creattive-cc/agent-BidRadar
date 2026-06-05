import { useEffect, useState } from "react";
import {
  fetchFilters, saveFilters,
  fetchProducts, createProduct, updateProduct, deleteProduct,
} from "../services/api";

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
        checked ? "bg-violet-600" : "bg-gray-200"
      }`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-6" : "translate-x-1"}`} />
    </button>
  );
}

function ProductModal({ product, onClose, onSave }) {
  const [name, setName] = useState(product?.name ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [cnaeInput, setCnaeInput] = useState(product?.cnae_codes?.join(", ") ?? "");
  const [tagInput, setTagInput] = useState(product?.tags?.join(", ") ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const data = {
        name,
        description,
        cnae_codes: cnaeInput.split(",").map((s) => s.trim()).filter(Boolean),
        tags: tagInput.split(",").map((s) => s.trim()).filter(Boolean),
      };
      const result = product
        ? await updateProduct(product.id, data)
        : await createProduct(data);
      onSave(result);
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-900 mb-4">
          {product ? "Editar Produto" : "Novo Produto"}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Nome</label>
            <input
              value={name} onChange={(e) => setName(e.target.value)} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Descrição</label>
            <textarea
              value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Códigos CNAE (separados por vírgula)</label>
            <input
              value={cnaeInput} onChange={(e) => setCnaeInput(e.target.value)} placeholder="Ex: 6204-0, 6110-8"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tags (separadas por vírgula)</label>
            <input
              value={tagInput} onChange={(e) => setTagInput(e.target.value)} placeholder="Ex: SAAS, ENTERPRISE"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 border border-gray-200 text-gray-600 text-sm font-medium py-2 rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-60">
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Filters() {
  const [filters, setFilters] = useState(null);
  const [products, setProducts] = useState([]);
  const [termInput, setTermInput] = useState("");
  const [productModal, setProductModal] = useState(null); // null | "new" | product object
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchFilters().then(setFilters).catch(console.error);
    fetchProducts().then(setProducts).catch(console.error);
  }, []);

  async function patchFilters(patch) {
    const updated = { ...filters, ...patch };
    setFilters(updated);
    setSaving(true);
    try {
      await saveFilters(patch);
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  }

  function addTerm() {
    const t = termInput.trim();
    if (!t || filters.exclusion_terms.includes(t)) return;
    patchFilters({ exclusion_terms: [...filters.exclusion_terms, t] });
    setTermInput("");
  }

  function removeTerm(term) {
    patchFilters({ exclusion_terms: filters.exclusion_terms.filter((t) => t !== term) });
  }

  async function handleDeleteProduct(id) {
    if (!confirm("Remover produto?")) return;
    await deleteProduct(id);
    setProducts((prev) => prev.filter((p) => p.id !== id));
  }

  function handleProductSaved(result) {
    setProducts((prev) => {
      const idx = prev.findIndex((p) => p.id === result.id);
      return idx >= 0 ? prev.map((p) => (p.id === result.id ? result : p)) : [...prev, result];
    });
    setProductModal(null);
  }

  if (!filters) return <div className="p-8 text-sm text-gray-400">Carregando...</div>;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Filtros e Regras</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure aqui os indicadores a serem analisados</p>
      </div>

      {/* Filter panels */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {/* Termos de exclusão */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
              <span className="text-sm font-semibold text-gray-800">Termos de Exclusão</span>
            </div>
            <Toggle
              checked={filters.enable_exclusion_terms}
              onChange={(v) => patchFilters({ enable_exclusion_terms: v })}
            />
          </div>
          <p className="text-xs text-gray-400 mb-3">Descarte automaticamente editais que contenham estes termos.</p>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {filters.exclusion_terms.map((term) => (
              <span key={term} className="flex items-center gap-1 bg-red-50 text-red-600 text-xs px-2 py-1 rounded-full">
                {term}
                <button onClick={() => removeTerm(term)} className="hover:text-red-800 ml-0.5">×</button>
              </span>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <input
              value={termInput}
              onChange={(e) => setTermInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTerm()}
              placeholder="Adicionar palavra-chave..."
              className="flex-1 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-400"
            />
            <button onClick={addTerm} className="w-7 h-7 bg-violet-100 hover:bg-violet-200 text-violet-600 rounded-full flex items-center justify-center transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
        </div>

        {/* Valor mínimo */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <span className="text-sm font-semibold text-gray-800">Valor Mínimo Estimado</span>
            </div>
            <Toggle
              checked={filters.enable_min_value}
              onChange={(v) => patchFilters({ enable_min_value: v })}
            />
          </div>
          <p className="text-xs text-gray-400 mb-3">Filtrar editais com valor global acima de:</p>
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden focus-within:ring-2 focus-within:ring-violet-400">
            <span className="px-3 py-2.5 text-xs text-gray-400 border-r border-gray-200 bg-gray-50">R$</span>
            <input
              type="number"
              value={filters.min_value ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, min_value: e.target.value ? Number(e.target.value) : null }))}
              onBlur={(e) => e.target.value && patchFilters({ min_value: Number(e.target.value) })}
              placeholder="15000"
              className="flex-1 px-3 py-2.5 text-sm focus:outline-none"
            />
          </div>
        </div>

        {/* Capital social */}
        <div className="bg-white border border-gray-100 rounded-xl p-5 opacity-70">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              <span className="text-sm font-semibold text-gray-800">Exigência de Capital Social</span>
            </div>
            <Toggle
              checked={filters.enable_capital_social}
              onChange={(v) => patchFilters({ enable_capital_social: v })}
            />
          </div>
          <p className="text-xs text-gray-400 mb-3">Limite máximo aceitável para o capital social exigido (%):</p>
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
            <input
              type="number"
              value={filters.max_capital_social_pct ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, max_capital_social_pct: e.target.value ? Number(e.target.value) : null }))}
              onBlur={(e) => patchFilters({ max_capital_social_pct: e.target.value ? Number(e.target.value) : null })}
              placeholder="Ex: 10"
              disabled={!filters.enable_capital_social}
              className="flex-1 px-3 py-2.5 text-sm focus:outline-none disabled:bg-gray-50"
            />
            <span className="px-3 py-2.5 text-xs text-gray-400 border-l border-gray-200 bg-gray-50">%</span>
          </div>
        </div>
      </div>

      {/* Products */}
      <div className="bg-white border border-gray-100 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <h2 className="text-base font-semibold text-gray-900">Catálogo de Produtos (Matching)</h2>
            </div>
            <p className="text-xs text-gray-400 mt-0.5 ml-6">A IA utiliza estas descrições para encontrar oportunidades relevantes.</p>
          </div>
          <button
            onClick={() => setProductModal("new")}
            className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Novo Produto
          </button>
        </div>

        {products.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">Nenhum produto cadastrado. Clique em "+ Novo Produto" para começar.</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {products.map((p) => (
              <div key={p.id} className="flex items-start gap-4 py-4">
                <div className="w-9 h-9 rounded-full bg-violet-50 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{p.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{p.description}</p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {p.cnae_codes.map((c) => (
                      <span key={c} className="text-[10px] font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded uppercase">
                        CNAE {c}
                      </span>
                    ))}
                    {p.tags.map((t) => (
                      <span key={t} className="text-[10px] font-semibold bg-violet-50 text-violet-600 px-2 py-0.5 rounded uppercase">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setProductModal(p)} className="text-gray-400 hover:text-violet-600 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button onClick={() => handleDeleteProduct(p.id)} className="text-gray-400 hover:text-red-500 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {productModal && (
        <ProductModal
          product={productModal === "new" ? null : productModal}
          onClose={() => setProductModal(null)}
          onSave={handleProductSaved}
        />
      )}
    </div>
  );
}
