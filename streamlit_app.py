"""
BidRadar — App de DEMONSTRAÇÃO (Streamlit)
==========================================

Camada visual fina por cima do agente real do repositório (pasta `agent/`).
Mostra o ciclo ponta-a-ponta para apresentação:

    Coleta (PNCP)  →  Análise de aderência  →  Dashboard de oportunidades

NÃO substitui a Interface Web oficial (Jira ID-30 / React). É um "demo runner"
para validar o agente funcionando e ser publicado em Cloud Run com URL própria.

Modos:
  • Dados de exemplo (offline)  -> sempre funciona, ideal para apresentação
  • PNCP ao vivo                -> chama a API pública do PNCP em tempo real

Análise:
  • Heurística (rápida, sem credenciais)
  • Gemini / Vertex AI (se houver service_account.json + libs; cai em heurística
    automaticamente se indisponível)
"""

from __future__ import annotations

import os

# Desliga scrapers que exigem navegador (Playwright) — a demo usa só o PNCP (API pública).
os.environ.setdefault("BIDRADAR_ENABLE_BLL", "false")
os.environ.setdefault("BIDRADAR_ENABLE_CONLICITACAO", "false")
os.environ.setdefault("BIDRADAR_ENABLE_COMPRASNET", "true")
os.environ.setdefault("BIDRADAR_LLM_PROVIDER", "heuristic")

import pandas as pd
import streamlit as st

from agent.analyzer.matcher import score_bid_with_profile
from agent.company_profile import PROFILE_DIR, ensure_profile_dir, read_profile_files
from agent.config import settings
from agent.schemas import AnalyzedBid, ScrapedBid

# --------------------------------------------------------------------------- #
# Dados de exemplo (offline) — editais fictícios em formato PNCP, variados de
# propósito para evidenciar a análise separando o que adere do que não adere.
# --------------------------------------------------------------------------- #
SEED_BIDS: list[ScrapedBid] = [
    ScrapedBid(
        title="Contratação de empresa para desenvolvimento de sistema web e portal de transparência",
        agency="Prefeitura Municipal de Manaus",
        estimated_value=480000.0,
        deadline="2026-06-20T17:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/101",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Serviço de análise de dados e business intelligence (BI) para gestão pública",
        agency="Secretaria de Estado de Fazenda do Amazonas",
        estimated_value=620000.0,
        deadline="2026-06-18T14:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/102",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Sustentação e suporte técnico em TI com solução em nuvem (cloud) e software",
        agency="Tribunal de Justiça do Amazonas",
        estimated_value=350000.0,
        deadline="2026-06-25T16:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/103",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Aquisição de licenças de software de gestão e suporte de sistema",
        agency="Universidade Federal do Amazonas",
        estimated_value=210000.0,
        deadline="2026-07-01T10:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/104",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Contratação de serviços de limpeza e conservação predial",
        agency="Prefeitura Municipal de Parintins",
        estimated_value=180000.0,
        deadline="2026-06-15T09:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/105",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Aquisição de merenda escolar e transporte escolar para rede municipal",
        agency="Secretaria Municipal de Educação",
        estimated_value=950000.0,
        deadline="2026-06-12T11:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/106",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Execução de obra civil de reforma de unidade básica de saúde",
        agency="Prefeitura Municipal de Itacoatiara",
        estimated_value=1300000.0,
        deadline="2026-06-30T15:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/107",
        source_site="ComprasNet/PNCP",
    ),
    ScrapedBid(
        title="Aquisição de medicamentos básicos para a rede de atenção primária",
        agency="Secretaria de Estado de Saúde",
        estimated_value=2200000.0,
        deadline="2026-06-22T13:00:00",
        url="https://pncp.gov.br/app/editais/00000000000191/2026/108",
        source_site="ComprasNet/PNCP",
    ),
]


# --------------------------------------------------------------------------- #
# Lógica (sem Streamlit — testável isoladamente)
# --------------------------------------------------------------------------- #
def get_profile_docs() -> dict[str, str]:
    return read_profile_files()


def analyze_bids(bids: list[ScrapedBid], profile: dict[str, str]) -> list[AnalyzedBid]:
    """Pontua cada edital reusando o analisador real do agente."""
    return [score_bid_with_profile(b, profile) for b in bids]


