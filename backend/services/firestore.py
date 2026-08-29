"""
firestore.py — Firebase Admin SDK 초기화 및 Firestore CRUD 공통 서비스
지연 초기화(lazy init): 서버 기동 시가 아닌 첫 DB 호출 시 Firebase를 초기화합니다.
"""
import json
import os
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client

# ──────────────────────────────────────────────
# Firebase 지연 초기화 (Lazy Init)
# ──────────────────────────────────────────────

_db: Optional[Client] = None


def _get_db() -> Client:
    """첫 호출 시 Firebase를 초기화하고 Firestore 클라이언트를 반환한다."""
    global _db
    if _db is not None:
        return _db

    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise EnvironmentError(
            "FIREBASE_SERVICE_ACCOUNT_JSON 환경 변수가 설정되지 않았습니다. "
            ".env 파일을 확인하세요."
        )

    try:
        service_account_dict = json.loads(service_account_json)
    except json.JSONDecodeError:
        # Render UI 붙여넣기 시 private_key의 \n이 실제 줄바꿈으로 변환되는 문제 자동 복구
        fixed_json = service_account_json.replace('\r\n', '\\n').replace('\n', '\\n')
        service_account_dict = json.loads(fixed_json)
    cred = credentials.Certificate(service_account_dict)
    firebase_admin.initialize_app(cred)
    _db = firestore.client()
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
