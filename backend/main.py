"""
main.py — FastAPI 앱 진입점
CORS 설정 / 라우터 등록 / 헬스체크
"""
import os
import signal
import socket
import sys

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

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
    """앱 시작 시 포트 정리"""
    _kill_process_on_port(PORT)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
