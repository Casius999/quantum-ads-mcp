"""Pure campaign analytics: anomalies, pacing, search-term mining, GA4 reconciliation.

Everything here takes plain rows (already fetched) and returns findings with the evidence and,
where an action follows, the ready-to-apply ``MutateOperation`` JSON for ``ads.mutate`` — so the
agent goes from insight to change in one step.
"""

from __future__ import annotations

import calendar
import datetime as dt
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

MICROS = 1_000_000


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def robust_z(history: Sequence[float], value: float) -> float:
    """Robust z-score of ``value`` against ``history`` (median / MAD, 1.4826 scaling)."""
    if len(history) < 3:
        return 0.0
    median = statistics.median(history)
    mad = statistics.median(abs(x - median) for x in history) * 1.4826
    if mad == 0:
        spread = statistics.pstdev(history)
        if spread == 0:
            return 0.0 if value == median else (10.0 if value > median else -10.0)
        mad = spread
    return (value - median) / mad


def detect_anomalies(
    rows: Iterable[Mapping[str, Any]],
    *,
    metrics: Sequence[str] = ("cost_micros", "conversions", "clicks"),
    threshold: float = 3.5,
) -> list[dict[str, object]]:
    """Flag each campaign whose latest day deviates from its own history on any metric.

    ``rows``: flattened GAQL rows with ``campaign.id``, ``campaign.name``, ``segments.date`` and
    ``metrics.<name>``. The latest date present is compared against the earlier days.
    """
    series: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    names: dict[str, str] = {}
    for row in rows:
        campaign = str(row.get("campaign.id"))
        names[campaign] = str(row.get("campaign.name", campaign))
        day = str(row.get("segments.date"))
        for metric in metrics:
            series[campaign][metric][day] = _num(row.get(f"metrics.{metric}"))
    findings: list[dict[str, object]] = []
    for campaign, by_metric in series.items():
        for metric, by_day in by_metric.items():
            days = sorted(by_day)
            if len(days) < 4:
                continue
            latest, history = by_day[days[-1]], [by_day[d] for d in days[:-1]]
            score = robust_z(history, latest)
            if abs(score) >= threshold:
                findings.append(
                    {
                        "campaign_id": campaign,
                        "campaign": names[campaign],
                        "metric": metric,
                        "date": days[-1],
                        "value": latest,
                        "baseline_median": statistics.median(history),
                        "robust_z": round(score, 2),
                        "direction": "spike" if score > 0 else "drop",
                    }
                )
    return sorted(findings, key=lambda f: -abs(float(str(f["robust_z"]))))


def pacing(
    rows: Iterable[Mapping[str, Any]], *, today: dt.date, tolerance: float = 0.15
) -> list[dict[str, object]]:
    """Month-to-date spend vs the daily budget, projected to month end.

    ``rows``: per-campaign month-to-date ``metrics.cost_micros`` and
    ``campaign_budget.amount_micros`` (daily). Google may spend up to 2x a daily budget on a
    day but bills at most 30.4x per month, so the monthly cap is ``daily * 30.4``.
    """
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    elapsed = max(today.day - 1, 1)  # complete days this month
    out: list[dict[str, object]] = []
    for row in rows:
        spend = _num(row.get("metrics.cost_micros")) / MICROS
        daily = _num(row.get("campaign_budget.amount_micros")) / MICROS
        if daily <= 0:
            continue
        expected = daily * elapsed
        projected = spend / elapsed * days_in_month
        cap = daily * 30.4
        ratio = spend / expected if expected else 0.0
        status = "on_pace"
        if ratio > 1 + tolerance:
            status = "overpacing"
        elif ratio < 1 - tolerance:
            status = "underpacing"
        out.append(
            {
                "campaign_id": str(row.get("campaign.id")),
                "campaign": str(row.get("campaign.name")),
                "daily_budget": round(daily, 2),
                "spend_to_date": round(spend, 2),
                "expected_to_date": round(expected, 2),
                "projected_month": round(projected, 2),
                "monthly_cap": round(cap, 2),
                "pace_ratio": round(ratio, 2),
                "status": status,
            }
        )
    return sorted(out, key=lambda r: -abs(float(str(r["pace_ratio"])) - 1))


