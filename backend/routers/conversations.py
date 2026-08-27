"""
routers/conversations.py — 대화 기록 API
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import ConversationCreate, ConversationListItem, ConversationResponse
from services.firestore import add_doc, delete_doc, get_all, get_one

router = APIRouter(prefix="/api/conversations", tags=["대화 기록"])


# ──────────────────────────────────────────────
# POST /api/conversations — 대화 저장
# ──────────────────────────────────────────────

@router.post("", response_model=ConversationResponse, status_code=201, summary="대화 저장")
def create_conversation(body: ConversationCreate):
    """새 대화 기록을 Firestore `conversations` 컬렉션에 저장합니다."""
    created_at = datetime.now(timezone.utc).isoformat()
    doc = {
        "title": body.title,
        "messages": [m.model_dump() for m in body.messages],
        "created_at": created_at,
    }
    doc_id = add_doc("conversations", doc)
    return ConversationResponse(
        id=doc_id,
        title=body.title,
        created_at=created_at,
        messages=body.messages,
    )


# ──────────────────────────────────────────────
# GET /api/conversations — 대화 목록 조회 (messages 제외)
# ──────────────────────────────────────────────

@router.get("", response_model=list[ConversationListItem], summary="대화 목록 조회")
def list_conversations():
    """저장된 대화 목록을 최신순으로 반환합니다 (messages 필드는 포함되지 않음)."""
    docs = get_all("conversations", order_by="created_at")
    # 최신순 정렬
    docs = sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)
    return [
        ConversationListItem(
            id=d["id"],
            title=d.get("title", "제목 없음"),
            created_at=d.get("created_at", ""),
        )
        for d in docs
    ]


# ──────────────────────────────────────────────
# GET /api/conversations/{id} — 특정 대화 전체 메시지 조회 (옵션 A)
# ──────────────────────────────────────────────

@router.get("/{conv_id}", response_model=ConversationResponse, summary="특정 대화 불러오기")
def get_conversation(conv_id: str):
    """지정한 대화의 전체 메시지를 조회합니다."""
    doc = get_one("conversations", conv_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
    return ConversationResponse(
        id=doc["id"],
        title=doc.get("title", "제목 없음"),
        created_at=doc.get("created_at", ""),
        messages=doc.get("messages", []),
    )


# ──────────────────────────────────────────────
# DELETE /api/conversations/{id} — 대화 삭제
# ──────────────────────────────────────────────

@router.delete("/{conv_id}", status_code=204, summary="대화 삭제")
def delete_conversation(conv_id: str):
    """지정한 대화 기록을 삭제합니다."""
    ok = delete_doc("conversations", conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
