"""
firestore.py — Firebase Admin SDK 초기화 및 Firestore CRUD 공통 서비스
지연 초기화(lazy init): 서버 기동 시가 아닌 첫 DB 호출 시 Firebase를 초기화합니다.
"""
import base64
import json
import logging
import os
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client

logger = logging.getLogger("firestore")

# ──────────────────────────────────────────────
# Firebase 지연 초기화 (Lazy Init)
# ──────────────────────────────────────────────

_db: Optional[Client] = None


def _get_db() -> Client:
    """첫 호출 시 Firebase를 초기화하고 Firestore 클라이언트를 반환한다."""
    global _db
    if _db is not None:
        logger.debug("Firestore 클라이언트 재사용 (이미 초기화됨)")
        return _db

    if firebase_admin._apps:
        logger.info("Firebase 앱 이미 초기화됨 → 클라이언트 획득")
        _db = firestore.client()
        return _db

    logger.info("Firebase 초기화 시작...")

    # Base64 방식 우선 시도
    b64_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "")
    if b64_json:
        logger.info(f"[1/4] FIREBASE_SERVICE_ACCOUNT_B64 발견 (길이={len(b64_json)})")
        try:
            service_account_json = base64.b64decode(b64_json.strip()).decode("utf-8")
            logger.info("[2/4] Base64 디코딩 성공")
        except Exception as e:
            logger.error(f"[2/4] Base64 디코딩 실패: {e}")
            raise
    else:
        logger.info("[1/4] B64 환경변수 없음 → JSON 방식 시도")
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
        if service_account_json:
            logger.info(f"[1/4] FIREBASE_SERVICE_ACCOUNT_JSON 발견 (길이={len(service_account_json)})")
        else:
            logger.error("[1/4] FIREBASE_SERVICE_ACCOUNT_B64·JSON 모두 없음!")

    if not service_account_json:
        raise EnvironmentError(
            "FIREBASE_SERVICE_ACCOUNT_B64 또는 FIREBASE_SERVICE_ACCOUNT_JSON 환경 변수가 설정되지 않았습니다."
        )

    try:
        service_account_dict = json.loads(service_account_json)
        logger.info(f"[2/4] JSON 파싱 성공 (project_id={service_account_dict.get('project_id')})")
    except json.JSONDecodeError as e:
        logger.warning(f"[2/4] JSON 파싱 1차 실패: {e} → \\n 이스케이프 복구 시도")
        try:
            fixed_json = service_account_json.replace('\r\n', '\\n').replace('\n', '\\n')
            service_account_dict = json.loads(fixed_json)
            logger.info(f"[2/4] JSON 파싱 복구 성공 (project_id={service_account_dict.get('project_id')})")
        except json.JSONDecodeError as e2:
            logger.error(f"[2/4] JSON 파싱 최종 실패: {e2}")
            logger.error(f"      원본 앞 200자: {service_account_json[:200]}")
            raise

    try:
        cred = credentials.Certificate(service_account_dict)
        logger.info("[3/4] Firebase 자격증명 객체 생성 성공")
    except Exception as e:
        logger.error(f"[3/4] Firebase 자격증명 생성 실패: {e}")
        raise

    try:
        firebase_admin.initialize_app(cred)
        logger.info("[4/4] Firebase 앱 초기화 성공")
    except Exception as e:
        logger.error(f"[4/4] Firebase 앱 초기화 실패: {e}")
        raise

    try:
        _db = firestore.client()
        logger.info("✅ Firestore 클라이언트 생성 완료")
    except Exception as e:
        logger.error(f"Firestore 클라이언트 생성 실패: {e}")
        raise

    return _db


# ──────────────────────────────────────────────
# 공통 CRUD 헬퍼
# ──────────────────────────────────────────────

def get_all(collection: str, order_by: Optional[str] = None, limit: Optional[int] = None) -> list[dict]:
    """컬렉션 전체 조회"""
    ref = _get_db().collection(collection)
    if order_by:
        ref = ref.order_by(order_by)
    if limit:
        ref = ref.limit(limit)
    docs = ref.stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def get_one(collection: str, doc_id: str) -> Optional[dict]:
    """단일 문서 조회"""
    doc = _get_db().collection(collection).document(doc_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


def add_doc(collection: str, data: dict) -> str:
    """새 문서 추가 → 생성된 doc_id 반환"""
    _, ref = _get_db().collection(collection).add(data)
    return ref.id


def update_doc(collection: str, doc_id: str, data: dict) -> bool:
    """문서 부분 업데이트 → 존재 여부 반환"""
    ref = _get_db().collection(collection).document(doc_id)
    doc = ref.get()
    if not doc.exists:
        return False
    ref.update(data)
    return True


def delete_doc(collection: str, doc_id: str) -> bool:
    """문서 삭제 → 존재 여부 반환"""
    ref = _get_db().collection(collection).document(doc_id)
    doc = ref.get()
    if not doc.exists:
        return False
    ref.delete()
    return True
