"""
routers/data.py — 데이터 API (CRUD 4 + summary 1 + statistics 1 + export 1 + sync-public 1)
"""
import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from models.schemas import DataCreate, DataItem, DataUpdate, StatisticsResponse, SummaryResponse
from services.firestore import add_doc, delete_doc, get_all, get_one, update_doc
from services.summary import compute_statistics, compute_summary
from services.public_data import fetch_subway_stats

router = APIRouter(prefix="/api/data", tags=["데이터 관리"])


# ──────────────────────────────────────────────
# POST /api/data/sync-public — 공공데이터 동기화
# ──────────────────────────────────────────────

@router.post("/sync-public", summary="공공데이터 동기화 (서울 열린데이터광장)")
def sync_public_data(target_date: str = Query(
    default="",
    description="동기화할 연월 (YYYYMM). 미입력 시 이번 달."
)):
    """
    서울 열린데이터광장 CardSubwayStatsNew API에서 지하철 승하차 데이터를 수집하여
    Firestore에 저장합니다. 이미 존재하는 데이터(날짜+역명 동일)는 스킵합니다.

    - SEOUL_API_KEY 환경변수 필요 (https://data.seoul.go.kr 에서 발급)
    - 반환: { inserted, skipped, total, target_ym }
    """
    # 대상 연월 결정
    if not target_date:
        target_ym = "202607"
    else:
        target_ym = target_date.replace("-", "")[:6]

    # 공공API에서 데이터 수집
    try:
        rows = fetch_subway_stats(target_ym)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not rows:
        return {"inserted": 0, "skipped": 0, "total": 0, "target_ym": target_ym,
                "message": "해당 월 데이터가 없습니다. (공공API 반영 지연일 수 있음)"}

    # 기존 데이터 키 셋 (날짜+역명) — 중복 방지
    existing = get_all("data", order_by="date")
    existing_keys = {(d["date"], d.get("memo", "")) for d in existing}

    inserted = 0
    skipped = 0

    for row in rows:
        key = (row["date"], row["memo"])
        if key in existing_keys:
            skipped += 1
            continue
        add_doc("data", {
            **row,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        existing_keys.add(key)
        inserted += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total": inserted + skipped,
        "target_ym": target_ym,
        "message": f"✅ {inserted}건 추가됨, {skipped}건 중복 스킵",
    }




# ──────────────────────────────────────────────
# POST /api/data — 새 데이터 추가
# ──────────────────────────────────────────────

@router.post("", response_model=DataItem, status_code=201, summary="새 데이터 추가")
def create_data(body: DataCreate):
    """지하철 승하차 데이터 1건을 Firestore `data` 컬렉션에 추가합니다."""
    doc = {
        "date": body.date,
        "value": body.value,
        "memo": body.memo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc_id = add_doc("data", doc)
    return DataItem(id=doc_id, **body.model_dump())


# ──────────────────────────────────────────────
# GET /api/data/summary — 요약 (라우터 순서 주의: /{id} 보다 먼저 등록)
# ──────────────────────────────────────────────

@router.get("/summary", response_model=SummaryResponse, summary="데이터 요약 (AI 프롬프트 주입용)")
def get_summary():
    """Firestore `data` 컬렉션을 집계하여 기간·통계·트렌드·TOP 역을 반환합니다."""
    result = compute_summary()
    return result


# ──────────────────────────────────────────────
# GET /api/data/statistics — 추가 통계 (보너스)
# ──────────────────────────────────────────────

@router.get("/statistics", response_model=StatisticsResponse, summary="추가 통계 (노선별/요일별/월별)")
def get_statistics():
    """노선별 평균, 요일별 평균, 월별 평균 등 추가 통계를 반환합니다."""
    return compute_statistics()


# ──────────────────────────────────────────────
# GET /api/data/export — CSV/JSON 내보내기 (보너스)
# ──────────────────────────────────────────────

@router.get("/export", summary="데이터 내보내기 (CSV / JSON)")
def export_data(format: str = Query("csv", pattern="^(csv|json)$")):
    """데이터 전체를 CSV 또는 JSON 파일로 다운로드합니다."""
    docs = get_all("data", order_by="date")

    if format == "json":
        content = json.dumps(docs, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=subway_data.json"},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "date", "value", "memo"])
    for d in docs:
        writer.writerow([d.get("id", ""), d.get("date", ""), d.get("value", ""), d.get("memo", "")])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=subway_data.csv"},
    )


# ──────────────────────────────────────────────
# GET /api/data — 목록 조회
# ──────────────────────────────────────────────

@router.get("", response_model=list[DataItem], summary="데이터 목록 조회")
def list_data(limit: Optional[int] = Query(None, ge=1, le=1000, description="최대 조회 건수")):
    """Firestore `data` 컬렉션의 전체(또는 최근 N건) 데이터를 반환합니다."""
    docs = get_all("data", order_by="date", limit=limit)
    return [DataItem(id=d["id"], date=d["date"], value=d["value"], memo=d["memo"]) for d in docs]


# ──────────────────────────────────────────────
# PUT /api/data/{id} — 수정
# ──────────────────────────────────────────────

@router.put("/{doc_id}", response_model=DataItem, summary="데이터 수정")
def update_data(doc_id: str, body: DataUpdate):
    """지정한 문서를 부분 수정합니다 (변경 필드만 전송 가능)."""
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")

    ok = update_doc("data", doc_id, changes)
    if not ok:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없습니다: {doc_id}")

    updated = get_one("data", doc_id)
    return DataItem(id=updated["id"], date=updated["date"], value=updated["value"], memo=updated["memo"])


# ──────────────────────────────────────────────
# DELETE /api/data/{id} — 삭제
# ──────────────────────────────────────────────

@router.delete("/{doc_id}", status_code=204, summary="데이터 삭제")
def delete_data(doc_id: str):
    """지정한 문서를 삭제합니다."""
    ok = delete_doc("data", doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없습니다: {doc_id}")
