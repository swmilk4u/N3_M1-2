"""
routers/chat.py — AI 채팅 API (컨텍스트 주입 + 자동 저장 + Function Calling)
"""
from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse, ConversationCreate, MessageSchema
from services.openai_service import chat_with_context
from services.summary import compute_summary
from services.firestore import add_doc, get_one
from datetime import datetime, timezone

router = APIRouter(prefix="/api/chat", tags=["AI 채팅"])


@router.post("", response_model=ChatResponse, summary="AI 채팅 (컨텍스트 주입)")
def chat(body: ChatRequest):
    """
    동작 흐름:
    1. GET /api/data/summary → 데이터 요약 조회
    2. 요약을 시스템 프롬프트에 삽입
    3. GPT API 호출 (Function Calling 지원)
    4. 대화 내용을 conversations 컬렉션에 자동 저장
    """
    # 1) 데이터 요약 조회
    try:
        summary = compute_summary()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"데이터 요약 조회 실패: {str(e)}")

    # 2) 이전 히스토리 구성 (conversation_id가 있으면 불러오기)
    history = [m.model_dump() for m in body.history]
    if body.conversation_id and not history:
        existing = get_one("conversations", body.conversation_id)
        if existing:
            history = existing.get("messages", [])

    # 3) GPT 호출 (시스템 프롬프트 주입 + Function Calling)
    try:
        answer, tools_used = chat_with_context(
            user_message=body.message,
            summary=summary,
            history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GPT API 호출 실패: {str(e)}")

    # 4) 대화 자동 저장
    new_messages = history + [
        {"role": "user", "content": body.message},
        {"role": "assistant", "content": answer},
    ]

    title = body.message[:50] + ("..." if len(body.message) > 50 else "")
    conv_doc = {
        "title": title,
        "messages": new_messages,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if body.conversation_id:
        # 기존 대화 업데이트
        from services.firestore import update_doc
        update_doc("conversations", body.conversation_id, {"messages": new_messages})
        conv_id = body.conversation_id
    else:
        conv_id = add_doc("conversations", conv_doc)

    return ChatResponse(
        answer=answer,
        conversation_id=conv_id,
        tool_calls_used=tools_used,
    )