def collect_live(days: int, modalidades: str, limit: int) -> list[ScrapedBid]:
    """Coleta ao vivo do PNCP (API pública). Importa aqui para isolar o Playwright."""
    os.environ["BIDRADAR_PNCP_MODALIDADES"] = modalidades
    from agent.scraper.pncp import scrape_pncp  # import tardio

    bids = scrape_pncp()
    return bids[:limit] if limit else bids


def priority_of(score: float) -> tuple[str, str]:
    """Retorna (rótulo, cor) a partir do score."""
    if score >= 75:
        return "ALTA", "#16a34a"
    if score >= 45:
        return "MÉDIA", "#d97706"
    return "BAIXA", "#dc2626"


def bids_to_dataframe(bids: list[AnalyzedBid]) -> pd.DataFrame:
    rows = []
    for b in bids:
        rows.append(
            {
                "Score": round(b.score, 1),
                "Prioridade": priority_of(b.score)[0],
                "Objeto": b.title,
                "Órgão": b.agency,
                "Valor estimado": b.estimated_value,
                "Prazo": (b.deadline or "")[:10],
                "Fonte": b.source_site,
                "URL": b.url,
                "Justificativa": b.justification,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    return df


def fmt_brl(v: float | None) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
def main() -> None:  # pragma: no cover (UI)
    st.set_page_config(
        page_title="BidRadar — Demo",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem;}
        .bid-card {border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px;margin-bottom:12px;background:#ffffff;}
        .bid-badge {display:inline-block;color:#fff;font-weight:700;font-size:12px;padding:2px 10px;border-radius:999px;letter-spacing:.04em;}
        .bid-title {font-size:16px;font-weight:600;margin:6px 0 2px 0;color:#111827;}
        .bid-meta {font-size:13px;color:#6b7280;}
        .score-big {font-size:30px;font-weight:800;line-height:1;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📡 BidRadar — Agente de Licitações")
    st.caption(
        "Demonstração funcional · projeto **Desenvolvimento IA (Creattive)** · "
        "coleta → análise de aderência → dashboard"
    )

    # ---------------- Sidebar (controles) ---------------- #
    with st.sidebar:
        st.header("⚙️ Controles")

        fonte = st.radio(
            "Fonte de dados",
            ["Dados de exemplo (offline)", "PNCP ao vivo"],
            help="Use 'Dados de exemplo' para a apresentação (não depende de rede).",
        )

        dias, modalidades, limite = 30, "8,6", 30
        if fonte == "PNCP ao vivo":
            modalidades = st.text_input("Modalidades PNCP", "8,6")
            limite = st.slider("Máx. de editais", 5, 60, 25, step=5)
            st.caption("8=Pregão Eletrônico · 6=Dispensa · veja a Lei 14.133.")

        analise = st.radio(
            "Motor de análise",
            ["Heurística (rápida)", "Gemini / Vertex AI"],
            help="Gemini requer service_account.json + libs; cai em heurística se indisponível.",
        )
        settings.llm_provider = (
            "vertex_gemini" if analise.startswith("Gemini") else "heuristic"
        )

        st.divider()
        score_min = st.slider("Score mínimo", 0, 100, 0, step=5)
        busca = st.text_input("Buscar por palavra", "").strip().lower()

        rodar = st.button("🔄 Rodar agente", type="primary", use_container_width=True)

    # ---------------- Execução ---------------- #
    if rodar:
        profile = get_profile_docs()
        try:
            if fonte == "PNCP ao vivo":
                with st.spinner("Consultando o PNCP em tempo real…"):
                    raw = collect_live(dias, modalidades, limite)
                if not raw:
                    st.warning(
                        "O PNCP não retornou itens agora. Usando dados de exemplo para a demo."
                    )
                    raw = SEED_BIDS
            else:
                raw = SEED_BIDS
            with st.spinner("Analisando aderência ao perfil da empresa…"):
                st.session_state["bids"] = analyze_bids(raw, profile)
            st.session_state["origem"] = fonte
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha na coleta ao vivo ({exc}). Mostrando dados de exemplo.")
            st.session_state["bids"] = analyze_bids(SEED_BIDS, profile)
            st.session_state["origem"] = "Dados de exemplo (fallback)"

    tab_dash, tab_perfil, tab_fluxo = st.tabs(
        ["📊 Oportunidades", "🏢 Perfil da empresa", "🔎 Como funciona"]
    )

    # ---------------- Aba: Dashboard ---------------- #
    with tab_dash:
        bids: list[AnalyzedBid] = st.session_state.get("bids", [])
        if not bids:
            st.info("Clique em **Rodar agente** na barra lateral para começar.")
        else:
            df = bids_to_dataframe(bids)
            df = df[df["Score"] >= score_min]
            if busca:
                mask = (
                    df["Objeto"].str.lower().str.contains(busca)
                    | df["Órgão"].str.lower().str.contains(busca)
                )
                df = df[mask]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Editais coletados", len(bids))
            c2.metric("Alta aderência (≥75)", int((df["Score"] >= 75).sum()))
            c3.metric("Score médio", f"{df['Score'].mean():.0f}" if len(df) else "—")
            total_alta = df[df["Score"] >= 75]["Valor estimado"].fillna(0).sum()
            c4.metric("Σ valor (alta aderência)", fmt_brl(float(total_alta)))

            st.caption(f"Origem: **{st.session_state.get('origem','—')}** · {len(df)} edital(is) após filtros")

            for _, row in df.iterrows():
                label, color = priority_of(row["Score"])
                st.markdown(
                    f"""
                    <div class="bid-card">
                      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
                        <div style="flex:1;">
                          <span class="bid-badge" style="background:{color};">{label}</span>
                          <div class="bid-title">{row['Objeto']}</div>
                          <div class="bid-meta">🏛️ {row['Órgão']} &nbsp;·&nbsp; 💰 {fmt_brl(row['Valor estimado'])} &nbsp;·&nbsp; 🗓️ {row['Prazo'] or '—'} &nbsp;·&nbsp; {row['Fonte']}</div>
                          <div class="bid-meta" style="margin-top:6px;">📝 {row['Justificativa']}</div>
                          <div class="bid-meta" style="margin-top:6px;"><a href="{row['URL']}" target="_blank">Abrir edital ↗</a></div>
                        </div>
                        <div style="text-align:center;color:{color};">
                          <div class="score-big">{row['Score']:.0f}</div>
                          <div class="bid-meta">/100</div>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("Ver como tabela / exportar CSV"):
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇️ Baixar CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "bidradar_oportunidades.csv",
                    "text/csv",
                )

    # ---------------- Aba: Perfil da empresa ---------------- #
    with tab_perfil:
        st.subheader("Perfil da empresa (fonte única da verdade)")
        st.caption(
            "Quem entende do negócio edita texto em `company_profile/*.md`; o agente lê e "
            "usa na análise. Edite e clique em salvar para ver o impacto na próxima execução."
        )
        ensure_profile_dir()
        files = sorted(p.name for p in PROFILE_DIR.glob("*.md"))
        if not files:
            st.warning("Nenhum arquivo .md em company_profile/.")
        else:
            escolha = st.selectbox("Arquivo", files)
            conteudo = (PROFILE_DIR / escolha).read_text(encoding="utf-8")
            novo = st.text_area("Conteúdo", conteudo, height=360)
            if st.button("💾 Salvar perfil"):
                (PROFILE_DIR / escolha).write_text(novo, encoding="utf-8")
                st.success(f"{escolha} salvo. Rode o agente novamente para reanalisar.")

    # ---------------- Aba: Como funciona ---------------- #
    with tab_fluxo:
        st.subheader("Pipeline do agente")
        st.markdown(
            """
1. **Coleta** — busca editais no **PNCP** (API pública, paginada, com rate-limit e retry).
2. **Filtros pré-IA** — descarta exclusivos ME/EPP, abaixo do valor mínimo e blacklist.
3. **Análise de aderência** — cruza o objeto do edital com o **perfil da empresa** e gera
   *score 0–100* + justificativa. Heurística por padrão; **Gemini (Vertex AI)** quando habilitado.
4. **Dashboard** — prioriza por score para o time focar nas melhores oportunidades.

> Esta demo executa as etapas **1, 3 e 4** ao vivo. As etapas de produção
> (BigQuery, Cloud Storage, Pub/Sub, extração de PDF e RAG) degradam de forma
> graciosa quando rodando fora do GCP.
            """
        )
        st.caption(
            "Mapeamento Jira: ID-28 (coleta) · ID-29 (análise IA) · ID-30 (interface) · "
            "ID-27 (infra GCP, Cloud Run)."
        )


if __name__ == "__main__":
    main()
