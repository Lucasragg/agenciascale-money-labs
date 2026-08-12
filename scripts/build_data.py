#!/usr/bin/env python3
"""Build the public, PII-free dashboard dataset from two read-only Google Sheets."""

from __future__ import annotations

import csv
import io
import json
import re
import time
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ADS_SOURCES = (
    (
        "Bubba",
        "BRL",
        "https://docs.google.com/spreadsheets/d/"
        "1f4gIgN-Z6RMKYJpejrnAW7JVOVI_Hvm_KJzuGYWinSo/gviz/tq"
        "?tqx=out:csv&sheet=Bubba",
    ),
    (
        "MoneyLabs Dolar",
        "USD",
        "https://docs.google.com/spreadsheets/d/"
        "1f4gIgN-Z6RMKYJpejrnAW7JVOVI_Hvm_KJzuGYWinSo/gviz/tq"
        "?tqx=out:csv&gid=1446765993",
    ),
)
EVENTS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1DmGXEvfbS1_324K3PIadyP3kv1tBDqkC6NaCWw_2KfE/export"
    "?format=csv&gid=0"
)
TAX_MULTIPLIER = 1.0
BRL_PER_USD = 5.10
CAMPAIGN_VIEWS = {
    "Bubba": ("sd | e2-cap", "bubba | e2-cap", "buba | e2-cap", "buba | pt-br | leads"),
    "Buba-EN": ("buba-ing",),
    "Mari": ("mari | e2-cap", "mari | pt-br | leads"),
    "Harumi": ("harumi | e2-cap",),
    "Lucas": ("lucas | e2-cap", "lucas | pt-br | leads"),
    "Alice": ("alice | e2-cap", "alice | pt-br | leads"),
    "Matheus": ("matheus | e2-cap", "matheus | pt-br | leads"),
    "Gabi": ("gabi | e2-cap", "gabriela | es | leads"),
    "Nick": ("nick | en | leads",),
}
EXACT_CAMPAIGN_VIEWS = {
    "[leads][abo]": "Bubba",
}
ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str, attempts: int = 4) -> bytes:
    error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MoneyLabsDashboard/1.0"})
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read()
        except Exception as exc:  # network retries belong at the integration boundary
            error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Falha ao ler fonte após {attempts} tentativas: {url}") from error


