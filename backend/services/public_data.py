"""
services/public_data.py — 서울 열린데이터광장 지하철 승하차 API 연동
API: CardSubwayTime (서울시 지하철 호선별 역별 시간대별 승객 현황)
문서: https://data.seoul.go.kr/dataList/OA-12252/S/1/datasetView.do
"""
import os
from typing import Any

import requests

_SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"
_SERVICE_NAME = "CardSubwayTime"


def fetch_subway_stats(target_ym: str, page_size: int = 1000) -> list[dict[str, Any]]:
    """
    서울 열린데이터광장 CardSubwayTime API에서 특정 월(YYYYMM)의
    전체 지하철 역별 승하차 합계 데이터를 수집합니다.

    Args:
        target_ym: 조회 대상 연월 (예: "202512" 또는 "202401")
        page_size: 한 번에 가져올 건수 (기본 1000)

    Returns:
        [{"date": "2025-12-01", "value": 1284920, "memo": "강남역_2호선"}, ...]
    """
    api_key = os.getenv("SEOUL_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SEOUL_API_KEY 환경변수가 설정되지 않았습니다. "
            "Render 대시보드의 Environment 설정에서 SEOUL_API_KEY를 추가해 주세요."
        )

    # 6자리 YYYYMM 형식 검증
    target_ym = target_ym.replace("-", "")[:6]
    if len(target_ym) != 6:
        target_ym = "202512"  # 기본값

    results: list[dict[str, Any]] = []
    start_idx = 1

    while True:
        end_idx = start_idx + page_size - 1
        url = (
            f"{_SEOUL_API_BASE}/{api_key}/json/{_SERVICE_NAME}"
            f"/{start_idx}/{end_idx}/{target_ym}/"
        )

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"공공API 요청 실패: {e}") from e

        # 최상위 에러 응답 체크
        if "RESULT" in data:
            result_info = data["RESULT"]
            code = result_info.get("CODE", "")
            msg = result_info.get("MESSAGE", "알 수 없는 오류")
            if code == "INFO-200":
                # 해당 월 데이터 없음
                break
            if code != "INFO-000":
                raise RuntimeError(f"공공API 오류 [{code}]: {msg}")

        service_data = data.get(_SERVICE_NAME, {})
        result_code = service_data.get("RESULT", {})
        if isinstance(result_code, dict):
            code = result_code.get("CODE", "")
            if code not in ("INFO-000", "INFO-200"):
                msg = result_code.get("MESSAGE", "알 수 없는 오류")
                raise RuntimeError(f"공공API 오류 [{code}]: {msg}")
            if code == "INFO-200":
                break

        rows = service_data.get("row", [])
        if not rows:
            break

        for row in rows:
            parsed = _parse_row(row)
            if parsed:
                results.append(parsed)

        total_count = service_data.get("list_total_count", 0)
        if end_idx >= total_count:
            break

        start_idx = end_idx + 1

    return results


def _parse_row(row: dict) -> dict[str, Any] | None:
    """
    CardSubwayTime 응답 행(각 역의 시간대별 승하차 인원)을 파싱하여
    해당 월 전체 승하차 인원 합계를 계산합니다.
    """
    try:
        use_mm = str(row.get("USE_MM", "")).strip()
        if len(use_mm) != 6:
            return None

        # YYYYMM -> YYYY-MM-01
        date_str = f"{use_mm[:4]}-{use_mm[4:6]}-01"

        line = str(row.get("SBWY_ROUT_LN_NM", "")).strip()
        station = str(row.get("STTN", "")).strip()
        if not station or not line:
            return None

        if not station.endswith("역"):
            station = station + "역"
        line = line.lstrip("0")

        memo = f"{station}_{line}"

        # 시간대별 승차/하차 인원 전체 합산
        total_passengers = 0
        for k, v in row.items():
            if k.startswith("HR_") and (k.endswith("_GET_ON_NOPE") or k.endswith("_GET_OFF_NOPE")):
                try:
                    total_passengers += int(float(v or 0))
                except (ValueError, TypeError):
                    pass

        if total_passengers <= 0:
            return None

        return {"date": date_str, "value": total_passengers, "memo": memo}

    except Exception:
        return None
