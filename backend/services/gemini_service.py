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

    system_prompt = (
        "You are a Seoul subway data analysis AI assistant. Answer in Korean.\n\n"
        "[Data Summary]\n"
        f"- Period: {summary.get('period', 'N/A')}\n"
        f"- Records: {summary.get('count', 0)}\n"
        f"- Daily avg ridership: {avg:,}\n"
        f"- Max: {mx:,} / Min: {mn:,}\n"
        f"- Trend: {summary.get('trend', 'N/A')}\n"
        f"- Top stations: {', '.join(summary.get('top_stations', []))}\n\n"
        "Provide specific, data-driven answers in Korean. "
        "Use tools if you need more detailed data. "
        "Express numbers in Korean units."
    )

    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=_TOOLS,
        max_output_tokens=MAX_TOKENS,
        temperature=0.7,
    )

    response = client.models.generate_content(model=MODEL, contents=contents, config=config)

    while True:
        fn_calls = [
            p.function_call
            for p in response.candidates[0].content.parts
            if p.function_call
        ]
        if not fn_calls:
            break

        contents.append(response.candidates[0].content)

        tool_response_parts = []
        for fc in fn_calls:
            tools_used.append(fc.name)
            result = _execute_tool(fc.name, dict(fc.args))
            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        contents.append(types.Content(role="tool", parts=tool_response_parts))
        response = client.models.generate_content(model=MODEL, contents=contents, config=config)

    text = "".join(
        p.text for p in response.candidates[0].content.parts if hasattr(p, "text") and p.text
    )
    return text, tools_used