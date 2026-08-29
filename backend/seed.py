"""
seed.py — sample_data.csv를 Firestore에 벌크 업로드 (1회용 스크립트)
실행: python seed.py
"""
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Firestore 초기화
from services.firestore import _get_db, add_doc, get_all

def seed():
    csv_path = Path(__file__).parent / "sample_data.csv"
    if not csv_path.exists():
        print("❌ sample_data.csv 파일이 없습니다.")
        sys.exit(1)

    # 기존 Firestore 데이터의 (date, memo) 셋 — 중복 방지
    print("🔍 기존 Firestore 데이터 조회 중...")
    existing = get_all("data", order_by="date")
    existing_keys = {(d["date"], d.get("memo", "")) for d in existing}
    print(f"   기존 데이터: {len(existing_keys)}건")

    db = _get_db()
    col_ref = db.collection("data")

    inserted = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = db.batch()
        batch_count = 0

        for row in reader:
            date = row["date"].strip()
            value = int(row["value"].strip())
            memo = row["memo"].strip()

            key = (date, memo)
            if key in existing_keys:
                skipped += 1
                continue

            doc_ref = col_ref.document()
            batch.set(doc_ref, {
                "date": date,
                "value": value,
                "memo": memo,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            batch_count += 1
            inserted += 1

            # Firestore 배치는 500건 제한
            if batch_count >= 400:
                batch.commit()
                print(f"   배치 커밋: {inserted}건 적재됨...")
                batch = db.batch()
                batch_count = 0

        if batch_count > 0:
            batch.commit()

    print(f"\n✅ 완료! 추가: {inserted}건 / 스킵(중복): {skipped}건")


if __name__ == "__main__":
    seed()
