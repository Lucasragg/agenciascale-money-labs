#!/usr/bin/env python3
"""Build the public, PII-free dashboard dataset from two read-only Google Sheets."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ADS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1f4gIgN-Z6RMKYJpejrnAW7JVOVI_Hvm_KJzuGYWinSo/gviz/tq"
    "?tqx=out:csv&sheet=Bubba"
)
EVENTS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1DmGXEvfbS1_324K3PIadyP3kv1tBDqkC6NaCWw_2KfE/export"
    "?format=csv&gid=0"
)
FX_URL = "https://api.frankfurter.app/latest?from=USD&to=BRL"
TAX_MULTIPLIER = 1.1385
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


def usd_brl_rate() -> tuple[float, str]:
    fallback = parse_number(os.getenv("USD_BRL_RATE", "5.50")) or 5.50
    try:
        payload = json.loads(fetch(FX_URL, attempts=2).decode("utf-8"))
        rate = float(payload["rates"]["BRL"])
        return rate, str(payload.get("date") or "latest")
    except Exception:
        return fallback, "fallback"


def main() -> None:
    ads_source = decode_csv(fetch(ADS_URL))
    events_source = decode_csv(fetch(EVENTS_URL))
    if not ads_source or not events_source:
        raise RuntimeError("Uma das planilhas não retornou linhas de dados.")
    required = {norm(x) for x in ("Data/hora (Brasília)", "Evento", "UTM Campaign", "UTM Content")}
    if not required.issubset({norm(x) for x in events_source[0].keys()}):
        raise RuntimeError("Cabeçalhos esperados não encontrados na planilha VMFY SHEETS.")

    ads: list[dict[str, object]] = []
    campaign_names: dict[str, str] = {}
    adset_by_campaign_ad: dict[tuple[str, str], set[str]] = defaultdict(set)
    adsets_by_campaign: dict[str, set[str]] = defaultdict(set)
    for row in ads_source:
        date = parse_date(get(row, "Day", "Dia", "Date"))
        campaign = get(row, "Campaign Name", "Campanha")
        adset = get(row, "Ad Set Name", "Conjunto de anúncios")
        ad = get(row, "Ad Name", "Anúncio")
        if not date or not campaign:
            continue
        item = {
            "date": date,
            "campaign": campaign,
            "adset": adset or "Sem conjunto",
            "ad": ad or "Sem anúncio",
            "spend": round(parse_number(get(row, "Amount Spent", "Valor gasto")) * TAX_MULTIPLIER, 4),
            "impressions": int(parse_number(get(row, "Impressions", "Impressões"))),
            "clicks": int(parse_number(get(row, "Link Clicks", "Cliques no link"))),
            "pageViews": int(parse_number(get(row, "Landing Page Views", "Visualizações da página de destino"))),
        }
        ads.append(item)
        ckey, akey = norm(campaign), norm(ad)
        campaign_names[ckey] = campaign
        adset_by_campaign_ad[(ckey, akey)].add(item["adset"])
        adsets_by_campaign[ckey].add(item["adset"])

    def resolve_utm(campaign: str, ad: str) -> tuple[str, str, str] | None:
        ckey, akey = norm(campaign), norm(ad)
        if ckey not in campaign_names:
            return None
        sets = adset_by_campaign_ad.get((ckey, akey), set())
        if not sets and len(adsets_by_campaign[ckey]) == 1:
            sets = adsets_by_campaign[ckey]
        adset = next(iter(sets)) if len(sets) == 1 else "Não atribuído"
        return campaign_names[ckey], adset, ad.strip() or "Não atribuído"

    prepared: list[dict[str, object]] = []
    source_counts = {"leadRows": 0, "saleRows": 0, "matchedLeads": 0, "matchedSales": 0}
    sorted_events = sorted(events_source, key=lambda r: parse_date(get(r, "Data/hora (Brasília)")) or "")
    for row in sorted_events:
        event = norm(get(row, "Evento"))
        if event not in {"lead salvo", "venda registrada"}:
            continue
        kind = "lead" if event == "lead salvo" else "sale"
        source_counts["leadRows" if kind == "lead" else "saleRows"] += 1
        date = parse_date(get(row, "Data/hora (Brasília)"))
        if not date:
            continue
        campaign = get(row, "UTM Campaign")
        ad = get(row, "UTM Content")
        resolved = resolve_utm(campaign, ad)
        if not resolved:
            continue
        campaign, adset, ad = resolved
        prepared.append({
            "date": date,
            "type": kind,
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
            "valueUsd": round(parse_number(get(row, "Valor de conversão")), 4) if kind == "sale" else 0,
        })
        source_counts["matchedLeads" if kind == "lead" else "matchedSales"] += 1

    rate, rate_date = usd_brl_rate()
    for event in prepared:
        event["valueBrl"] = round(float(event.pop("valueUsd")) * rate, 4)

    dates = [str(row["date"]) for row in ads] + [str(row["date"]) for row in prepared]
    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "taxMultiplier": TAX_MULTIPLIER,
        "currency": "BRL",
        "fx": {"usdBrl": rate, "date": rate_date, "source": "Frankfurter/ECB" if rate_date != "fallback" else "fallback"},
        "range": {"min": min(dates) if dates else None, "max": max(dates) if dates else None},
        "sourceCounts": {**source_counts, "adRows": len(ads)},
        "ads": ads,
        "events": prepared,
    }
    target = ROOT / "public" / "data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"target": str(target), "ads": len(ads), "events": len(prepared), "counts": source_counts}))


if __name__ == "__main__":
    main()
