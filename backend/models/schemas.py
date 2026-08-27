"""
schemas.py — Pydantic v2 요청/응답 스키마 정의
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Data (지하철 승하차 데이터)
# ──────────────────────────────────────────────

class DataCreate(BaseModel):
    """새 데이터 추가 요청 바디"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2024-11-01"])
    value: int = Field(..., ge=0, description="승하차 합계 (명)")
    memo: str = Field(..., min_length=1, max_length=100, examples=["강남역_2호선"])


class DataUpdate(BaseModel):
    """데이터 수정 요청 바디 (부분 수정 허용)"""
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    value: Optional[int] = Field(None, ge=0)
    memo: Optional[str] = Field(None, min_length=1, max_length=100)


class DataItem(BaseModel):
    """데이터 응답 모델"""
    id: str
    date: str
    value: int
    memo: str


# ──────────────────────────────────────────────
# Summary (요약 통계)
# ──────────────────────────────────────────────

class MetricsSchema(BaseModel):
    average: float
    max: int
    min: int
    total: int


class SummaryResponse(BaseModel):
    period: str
    count: int
    metrics: MetricsSchema
    trend: str
    top_stations: list[str]


class StatisticsResponse(BaseModel):
    """보너스: 추가 통계 API 응답"""
    by_line: dict[str, Any]        # 노선별 평균
    by_weekday: dict[str, float]   # 요일별 평균
    by_month: dict[str, float]     # 월별 평균


# ──────────────────────────────────────────────
# Conversations (대화 기록)
# ──────────────────────────────────────────────

class MessageSchema(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ConversationCreate(BaseModel):
    """대화 저장 요청 바디"""
    title: str = Field(..., min_length=1, max_length=200)
    messages: list[MessageSchema]


class ConversationResponse(BaseModel):
    """대화 응답 모델"""
    id: str
    title: str
    created_at: str
    messages: list[MessageSchema]


class ConversationListItem(BaseModel):
    """대화 목록 아이템 (messages 제외)"""
    id: str
    title: str
    created_at: str


# ──────────────────────────────────────────────
# Chat (AI 채팅)
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """채팅 요청 바디"""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(None, description="이어 쓸 대화 ID (없으면 새 대화)")
    history: list[MessageSchema] = Field(default_factory=list, description="이전 메시지 히스토리")


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    answer: str
    conversation_id: str
    tool_calls_used: list[str] = Field(default_factory=list, description="사용된 Function Calling 도구명")
