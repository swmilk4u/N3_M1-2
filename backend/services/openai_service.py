"""
openai_service.py — OpenAI GPT API 호출 서비스 (Function Calling 포함)
지연 초기화(lazy init): 모듈 import 시가 아닌 첫 API 호출 시 클라이언트를 생성합니다.
"""
import json
import os
from typing import Optional

from openai import OpenAI

_client: Optional[OpenAI] = None

MODEL      = "gpt-4o-mini"
MAX_TOKENS = 1024  # 과금 방지


def _get_client() -> OpenAI:
    """첫 호출 시 OpenAI 클라이언트를 생성한다."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

# ──────────────────────────────────────────────
# Function Calling 도구 스키마 (보너스)
# ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_data_summary",
            "description": "지하철 승하차 데이터 요약 정보를 조회합니다. 통계/트렌드 질문 시 호출하세요.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_data",
            "description": "최근 N개의 지하철 승하차 원본 데이터를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "조회할 데이터 건수 (기본값 30)",
                        "default": 30,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversations",
            "description": "저장된 이전 대화 목록을 조회합니다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ──────────────────────────────────────────────
# 도구 실행 핸들러
# ──────────────────────────────────────────────

def _execute_tool(tool_name: str, tool_args: dict) -> str:
    """Function Calling 도구를 실제 실행하여 결과 문자열 반환"""
    from services.summary import compute_summary
    from services.firestore import get_all

    if tool_name == "get_data_summary":
        summary = compute_summary()
        return json.dumps(summary, ensure_ascii=False)

    elif tool_name == "get_recent_data":
        limit = tool_args.get("limit", 30)
        docs = get_all("data", order_by="date", limit=limit)
        return json.dumps(docs[-limit:], ensure_ascii=False)

    elif tool_name == "get_conversations":
        convs = get_all("conversations", order_by="created_at")
        # messages 필드 제외하고 목록만 반환
        result = [{"id": c["id"], "title": c.get("title", ""), "created_at": c.get("created_at", "")} for c in convs]
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": f"알 수 없는 도구: {tool_name}"})


# ──────────────────────────────────────────────
# 메인 채팅 함수
# ──────────────────────────────────────────────

def chat_with_context(
    user_message: str,
    summary: dict,
    history: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """
    컨텍스트 주입 + Function Calling 지원 GPT 호출

    Returns:
        (answer: str, tools_used: list[str])
    """
    history = history or []
    tools_used: list[str] = []

    # 시스템 프롬프트 — 데이터 요약 주입
    system_prompt = f"""당신은 서울 지하철 데이터 분석 AI 비서입니다.

[사용자 데이터 요약]
- 데이터 기간: {summary.get('period', '알 수 없음')}
- 총 레코드: {summary.get('count', 0)}개
- 일평균 승하차: {summary.get('metrics', {}).get('average', 0):,}명
- 최고: {summary.get('metrics', {}).get('max', 0):,}명  최저: {summary.get('metrics', {}).get('min', 0):,}명
- 최근 트렌드: {summary.get('trend', '알 수 없음')}
- TOP 역: {', '.join(summary.get('top_stations', []))}

위 데이터를 기반으로 구체적이고 맞춤형 답변을 제공하세요.
필요 시 도구(tool)를 호출하여 최신 데이터를 조회할 수 있습니다.
숫자는 항상 한국식 단위(명, %, 배)로 표현하세요."""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # 1차 GPT 호출 (Function Calling 허용)
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=MAX_TOKENS,
        temperature=0.7,
    )

    msg = response.choices[0].message

    # Function Calling 처리
    while msg.tool_calls:
        messages.append(msg)

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments or "{}")
            tools_used.append(tool_name)

            tool_result = _execute_tool(tool_name, tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

        # 도구 결과 반영 후 재호출
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=MAX_TOKENS,
            temperature=0.7,
        )
        msg = response.choices[0].message

    return msg.content or "", tools_used
