const API_BASE = "http://localhost:8000";

export async function fetchBids() {
  const res = await fetch(`${API_BASE}/licitacoes`);
  if (!res.ok) throw new Error("Falha ao carregar licitacoes");
  return res.json();
}

export async function runAgentOnce() {
  const res = await fetch(`${API_BASE}/agent/run-once`, { method: "POST" });
  if (!res.ok) throw new Error("Falha ao executar agente");
  return res.json();
}

export async function fetchProfileFiles() {
  const res = await fetch(`${API_BASE}/company-profile/files`);
  if (!res.ok) throw new Error("Falha ao listar arquivos de perfil");
  return res.json();
}

export async function fetchProfileContent(filename) {
  const res = await fetch(`${API_BASE}/company-profile/${filename}`);
  if (!res.ok) throw new Error("Falha ao carregar arquivo de perfil");
  return res.json();
}

export async function saveProfileContent(filename, content) {
  const res = await fetch(`${API_BASE}/company-profile/${filename}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("Falha ao salvar arquivo de perfil");
  return res.json();
}