def decode_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{str(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def norm(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip().casefold()


def campaign_view(campaign: object) -> str | None:
    campaign_key = norm(campaign)
    if campaign_key in EXACT_CAMPAIGN_VIEWS:
        return EXACT_CAMPAIGN_VIEWS[campaign_key]
    return next((name for name, markers in CAMPAIGN_VIEWS.items() if any(marker in campaign_key for marker in markers)), None)


def parse_number(value: object) -> float:
    raw = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not raw:
        return 0.0
    raw = re.sub(r"[^0-9,.-]", "", raw)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def parse_date(value: object) -> str | None:
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def get(row: dict[str, str], *names: str) -> str:
    by_norm = {norm(key): value for key, value in row.items()}
    for name in names:
        if norm(name) in by_norm:
            return by_norm[norm(name)]
    return ""


def main() -> None:
    ads_sources = [(name, currency, decode_csv(fetch(url))) for name, currency, url in ADS_SOURCES]
    ads_source = [(row, name, currency) for name, currency, rows in ads_sources for row in rows]
    events_source = decode_csv(fetch(EVENTS_URL))
    if any(not rows for _, _, rows in ads_sources) or not events_source:
        raise RuntimeError("Uma das planilhas não retornou linhas de dados.")
    required = {norm(x) for x in ("Data/hora (Brasília)", "Evento", "Tipo de registro", "UTM Campaign", "UTM Content")}
    if not required.issubset({norm(x) for x in events_source[0].keys()}):
        raise RuntimeError("Cabeçalhos esperados não encontrados na planilha VMFY SHEETS.")

    cutoff_date = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    ads: list[dict[str, object]] = []
    campaign_names: dict[str, tuple[str, str]] = {}
    adset_by_campaign_ad: dict[tuple[str, str], set[str]] = defaultdict(set)
    adsets_by_campaign: dict[str, set[str]] = defaultdict(set)
    for row, source_tab, source_currency in ads_source:
        date = parse_date(get(row, "Day", "Dia", "Date"))
        campaign = get(row, "Campaign Name", "Campanha")
        adset = get(row, "Ad Set Name", "Conjunto de anúncios")
        ad = get(row, "Ad Name", "Anúncio")
        campaign_key = norm(campaign)
        view = campaign_view(campaign)
        if not date or not campaign or date > cutoff_date or not view:
            continue
        raw_spend = parse_number(get(row, "Amount Spent", "Valor gasto"))
        spend_usd = raw_spend if source_currency == "USD" else raw_spend / BRL_PER_USD
        item = {
            "date": date,
            "view": view,
            "campaign": campaign,
            "adset": adset or "Sem conjunto",
            "ad": ad or "Sem anúncio",
            "spend": round(spend_usd, 4),
            "sourceCurrency": source_currency,
            "sourceTab": source_tab,
            "impressions": int(parse_number(get(row, "Impressions", "Impressões"))),
            "clicks": int(parse_number(get(row, "Link Clicks", "Cliques no link"))),
            "pageViews": int(parse_number(get(row, "Landing Page Views", "Visualizações da página de destino"))),
        }
        ads.append(item)
        ckey, akey = norm(campaign), norm(ad)
        campaign_names[ckey] = (view, campaign)
        adset_by_campaign_ad[(ckey, akey)].add(item["adset"])
        adsets_by_campaign[ckey].add(item["adset"])

    def resolve_utm(campaign: str, ad: str) -> tuple[str, str, str, str] | None:
        ckey, akey = norm(campaign), norm(ad)
        if ckey not in campaign_names:
            return None
        sets = adset_by_campaign_ad.get((ckey, akey), set())
        if not sets and len(adsets_by_campaign[ckey]) == 1:
            sets = adsets_by_campaign[ckey]
        adset = next(iter(sets)) if len(sets) == 1 else "Não atribuído"
        view, campaign_name = campaign_names[ckey]
        return view, campaign_name, adset, ad.strip() or "Não atribuído"

    prepared: list[dict[str, object]] = []
    source_counts = {"leadRows": 0, "saleRows": 0, "matchedLeads": 0, "matchedSales": 0}
    sorted_events = sorted(events_source, key=lambda r: parse_date(get(r, "Data/hora (Brasília)")) or "")
    for row in sorted_events:
        event = norm(get(row, "Evento"))
        record_type = norm(get(row, "Tipo de registro"))
        if record_type == "aprovacao de plano":
            kind = "sale"
        elif event == "lead salvo":
            kind = "lead"
        else:
            continue
        source_counts["leadRows" if kind == "lead" else "saleRows"] += 1
        date = parse_date(get(row, "Data/hora (Brasília)"))
        if not date or date > cutoff_date:
            continue
        campaign = get(row, "UTM Campaign")
        ad = get(row, "UTM Content")
        resolved = resolve_utm(campaign, ad)
        if not resolved:
            continue
        view, campaign, adset, ad = resolved
        prepared.append({
            "date": date,
            "view": view,
            "type": kind,
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
        })
        source_counts["matchedLeads" if kind == "lead" else "matchedSales"] += 1

    dates = [str(row["date"]) for row in ads] + [str(row["date"]) for row in prepared]
    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "taxMultiplier": TAX_MULTIPLIER,
        "taxApplied": False,
        "currency": "USD",
        "brlPerUsd": BRL_PER_USD,
        "mediaSources": {"Bubba": {"currency": "BRL", "conversion": "Amount Spent / 5.10"}, "MoneyLabs Dolar": {"currency": "USD", "conversion": "Amount Spent"}},
        "views": list(CAMPAIGN_VIEWS),
        "campaignFilters": {"Bubba": ["SD | E2-CAP", "BUBBA | E2-CAP", "BUBA | E2-CAP", "Buba | PT-BR | LEADS", "[LEADS][ABO]"], "Buba-EN": ["BUBA-ING"], "Mari": ["MARI | E2-CAP", "Mari | PT-BR | LEADS"], "Harumi": ["Harumi | E2-CAP"], "Lucas": ["Lucas | E2-CAP", "Lucas | PT-BR | LEADS"], "Alice": ["Alice | E2-CAP", "Alice | PT-BR | LEADS"], "Matheus": ["MATHEUS | E2-CAP", "Matheus | PT-BR | LEADS"], "Gabi": ["GABI | E2-CAP", "Gabriela | ES | LEADS"], "Nick": ["Nick | EN | LEADS"]},
        "cutoffDate": cutoff_date,
        "range": {"min": min(dates) if dates else None, "max": max(dates) if dates else None},
        "sourceCounts": {**source_counts, "adRows": len(ads), "mediaRowsByTab": {name: sum(1 for row in ads if row["sourceTab"] == name) for name, _, _ in ADS_SOURCES}},
        "ads": ads,
        "events": prepared,
    }
    target = ROOT / "public" / "data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"target": str(target), "ads": len(ads), "events": len(prepared), "counts": source_counts}))


if __name__ == "__main__":
    main()
