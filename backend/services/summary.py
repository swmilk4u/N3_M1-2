"""
summary.py — Firestore data 컬렉션을 집계하여 요약/통계 정보 생성

⚡ 캐싱 전략 (Firestore 429 Quota 초과 방지):
   - compute_summary() / compute_statistics() 결과를 TTL_SECONDS 동안 메모리에 캐싱
   - 같은 결과를 반복 요청해도 Firestore 읽기가 발생하지 않음
   - 데이터 추가/수정/삭제 시 invalidate_cache()를 호출하여 즉시 갱신
"""
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from services.firestore import get_all

logger = logging.getLogger("summary")

# ──────────────────────────────────────────────
# 인메모리 TTL 캐시
# ──────────────────────────────────────────────

TTL_SECONDS = 600  # 10분 캐시 (필요 시 조정)

_cache: dict[str, Any] = {}
_cache_ts: dict[str, float] = {}


def _get_cached(key: str) -> Any | None:
    if key in _cache and (time.time() - _cache_ts.get(key, 0)) < TTL_SECONDS:
        remaining = int(TTL_SECONDS - (time.time() - _cache_ts[key]))
        logger.debug(f"[캐시 HIT] key={key}, 남은TTL={remaining}s → Firestore 읽기 생략")
        return _cache[key]
    return None


def _set_cached(key: str, value: Any) -> None:
    _cache[key] = value
    _cache_ts[key] = time.time()
    logger.info(f"[캐시 SET] key={key}, TTL={TTL_SECONDS}s")


def invalidate_cache() -> None:
    """데이터 추가·수정·삭제 후 캐시를 즉시 무효화합니다."""
    _cache.clear()
    _cache_ts.clear()
    logger.info("[캐시 CLEAR] 데이터 변경으로 캐시 초기화됨")


# ──────────────────────────────────────────────
# 데이터 요약 (프롬프트 주입용)
# ──────────────────────────────────────────────

def compute_summary() -> dict:
    """
    GET /api/data/summary 용 집계 (TTL 캐시 적용)
    반환 필드: period, count, metrics, trend, top_stations
    """
    cached = _get_cached("summary")
    if cached is not None:
        return cached

    logger.info("[Firestore READ] compute_summary → get_all('data') 호출")
    docs = get_all("data", order_by="date")

    if not docs:
        result = {
            "period": "데이터 없음",
            "count": 0,
            "metrics": {"average": 0, "max": 0, "min": 0, "total": 0},
            "trend": "데이터 없음",
            "top_stations": [],
        }
        _set_cached("summary", result)
        return result

    values = [int(d["value"]) for d in docs]
    dates  = [d["date"] for d in docs]

    total   = sum(values)
    avg     = round(total / len(values), 1)
    mx      = max(values)
    mn      = min(values)
    period  = f"{min(dates)} ~ {max(dates)}"

    trend = _compute_trend(docs)

    station_totals: dict[str, int] = defaultdict(int)
    for d in docs:
        station_totals[d["memo"]] += int(d["value"])
    top_stations = [
        s for s, _ in sorted(station_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    result = {
        "period": period,
        "count": len(docs),
        "metrics": {"average": avg, "max": mx, "min": mn, "total": total},
        "trend": trend,
        "top_stations": top_stations,
    }
    _set_cached("summary", result)
    logger.info(f"[Firestore READ 완료] {len(docs)}건 집계 → 캐시 저장")
    return result


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
    GET /api/data/statistics 용 집계 (TTL 캐시 적용)
    반환 필드: by_line, by_weekday, by_month
    """
    cached = _get_cached("statistics")
    if cached is not None:
        return cached

    logger.info("[Firestore READ] compute_statistics → get_all('data') 호출")
    docs = get_all("data", order_by="date")

    if not docs:
        result = {"by_line": {}, "by_weekday": {}, "by_month": {}}
        _set_cached("statistics", result)
        return result

    line_totals: dict[str, list[int]] = defaultdict(list)
    weekday_totals: dict[int, list[int]] = defaultdict(list)
    month_totals: dict[str, list[int]] = defaultdict(list)

    for d in docs:
        val  = int(d["value"])
        memo = d["memo"]

        parts = memo.split("_")
        line  = parts[-1] if len(parts) > 1 else memo
        line_totals[line].append(val)

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

    result = {
        "by_line": dict(sorted(by_line.items(), key=lambda x: x[1], reverse=True)),
        "by_weekday": {k: by_weekday.get(k, 0) for k in _WEEKDAY_KR},
        "by_month": dict(sorted(by_month.items())),
    }
    _set_cached("statistics", result)
    logger.info(f"[Firestore READ 완료] 통계 집계 → 캐시 저장")
    return result
