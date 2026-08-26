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
    "1DmGXEvfbS1_324K3PIadyP3kv1tBDqkC6NaCWw_2KfE/gviz/tq"
    "?tqx=out:csv&gid=0&headers=1"
    "&tq=select%20A%2CB%2CJ%2CK%2CL%2CM%2CN%2CS%2CAA%2CAF%2CAG%2CAH"
)
TAX_MULTIPLIER = 1.0
BRL_PER_USD = 5.10
CAMPAIGN_VIEWS = {
    "Bubba": ("sd | e2-cap", "bubba | e2-cap", "buba | e2-cap", "buba | pt-br |"),
    "Buba-EN": ("buba-ing", "buba | en | purchase"),
    "Mari": ("mari | e2-cap", "mari | pt-br | leads", "mari | pt-pt | purchase"),
    "Harumi": ("harumi | e2-cap", "harumi | purchase"),
    "Lucas": ("lucas | e2-cap", "lucas | pt-br | leads", "lucas | pt-br | purchase"),
    "Alice": ("alice | e2-cap", "alice | pt-br | leads", "alice | pt-br | purchase"),
    "Matheus": ("matheus | e2-cap", "matheus | pt-br | leads", "matheus | pt-br | purchase"),
    "Gabi": ("gabi | e2-cap", "gabi | es | lead", "gabi | es | pur", "gabriela | es | leads", "gabriela | es | purchase"),
    "Gabi PT-BR": ("gabriela | pt-br | purchase",),
    "Nick": ("nick | en | leads",),
    "Orgânico": (),
}
ORGANIC_EXPERT_VIEWS = {
    "buba": "Bubba",
    "mariane-paula": "Mari",
    "lucas-neves": "Lucas",
    "gabrielereina": "Gabi",
}
EXACT_CAMPAIGN_VIEWS = {
    "[leads][abo]": "Bubba",
    "[eu][lead][lp01-3][creative-test]": "Mari",
    "[us+ca][lead][lp01-3][creative-test]": "Mari",
    "[pt][lead][lp01-3][creative-test] — copia": "Mari",
    "[pt][lead][teste-lps] — copia": "Mari",
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


def parse_event_date_pacific(value: object) -> str | None:
    """Convert a VMFY timestamp from Brasilia time to the Meta account's Pacific date."""
    raw = str(value or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            brasilia = datetime.strptime(raw, fmt).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            return brasilia.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
        except ValueError:
            pass
    # Date-only values have no safe hour to shift; retain their declared calendar date.
    return parse_date(raw)


def get(row: dict[str, str], *names: str) -> str:
    by_norm = {norm(key): value for key, value in row.items()}
    for name in names:
        if norm(name) in by_norm:
            return by_norm[norm(name)]
    return ""


def clean_id(value: object) -> str:
    raw = str(value or "").strip()
    return raw[:-2] if raw.endswith(".0") and raw[:-2].isdigit() else raw


def main() -> None:
    ads_sources = [(name, currency, decode_csv(fetch(url))) for name, currency, url in ADS_SOURCES]
    ads_source = [(row, name, currency) for name, currency, rows in ads_sources for row in rows]
    events_source = decode_csv(fetch(EVENTS_URL))
    if any(not rows for _, _, rows in ads_sources) or not events_source:
        raise RuntimeError("Uma das planilhas não retornou linhas de dados.")
    required = {norm(x) for x in ("Data/hora (Brasília)", "Evento", "Tipo de registro", "UTM Campaign", "UTM Content")}
    if not required.issubset({norm(x) for x in events_source[0].keys()}):
        observed = ", ".join(events_source[0].keys())
        raise RuntimeError(f"Cabeçalhos esperados não encontrados na planilha VMFY SHEETS. Recebidos: {observed}")

    cutoff_date = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    mariane_campaign_ids: set[str] = set()
    mariane_adset_ids: set[str] = set()
    mariane_ad_ids: set[str] = set()
    for row in events_source:
        if norm(get(row, "Sub ID 1")) != "mariane-paula":
            continue
        campaign_id = clean_id(get(row, "Campaign ID"))
        utm_campaign_id = clean_id(get(row, "UTM Campaign"))
        adset_id = clean_id(get(row, "Ad Set ID"))
        ad_id = clean_id(get(row, "Ad ID"))
        utm_ad_id = clean_id(get(row, "UTM Content"))
        if campaign_id:
            mariane_campaign_ids.add(campaign_id)
        if utm_campaign_id:
            mariane_campaign_ids.add(utm_campaign_id)
        if adset_id:
            mariane_adset_ids.add(adset_id)
        if ad_id:
            mariane_ad_ids.add(ad_id)
        if utm_ad_id:
            mariane_ad_ids.add(utm_ad_id)

    mariane_campaign_names: set[str] = set()
    for row, _source_tab, _source_currency in ads_source:
        campaign = get(row, "Campaign Name", "Campanha")
        if not campaign:
            continue
        campaign_id = clean_id(get(row, "Campaign ID", "ID da campanha"))
        adset_id = clean_id(get(row, "Ad Set ID", "ID do conjunto de anúncios"))
        ad_id = clean_id(get(row, "Ad ID", "ID do anúncio"))
        if campaign_id in mariane_campaign_ids or adset_id in mariane_adset_ids or ad_id in mariane_ad_ids:
            mariane_campaign_names.add(norm(campaign))

    ads: list[dict[str, object]] = []
    campaign_names: dict[str, tuple[str, str]] = {}
    adset_by_campaign_ad: dict[tuple[str, str], set[str]] = defaultdict(set)
    adsets_by_campaign: dict[str, set[str]] = defaultdict(set)
    campaigns_by_id: dict[str, set[tuple[str, str]]] = defaultdict(set)
    adsets_by_id: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    ads_by_id: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    for row, source_tab, source_currency in ads_source:
        date = parse_date(get(row, "Day", "Dia", "Date"))
        campaign = get(row, "Campaign Name", "Campanha")
        adset = get(row, "Ad Set Name", "Conjunto de anúncios")
        ad = get(row, "Ad Name", "Anúncio")
        campaign_key = norm(campaign)
        view = campaign_view(campaign) or ("Mari" if campaign_key in mariane_campaign_names else None)
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
        campaign_id = clean_id(get(row, "Campaign ID", "ID da campanha"))
        adset_id = clean_id(get(row, "Ad Set ID", "ID do conjunto de anúncios"))
        ad_id = clean_id(get(row, "Ad ID", "ID do anúncio"))
        if campaign_id:
            campaigns_by_id[campaign_id].add((view, campaign))
        if adset_id:
            adsets_by_id[adset_id].add((view, campaign, item["adset"]))
        if ad_id:
            ads_by_id[ad_id].add((view, campaign, item["adset"], item["ad"]))

    def unique(mapping: dict[str, set[tuple]], identifier: object) -> tuple | None:
        values = mapping.get(clean_id(identifier), set())
        return next(iter(values)) if len(values) == 1 else None

    def resolve_utm(row: dict[str, str]) -> tuple[str, str, str, str, str] | None:
        campaign = get(row, "UTM Campaign")
        ad = get(row, "UTM Content")
        ckey, akey = norm(campaign), norm(ad)
        ad_match = unique(ads_by_id, get(row, "Ad ID")) or unique(ads_by_id, ad)
        if ad_match:
            return (*ad_match, "ad_id")

        campaign_match = unique(campaigns_by_id, get(row, "Campaign ID")) or unique(campaigns_by_id, campaign)
        if not campaign_match and ckey in campaign_names:
            campaign_match = campaign_names[ckey]
        if not campaign_match:
            return None
        view, campaign_name = campaign_match
        canonical_ckey = norm(campaign_name)
        adset_match = unique(adsets_by_id, get(row, "Ad Set ID"))
        if adset_match and (adset_match[0], adset_match[1]) != (view, campaign_name):
            adset_match = None
        sets = adset_by_campaign_ad.get((canonical_ckey, akey), set())
        if adset_match:
            adset = adset_match[2]
        elif len(sets) == 1:
            adset = next(iter(sets))
        elif len(adsets_by_campaign[canonical_ckey]) == 1:
            adset = next(iter(adsets_by_campaign[canonical_ckey]))
        else:
            adset = "Não atribuído"
        known_ad = bool(adset_by_campaign_ad.get((canonical_ckey, akey)))
        resolved_ad = ad.strip() if known_ad else "Não atribuído"
        method = "campaign_id" if clean_id(get(row, "Campaign ID")) or clean_id(campaign) in campaigns_by_id else "utm_name"
        return view, campaign_name, adset, resolved_ad, method

    prepared: list[dict[str, object]] = []
    source_counts = {"leadRows": 0, "saleRows": 0, "matchedLeads": 0, "matchedSales": 0, "idMatchedLeads": 0, "idMatchedSales": 0, "organicLeads": 0, "organicSales": 0, "organicExpertMatchedLeads": 0, "organicExpertMatchedSales": 0, "organicUnassignedLeads": 0, "organicUnassignedSales": 0, "timezoneShiftedLeads": 0, "timezoneShiftedSales": 0}
    for row in events_source:
        event = norm(get(row, "Evento"))
        record_type = norm(get(row, "Tipo de registro"))
        if record_type == "aprovacao de plano":
            kind = "sale"
        elif event == "lead salvo":
            kind = "lead"
        else:
            continue
        source_counts["leadRows" if kind == "lead" else "saleRows"] += 1
        timestamp = get(row, "Data/hora (Brasília)")
        source_date = parse_date(timestamp)
        date = parse_event_date_pacific(timestamp)
        if date and source_date and date != source_date:
            source_counts["timezoneShiftedLeads" if kind == "lead" else "timezoneShiftedSales"] += 1
        if not date or date > cutoff_date:
            continue
        has_utm = any(norm(get(row, name)) for name in ("UTM Source", "UTM Medium", "UTM Campaign", "UTM Term", "UTM Content"))
        if has_utm:
            resolved = resolve_utm(row)
        else:
            expert_view = ORGANIC_EXPERT_VIEWS.get(norm(get(row, "Sub ID 1")))
            resolved = (expert_view or "Orgânico", "Orgânico", "Orgânico", "Orgânico", "organic_expert" if expert_view else "organic")
        if not resolved:
            continue
        view, campaign, adset, ad, method = resolved
        prepared.append({
            "date": date,
            "view": view,
            "type": kind,
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
            "channel": "organic" if method in ("organic", "organic_expert") else "paid",
            "expert": view if method == "organic_expert" else ("Não identificado" if method == "organic" else view),
        })
        source_counts["matchedLeads" if kind == "lead" else "matchedSales"] += 1
        if method in ("organic", "organic_expert"):
            source_counts["organicLeads" if kind == "lead" else "organicSales"] += 1
            if method == "organic_expert":
                source_counts["organicExpertMatchedLeads" if kind == "lead" else "organicExpertMatchedSales"] += 1
            else:
                source_counts["organicUnassignedLeads" if kind == "lead" else "organicUnassignedSales"] += 1
        elif method != "utm_name":
            source_counts["idMatchedLeads" if kind == "lead" else "idMatchedSales"] += 1

    dates = [str(row["date"]) for row in ads] + [str(row["date"]) for row in prepared]
    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "taxMultiplier": TAX_MULTIPLIER,
        "taxApplied": False,
        "currency": "USD",
        "reportingTimezone": "America/Los_Angeles",
        "mediaTimezone": "America/Los_Angeles",
        "eventsSourceTimezone": "America/Sao_Paulo",
        "brlPerUsd": BRL_PER_USD,
        "mediaSources": {"Bubba": {"currency": "BRL", "conversion": "Amount Spent / 5.10"}, "MoneyLabs Dolar": {"currency": "USD", "conversion": "Amount Spent"}},
        "views": list(CAMPAIGN_VIEWS),
        "campaignFilters": {"Bubba": ["SD | E2-CAP", "BUBBA | E2-CAP", "BUBA | E2-CAP", "Buba | PT-BR", "[LEADS][ABO]", "Orgânico por Sub ID 1: buba"], "Buba-EN": ["BUBA-ING", "Buba | EN | PURCHASE"], "Mari": ["MARI | E2-CAP", "Mari | PT-BR | LEADS", "Mari | PT-PT | PURCHASE", "Sub ID 1: mariane-paula", "Orgânico por Sub ID 1: mariane-paula"], "Harumi": ["Harumi | E2-CAP", "Harumi | PURCHASE"], "Lucas": ["Lucas | E2-CAP", "Lucas | PT-BR | LEADS", "Lucas | PT-BR | PURCHASE", "Orgânico por Sub ID 1: lucas-neves"], "Alice": ["Alice | E2-CAP", "Alice | PT-BR | LEADS", "Alice | PT-BR | PURCHASE"], "Matheus": ["MATHEUS | E2-CAP", "Matheus | PT-BR | LEADS", "Matheus | PT-BR | PURCHASE"], "Gabi": ["GABI | E2-CAP", "GABI | ES | LEAD", "GABI | ES | PUR", "Gabriela | ES | LEADS", "Gabriela | ES | PURCHASE", "Orgânico por Sub ID 1: gabrielereina"], "Gabi PT-BR": ["Gabriela | PT-BR | PURCHASE"], "Nick": ["Nick | EN | LEADS"], "Orgânico": ["Sem UTMs e sem expert identificado no Sub ID 1"]},
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
