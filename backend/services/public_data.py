"""
services/public_data.py — 서울 열린데이터광장 지하철 승하차 API 연동
API: CardSubwayStatsNew (서울시 지하철 승하차 인원 정보)
문서: https://data.seoul.go.kr/dataList/OA-12252/S/1/datasetView.do
"""
import os
from typing import Any

import requests

# 서울 열린데이터광장 API 기본 URL
_SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"
_SERVICE_NAME = "CardSubwayStatsNew"


def fetch_subway_stats(target_ym: str, page_size: int = 1000) -> list[dict[str, Any]]:
    """
    서울 열린데이터광장에서 특정 월(YYYYMM)의 지하철 승하차 데이터를 수집합니다.

    Args:
        target_ym: 조회 대상 연월 (예: "202408")
        page_size: 한 번에 가져올 건수 (최대 1000)

    Returns:
        [{"date": "2024-08-01", "value": 182345, "memo": "강남역_2호선"}, ...]
    """
    api_key = os.getenv("SEOUL_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SEOUL_API_KEY 환경변수가 설정되지 않았습니다. "
            "https://data.seoul.go.kr 에서 인증키를 발급받아 설정해 주세요."
        )

    results: list[dict[str, Any]] = []
    start_idx = 1

    while True:
        end_idx = start_idx + page_size - 1
        # API URL: {base}/{key}/json/{service}/{start}/{end}/{USE_DT}
        url = (
            f"{_SEOUL_API_BASE}/{api_key}/json/{_SERVICE_NAME}"
            f"/{start_idx}/{end_idx}/{target_ym}"
        )

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"공공API 요청 실패: {e}") from e

        service_data = data.get(_SERVICE_NAME, {})

        # 에러 응답 처리
        result_code = service_data.get("RESULT", {})
        if isinstance(result_code, dict):
            code = result_code.get("CODE", "")
            if code not in ("INFO-000", "INFO-200"):
                msg = result_code.get("MESSAGE", "알 수 없는 오류")
                if code == "INFO-200":
                    break  # 데이터 없음 (정상 종료)
                raise RuntimeError(f"공공API 오류 [{code}]: {msg}")

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
    API 응답 행을 내부 형식으로 변환합니다.

    API 필드:
      USE_DT: 이용일자 (YYYYMMDD)
      LINE_NUM: 호선명 (예: "2호선")
      SUB_STA_NM: 역명 (예: "강남")
      RIDE_PASGR_NUM: 승차 인원
      ALIGHT_PASGR_NUM: 하차 인원
    """
    try:
        use_dt = str(row.get("USE_DT", "")).strip()
        if len(use_dt) != 8:
            return None

        # YYYYMMDD → YYYY-MM-DD
        date_str = f"{use_dt[:4]}-{use_dt[4:6]}-{use_dt[6:8]}"

        line = str(row.get("LINE_NUM", "")).strip()
        station = str(row.get("SUB_STA_NM", "")).strip()
        if not station or not line:
            return None

        # 역명 정규화: "강남" → "강남역", 노선: "02호선" → "2호선"
        if not station.endswith("역"):
            station = station + "역"
        line = line.lstrip("0")  # 앞자리 0 제거 (02호선 → 2호선)

        memo = f"{station}_{line}"

        ride = int(float(row.get("RIDE_PASGR_NUM", 0) or 0))
        alight = int(float(row.get("ALIGHT_PASGR_NUM", 0) or 0))
        value = ride + alight

        if value <= 0:
            return None

        return {"date": date_str, "value": value, "memo": memo}

    except (ValueError, TypeError):
        return None
