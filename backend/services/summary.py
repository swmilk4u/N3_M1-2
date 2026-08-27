"""
summary.py — Firestore data 컬렉션을 집계하여 요약/통계 정보 생성
"""
from collections import defaultdict
from datetime import datetime

from services.firestore import get_all


# ──────────────────────────────────────────────
# 데이터 요약 (프롬프트 주입용)
# ──────────────────────────────────────────────

def compute_summary() -> dict:
    """
    GET /api/data/summary 용 집계
    반환 필드: period, count, metrics, trend, top_stations
    """
    docs = get_all("data", order_by="date")

    if not docs:
        return {
            "period": "데이터 없음",
            "count": 0,
            "metrics": {"average": 0, "max": 0, "min": 0, "total": 0},
            "trend": "데이터 없음",
            "top_stations": [],
        }

    values = [int(d["value"]) for d in docs]
    dates  = [d["date"] for d in docs]

    total   = sum(values)
    avg     = round(total / len(values), 1)
    mx      = max(values)
    mn      = min(values)
    period  = f"{min(dates)} ~ {max(dates)}"

    # 트렌드: 최근 30일 평균 vs 전 30일 평균
    trend = _compute_trend(docs)

    # top_stations: memo 기준 상위 5개 (승하차 합계 기준)
    station_totals: dict[str, int] = defaultdict(int)
    for d in docs:
        station_totals[d["memo"]] += int(d["value"])
    top_stations = [
        s for s, _ in sorted(station_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    return {
        "period": period,
        "count": len(docs),
        "metrics": {"average": avg, "max": mx, "min": mn, "total": total},
        "trend": trend,
        "top_stations": top_stations,
    }


def _compute_trend(docs: list[dict]) -> str:
    """최근 30일 vs 직전 30일 평균 비교로 트렌드 문자열 생성"""
    sorted_docs = sorted(docs, key=lambda d: d["date"], reverse=True)

    recent = sorted_docs[:30]
    prev   = sorted_docs[30:60]

    if not recent:
        return "데이터 부족"

    recent_avg = sum(int(d["value"]) for d in recent) / len(recent)

    if not prev:
        return f"데이터 {len(recent)}건 (비교 불가)"

    prev_avg = sum(int(d["value"]) for d in prev) / len(prev)

    if prev_avg == 0:
        return "이전 데이터 없음"

    change_pct = round((recent_avg - prev_avg) / prev_avg * 100, 1)

    if change_pct > 3:
        return f"상승 (전월 대비 +{change_pct}%)"
    elif change_pct < -3:
        return f"하락 (전월 대비 {change_pct}%)"
    else:
        return f"보합 (전월 대비 {change_pct:+.1f}%)"


# ──────────────────────────────────────────────
# 추가 통계 (보너스: /api/data/statistics)
# ──────────────────────────────────────────────

_WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

def compute_statistics() -> dict:
    """
    GET /api/data/statistics 용 집계
    반환 필드: by_line, by_weekday, by_month
    """
    docs = get_all("data", order_by="date")

    if not docs:
        return {"by_line": {}, "by_weekday": {}, "by_month": {}}

    # 노선별 평균
    line_totals: dict[str, list[int]] = defaultdict(list)
    weekday_totals: dict[int, list[int]] = defaultdict(list)
    month_totals: dict[str, list[int]] = defaultdict(list)

    for d in docs:
        val  = int(d["value"])
        memo = d["memo"]

        # 노선 추출 (예: "강남역_2호선" → "2호선")
        parts = memo.split("_")
        line  = parts[-1] if len(parts) > 1 else memo
        line_totals[line].append(val)

        # 요일별
        try:
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
            weekday_totals[dt.weekday()].append(val)
            month_totals[d["date"][:7]].append(val)
        except ValueError:
            pass

    by_line = {
        line: round(sum(vals) / len(vals))
        for line, vals in line_totals.items()
    }
    by_weekday = {
        _WEEKDAY_KR[wd]: round(sum(vals) / len(vals))
        for wd, vals in weekday_totals.items()
    }
    by_month = {
        month: round(sum(vals) / len(vals))
        for month, vals in month_totals.items()
    }

    return {
        "by_line": dict(sorted(by_line.items(), key=lambda x: x[1], reverse=True)),
        "by_weekday": {k: by_weekday.get(k, 0) for k in _WEEKDAY_KR},
        "by_month": dict(sorted(by_month.items())),
    }