def mine_search_terms(
    rows: Iterable[Mapping[str, Any]],
    *,
    customer_id: str,
    keywords: Iterable[str] = (),
    min_waste_cost_micros: int = 5 * MICROS,
    min_conversions: float = 1.0,
) -> dict[str, list[dict[str, object]]]:
    """Wasted terms -> campaign negative keywords; converting untargeted terms -> new keywords.

    ``rows``: ``search_term_view`` rows with ``search_term_view.search_term``, ``campaign.id``,
    ``ad_group.id`` and metrics ``cost_micros``, ``clicks``, ``conversions``.
    """
    targeted = {k.strip().lower() for k in keywords}
    negatives: list[dict[str, object]] = []
    additions: list[dict[str, object]] = []
    for row in rows:
        term = str(row.get("search_term_view.search_term", "")).strip()
        if not term:
            continue
        cost = _num(row.get("metrics.cost_micros"))
        conversions = _num(row.get("metrics.conversions"))
        campaign = f"customers/{customer_id}/campaigns/{row.get('campaign.id')}"
        ad_group = f"customers/{customer_id}/adGroups/{row.get('ad_group.id')}"
        evidence = {
            "term": term,
            "cost": round(cost / MICROS, 2),
            "clicks": _num(row.get("metrics.clicks")),
            "conversions": conversions,
        }
        if conversions == 0 and cost >= min_waste_cost_micros:
            negatives.append(
                {
                    **evidence,
                    "operation": {
                        "campaign_criterion_operation": {
                            "create": {
                                "campaign": campaign,
                                "negative": True,
                                "keyword": {"text": term, "match_type": "EXACT"},
                            }
                        }
                    },
                }
            )
        elif conversions >= min_conversions and term.lower() not in targeted:
            additions.append(
                {
                    **evidence,
                    "operation": {
                        "ad_group_criterion_operation": {
                            "create": {
                                "ad_group": ad_group,
                                "status": "ENABLED",
                                "keyword": {"text": term, "match_type": "PHRASE"},
                            }
                        }
                    },
                }
            )
    negatives.sort(key=lambda n: -float(str(n["cost"])))
    additions.sort(key=lambda a: -float(str(a["conversions"])))
    return {"negative_keywords": negatives, "new_keywords": additions}


def reconcile(
    ads_rows: Iterable[Mapping[str, Any]],
    ga4_rows: Iterable[Mapping[str, Any]],
    *,
    tolerance: float = 0.2,
) -> dict[str, object]:
    """Daily Google Ads conversions vs GA4 key events from google / cpc traffic.

    ``ads_rows``: ``segments.date`` + ``metrics.conversions``; ``ga4_rows``: ``date`` (YYYYMMDD)
    + ``keyEvents``. Days whose relative gap exceeds ``tolerance`` are flagged.
    """
    ads: dict[str, float] = defaultdict(float)
    for row in ads_rows:
        ads[str(row.get("segments.date"))] += _num(row.get("metrics.conversions"))
    ga4: dict[str, float] = defaultdict(float)
    for row in ga4_rows:
        raw = str(row.get("date", ""))
        day = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else raw
        ga4[day] += _num(row.get("keyEvents"))
    days = []
    for day in sorted(set(ads) | set(ga4)):
        a, g = ads.get(day, 0.0), ga4.get(day, 0.0)
        gap = (a - g) / max(a, g) if max(a, g) else 0.0
        days.append(
            {
                "date": day,
                "ads_conversions": a,
                "ga4_key_events": g,
                "gap": round(gap, 3),
                "flag": abs(gap) > tolerance,
            }
        )
    total_a, total_g = sum(ads.values()), sum(ga4.values())
    return {
        "days": days,
        "ads_total": total_a,
        "ga4_total": total_g,
        "total_gap": round((total_a - total_g) / max(total_a, total_g), 3)
        if max(total_a, total_g)
        else 0.0,
        "flagged_days": sum(1 for d in days if d["flag"]),
    }
