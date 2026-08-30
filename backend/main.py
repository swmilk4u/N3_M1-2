"""
main.py — FastAPI 앱 진입점
CORS 설정 / 라우터 등록 / 헬스체크
"""
import logging
import os
import signal
import socket
import sys
import traceback

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

# ──────────────────────────────────────────────
# 포트 충돌 방지 (user_rules: 기존 프로세스 자동 종료)
# ──────────────────────────────────────────────

def _kill_process_on_port(port: int) -> None:
    """지정 포트를 점유 중인 프로세스를 종료한다 (Windows/Linux 공용)."""
    import subprocess, platform
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(["taskkill", "/F", "/PID", pid], check=False)
        else:
            result = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}"],
                capture_output=True, text=True
            )
            for pid in result.stdout.strip().splitlines():
                os.kill(int(pid), signal.SIGKILL)
    except Exception:
        pass  # 충돌 방지 실패 시 무시 후 계속 진행


PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 포트 정리 및 환경 변수 로그 출력"""
    _kill_process_on_port(PORT)

    # ── 환경 변수 진단 로그 ──
    logger.info("=" * 60)
    logger.info("🚀 서버 시작")
    logger.info(f"PORT            : {PORT}")

    allowed = os.getenv("ALLOWED_ORIGINS", "(미설정→기본값 사용)")
    logger.info(f"ALLOWED_ORIGINS : {allowed}")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    logger.info(f"GEMINI_API_KEY  : {'설정됨 (' + gemini_key[:8] + '...)' if gemini_key else '❌ 미설정'}")

    seoul_key = os.getenv("SEOUL_API_KEY", "")
    logger.info(f"SEOUL_API_KEY   : {'설정됨' if seoul_key else '❌ 미설정'}")

    b64_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "")
    json_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if b64_key:
        logger.info(f"FIREBASE        : B64 방식 설정됨 (길이={len(b64_key)})")
    elif json_key:
        logger.info(f"FIREBASE        : JSON 방식 설정됨 (길이={len(json_key)})")
    else:
        logger.error("FIREBASE        : ❌ 환경변수 없음! (B64·JSON 모두 미설정)")

    logger.info("=" * 60)
    yield


# ──────────────────────────────────────────────
# FastAPI 앱 생성
# ──────────────────────────────────────────────

app = FastAPI(
    title="서울 지하철 AI 비서 API",
    description=(
        "서울 지하철 역별 승하차 인원 데이터를 기반으로 "
        "GPT 컨텍스트 주입 방식의 맞춤형 AI 답변을 제공합니다.\n\n"
        "> ⚠️ **Render 무료 티어**: 15분 미사용 후 첫 요청 시 30~60초 지연이 발생할 수 있습니다."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ──────────────────────────────────────────────
# CORS 설정 (환경 변수 기반)
# ──────────────────────────────────────────────

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:5500")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
logger.info(f"CORS 허용 origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# 전역 예외 핸들러 (500 오류 상세 로그)
# ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"❌ 처리되지 않은 예외 발생")
    logger.error(f"   URL    : {request.method} {request.url}")
    logger.error(f"   Origin : {request.headers.get('origin', '없음')}")
    logger.error(f"   오류   : {type(exc).__name__}: {exc}")
    logger.error(f"   스택트레이스:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": tb,
        },
    )

# ──────────────────────────────────────────────
# 라우터 등록
# ──────────────────────────────────────────────

from routers.data import router as data_router
from routers.conversations import router as conv_router
from routers.chat import router as chat_router

app.include_router(data_router)
app.include_router(conv_router)
app.include_router(chat_router)

# ──────────────────────────────────────────────
# 헬스체크
# ──────────────────────────────────────────────

@app.get("/", tags=["헬스체크"], summary="서버 상태 확인")
def root():
    return {
        "status": "ok",
        "message": "서울 지하철 AI 비서 서버가 정상 동작 중입니다.",
        "docs": "/docs",
    }

@app.get("/health", tags=["헬스체크"], summary="헬스체크")
def health():
    return {"status": "healthy"}


# ──────────────────────────────────────────────
# 디버그 엔드포인트 (환경 변수 진단용)
# ──────────────────────────────────────────────

@app.get("/debug", tags=["헬스체크"], summary="환경 변수 진단")
def debug_env():
    """배포 환경 변수 상태를 확인합니다 (민감 정보는 마스킹)."""
    import base64, json as _json

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    seoul_key  = os.getenv("SEOUL_API_KEY", "")
    b64_key    = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "")
    json_key   = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")

    firebase_status = "❌ 미설정"
    firebase_detail = ""
    if b64_key:
        try:
            decoded = base64.b64decode(b64_key.strip()).decode("utf-8")
            parsed  = _json.loads(decoded)
            firebase_status = "✅ B64 방식 파싱 성공"
            firebase_detail = f"project_id={parsed.get('project_id')}, client_email={parsed.get('client_email','')[:30]}..."
        except Exception as e:
            firebase_status = f"❌ B64 파싱 실패: {e}"
    elif json_key:
        try:
            parsed  = _json.loads(json_key)
            firebase_status = "✅ JSON 방식 파싱 성공"
            firebase_detail = f"project_id={parsed.get('project_id')}, client_email={parsed.get('client_email','')[:30]}..."
        except Exception as e:
            firebase_status = f"❌ JSON 파싱 실패: {e}"

    # Firestore 실제 연결 시도
    firestore_conn = "미시도"
    try:
        from services.firestore import get_all
        get_all("data", limit=1)
        firestore_conn = "✅ Firestore 연결 성공"
    except Exception as e:
        firestore_conn = f"❌ Firestore 연결 실패: {type(e).__name__}: {e}"

    return {
        "cors_origins"     : allowed_origins,
        "gemini_api_key"   : f"설정됨({gemini_key[:8]}...)" if gemini_key else "❌ 미설정",
        "seoul_api_key"    : "설정됨" if seoul_key else "❌ 미설정",
        "firebase_auth"    : firebase_status,
        "firebase_detail"  : firebase_detail,
        "firestore_connect": firestore_conn,
        "allowed_origins"  : allowed_origins,
    }
