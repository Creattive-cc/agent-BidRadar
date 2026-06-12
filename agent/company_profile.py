from pathlib import Path

PROFILE_DIR = Path("company_profile")

_SEED_NAMES = {
    "sobre.md": "Sobre a Empresa",
    "servicos.md": "Portfólio de Produtos",
    "restricoes.md": "Restrições e Fora de Escopo",
    "capacitacoes.md": "Experiência e Capacitações",
}


def ensure_profile_dir() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def read_profile_files() -> dict[str, str]:
    """Lê documentos do banco de dados. Fallback para arquivos se o banco estiver vazio."""
    try:
        from agent.models import CompanyDocument, SessionLocal
        with SessionLocal() as session:
            docs = (
                session.query(CompanyDocument)
                .filter(CompanyDocument.is_active == True)
                .all()
            )
            if docs:
                return {doc.filename: doc.content for doc in docs}
    except Exception:
        pass

    # Fallback: lê dos arquivos .md
    ensure_profile_dir()
    data: dict[str, str] = {}
    for md_file in sorted(PROFILE_DIR.glob("*.md")):
        if md_file.name == "README.md":
            continue
        data[md_file.name] = md_file.read_text(encoding="utf-8")
    return data


def seed_documents_from_files() -> int:
    """Popula company_documents a partir dos arquivos .md se a tabela estiver vazia."""
    try:
        from agent.models import CompanyDocument, SessionLocal
        with SessionLocal() as session:
            if session.query(CompanyDocument).count() > 0:
                return 0
            inserted = 0
            ensure_profile_dir()
            for md_file in sorted(PROFILE_DIR.glob("*.md")):
                if md_file.name == "README.md":
                    continue
                name = _SEED_NAMES.get(md_file.name, md_file.stem.capitalize())
                doc = CompanyDocument(
                    name=name,
                    filename=md_file.name,
                    content=md_file.read_text(encoding="utf-8"),
                )
                session.add(doc)
                inserted += 1
            session.commit()
            return inserted
    except Exception:
        return 0
