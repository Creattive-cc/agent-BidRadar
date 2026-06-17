"""
Backfill das 3 datas novas (data_publicacao, data_inicio_propostas, data_abertura_propostas)
para editais já salvos no banco — sem re-rodar o Gemini.

Busca os últimos N dias no PNCP e faz UPDATE apenas nos registros que já existem por URL.

Uso:
    uv run python scripts/backfill_dates.py [--days 45] [--dry-run]
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.models import Bid, SessionLocal, init_db
from agent.scraper.pncp import (
    _apply_filters,
    _build_bid_and_row,
    _fetch_all_for_modalidade,
    _item_key,
    _load_filters,
    _parse_modalidades,
)


def main(days: int, dry_run: bool) -> None:
    print(f"[backfill_dates] janela={days} dias | dry_run={dry_run}")

    init_db()

    end_date = date.today()
    data_inicial = (end_date - timedelta(days=days)).strftime("%Y%m%d")
    data_final = end_date.strftime("%Y%m%d")
    print(f"[backfill_dates] período: {data_inicial} → {data_final}")

    modalidades = _parse_modalidades()
    filters = _load_filters()

    all_items: list[dict] = []
    global_seen: set[str] = set()

    for idx, codigo in enumerate(modalidades):
        print(f"[backfill_dates] scraping modalidade {codigo}...")
        items = _fetch_all_for_modalidade(codigo, data_inicial, data_final)
        items = _apply_filters(items, filters)
        for item in items:
            key = _item_key(item)
            if key in global_seen:
                continue
            global_seen.add(key)
            all_items.append(item)
        print(f"[backfill_dates]   → {len(all_items)} itens acumulados")
        if idx < len(modalidades) - 1:
            time.sleep(1.0)

    print(f"[backfill_dates] total coletado do PNCP: {len(all_items)} itens")

    # Monta mapa url → datas extraídas do PNCP
    url_to_dates: dict[str, dict] = {}
    for item in all_items:
        result = _build_bid_and_row(
            item, codigo=int(item.get("codigoModalidadeContratacao", 0))
        )
        if result is None:
            continue
        bid, _ = result
        if bid.url:
            url_to_dates[bid.url] = {
                "deadline": bid.deadline,
                "data_publicacao": bid.data_publicacao,
                "data_inicio_propostas": bid.data_inicio_propostas,
                "data_abertura_propostas": bid.data_abertura_propostas,
            }

    print(f"[backfill_dates] {len(url_to_dates)} URLs com datas extraídas")

    # Busca bids existentes no banco cujas URLs batem com o PNCP
    updated = 0
    skipped = 0

    with SessionLocal() as session:
        urls_no_banco = [u for u in url_to_dates if u]
        rows: list[Bid] = (
            session.query(Bid).filter(Bid.url.in_(urls_no_banco)).all()
        )
        print(f"[backfill_dates] {len(rows)} bids no banco batem com URLs coletadas")

        for row in rows:
            dates = url_to_dates.get(row.url)
            if not dates:
                skipped += 1
                continue

            changed = False
            for field, val in dates.items():
                if val is not None and getattr(row, field) != val:
                    if not dry_run:
                        setattr(row, field, val)
                    changed = True

            if changed:
                updated += 1
                print(f"  ✓ [{row.id}] {row.title[:60]}")
                for field, val in dates.items():
                    if val:
                        print(f"      {field}: {val}")
            else:
                skipped += 1

        if not dry_run and updated > 0:
            session.commit()
            print(f"\n[backfill_dates] commit: {updated} bids atualizados")
        elif dry_run:
            print(f"\n[backfill_dates] DRY RUN — nenhuma alteração salva")

    print(f"\n[backfill_dates] resultado: atualizados={updated} | sem mudança={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=45, help="Janela em dias (padrão: 45)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem salvar")
    args = parser.parse_args()
    main(days=args.days, dry_run=args.dry_run)
