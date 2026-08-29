"""
gemini_service.py -- Google Gemini API service (google.genai SDK)
"""
import json
import os
from typing import Optional

from google import genai
from google.genai import types

MODEL      = "gemini-3.6-flash"
MAX_TOKENS = 1024

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set in .env")
        _client = genai.Client(api_key=api_key)
    return _client


_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_data_summary",
        description="Get subway ridership data summary. Use for statistics or trend questions.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}),
    ),
    types.FunctionDeclaration(
        name="get_recent_data",
        description="Get recent N subway ridership records.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of records to fetch (default 30)",
                )
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_conversations",
        description="Get list of saved conversation history.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}),
    ),
]

_TOOLS = [types.Tool(function_declarations=_TOOL_DECLARATIONS)]


def _execute_tool(tool_name: str, tool_args: dict) -> str:
    from services.summary import compute_summary
    from services.firestore import get_all

    if tool_name == "get_data_summary":
        return json.dumps(compute_summary(), ensure_ascii=False)
    elif tool_name == "get_recent_data":
        limit = int(tool_args.get("limit", 30))
        docs = get_all("data", order_by="date", limit=limit)
        return json.dumps(docs[-limit:], ensure_ascii=False)
    elif tool_name == "get_conversations":
        convs = get_all("conversations", order_by="created_at")
        result = [{"id": c["id"], "title": c.get("title", ""), "created_at": c.get("created_at", "")} for c in convs]
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def chat_with_context(
    user_message: str,
    summary: dict,
    history: list | None = None,
) -> tuple:
    client = _get_client()
    history = history or []
    tools_used: list[str] = []

    avg = summary.get("metrics", {}).get("average", 0)
    mx  = summary.get("metrics", {}).get("max", 0)
    mn  = summary.get("metrics", {}).get("min", 0)
    total = summary.get("metrics", {}).get("total", 0)

    system_prompt = (
        "당신은 서울 지하철 역별 승하차 데이터 분석 AI 비서입니다. 한국어로 친절하고 전문적으로 답변하세요.\n\n"
        "[현재 데이터 요약 (컨텍스트)]\n"
        f"- 데이터 기간: {summary.get('period', '데이터 없음')}\n"
        f"- 총 레코드 수: {summary.get('count', 0):,}건\n"
        f"- 일평균 승하차 인원: {avg:,}명\n"
        f"- 최고 승하차 인원: {mx:,}명 / 최저: {mn:,}명\n"
        f"- 최근 트렌드: {summary.get('trend', '데이터 없음')}\n"
        f"- 주요 역 목록: {', '.join(summary.get('top_stations', [])) or '없음'}\n\n"
        "지침:\n"
        "1. 위의 [현재 데이터 요약] 정보를 적극 활용하여 데이터 기반으로 정확하게 답변하세요.\n"
        "2. 만약 데이터가 없거나 0건이면 데이터 추가 탭에서 승하차 데이터를 먼저 추가해 달라고 안내하세요.\n"
        "3. 숫자는 한국어 단위(만, 천 등)를 함께 사용하여 읽기 쉽게 표현하세요."
    )

    contents = []
    for msg in history[-6:]:  # 최근 6개 메시지만 컨텍스트 유지
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=MAX_TOKENS,
        temperature=0.7,
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )
        text = response.text or ""
    except Exception as e:
        # Fallback: 단일 프롬프트로 재시도
        prompt = f"{system_prompt}\n\n사용자 질문: {user_message}"
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        text = response.text or ""

    return text, tools_used