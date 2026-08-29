# 🚇 서울 지하철 AI 비서

> 서울 지하철 역별 승하차 인원 공공데이터를 분석하고, GPT 컨텍스트 주입 방식으로 맞춤형 AI 답변을 제공하는 웹 서비스
>
> **코디세이 AI 네이티브 과정 N3 — M1-2 AI Agent 개발 과제**

---

## 📌 서비스 소개

일반 AI는 "강남역 요즘 얼마나 붐벼?"라고 물어봐도 정확한 답을 모릅니다.

**서울 지하철 AI 비서**는 서울 열린데이터광장의 **지하철 역별 승하차 인원 공공데이터**를 Firestore에 저장·분석하고, 해당 요약 정보를 GPT 시스템 프롬프트에 주입하여 **내 데이터를 아는 맞춤형 AI 답변**을 제공합니다.

| 기존 AI | 이 서비스 |
|---------|----------|
| "강남역이 붐비긴 하죠" (일반 답변) | "최근 30일 평균 18만 명, 전체 역 중 3위입니다" (데이터 기반 답변) |
| 데이터를 직접 찾아봐야 함 | 자연어 질문으로 즉시 인사이트 획득 |
| 추세 파악 불가 | 전월 대비 증감률, 최고/최저 기록 자동 분석 |

---

## ✅ 최종 결과물 — 4가지 기능 구현

> 과제 요구 4가지 기능이 모두 정상 동작하는 애플리케이션

### 1. 데이터 기반 AI 채팅
- 입력: 사용자 자연어 질문
- 동작: `/api/data/summary` 호출 → 요약을 시스템 프롬프트에 삽입 → GPT 응답 생성
- 출력: 지하철 데이터를 반영한 AI 답변 + 로딩 스피너 표시

### 2. 데이터 관리 (CRUD)
- 입력: `(date, value, memo)` = `(날짜, 승하차합계, 역명_노선)` 형태
- 기능: 새 데이터 추가 / 목록 조회 / 수정 / 삭제
- 출력: Firestore `data` 컬렉션 갱신 및 화면 목록 즉시 반영

### 3. 대화 기록 저장 및 불러오기
- 입력: AI 채팅 종료 후 자동 저장 / 대화 목록 조회 / 특정 대화 선택
- 기능: `POST /api/conversations` 자동 저장, `GET /api/conversations/{id}` 불러오기
- 출력: 이전 대화 목록 표시, 선택 시 메시지 전체 재표시

### 4. 배포 및 문서화
- 백엔드: Render 배포 → Swagger UI `/docs` 확인 가능
- 프론트엔드: Vercel 배포 → 환경 변수로 백엔드 URL 관리
- 문서화: 본 README (실행 방법 + 환경변수 안내 포함)

---

## 🎯 과제 목표 — 학습 성과

이 과제를 통해 다음을 스스로 설명할 수 있습니다.

| # | 학습 목표 | 구현 위치 |
|---|----------|----------|
| 1 | 시계열 데이터 분석 → 요약 정보 생성 흐름 | `services/summary.py` |
| 2 | FastAPI 라우터/서비스 분리 구성 기준 | `routers/` + `services/` 디렉토리 분리 |
| 3 | Pydantic을 활용한 요청 데이터 검증 | `models/schemas.py` |
| 4 | Firestore CRUD 처리 방식 | `services/firestore.py` |
| 5 | 데이터 요약을 시스템 프롬프트에 주입하는 컨텍스트 주입 원리 | `routers/chat.py` |
| 6 | 배포 환경에서 CORS/환경변수/키 관리의 필요성 | `main.py` CORS 설정 + `.env` |
| 7 | Google Gemini API를 활용한 Function Calling 구현 | `services/gemini_service.py` |

---

## 🛠 기술 스택 & 개발 환경

### Backend
| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.10+ | 런타임 |
| FastAPI | 0.110+ | REST API 서버 |
| Uvicorn | 0.29+ | ASGI 서버 |
| firebase-admin | 6.5+ | Firestore 연동 |
| google-genai | 1.0+ | Gemini API 호출 |
| python-dotenv | 1.0+ | 환경 변수 관리 |
| pydantic | 2.7+ | 데이터 검증 |

### Frontend
| 기술 | 용도 |
|------|------|
| HTML5 / CSS3 / JavaScript (ES6+) | 바닐라 프론트엔드 (프레임워크 미사용) |

### 인프라
| 구분 | 서비스 |
|------|--------|
| 백엔드 배포 | Render (Web Service) |
| 프론트엔드 배포 | Vercel |
| 데이터베이스 | Firebase Firestore |
| AI 엔진 | Google Gemini (gemini-2.0-flash) |

### 데이터 출처
- **서울 열린데이터광장** — 지하철 호선별 역별 승하차 인원 정보
  - URL: https://data.seoul.go.kr
  - 구조: `(date, value, memo)` → `(날짜, 승하차합계, 역명_노선)`
  - 규모: 일별 데이터 기준 연간 300+ 역 × 365일

---

## 🔗 배포 URL

| 구분 | URL |
|------|-----|
| 🌐 프론트엔드 | `https://n3-m1-2.vercel.app` |
| ⚙️ 백엔드 API | `https://n3-m1-2.onrender.com` |
| 📄 Swagger UI | `https://n3-m1-2.onrender.com/docs` |

> ⚠️ **Render 무료 티어 콜드스타트 안내**
> 15분 이상 미사용 시 서버가 슬립 상태로 전환됩니다. 첫 요청 시 30~60초 지연이 발생할 수 있으며, 화면에 "서버 기동 중입니다..." 안내 문구가 표시됩니다.

---

## 📁 프로젝트 구조

```
N3_M1-2_AI agent/
├── backend/
│   ├── main.py                   # FastAPI 앱 진입점, CORS 설정
│   ├── routers/
│   │   ├── data.py               # GET/POST/PUT/DELETE /api/data, GET /api/data/summary
│   │   ├── conversations.py      # GET/POST/DELETE /api/conversations
│   │   └── chat.py               # POST /api/chat (컨텍스트 주입)
│   ├── services/
│   │   ├── firestore.py          # Firestore CRUD 공통 서비스
│   │   ├── openai_service.py     # GPT API 호출 서비스
│   │   └── summary.py            # 데이터 요약 로직 (통계 계산)
│   ├── models/
│   │   └── schemas.py            # Pydantic 요청/응답 스키마
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html                # 메인 SPA
│   ├── style.css                 # 스타일시트
│   └── app.js                   # 채팅/CRUD/대화기록 로직
└── README.md
```

---

## ⚡ 로컬 실행 방법

### 사전 준비
- Python 3.10 이상
- Firebase 프로젝트 + 서비스 계정 키 JSON
- OpenAI API 키

### 1. 저장소 클론

```bash
git clone https://github.com/your-username/subway-ai-assistant.git
cd subway-ai-assistant
```

### 2. 백엔드 실행

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 파일 생성
cp .env.example .env
# .env 파일에 아래 환경 변수 입력

# 서버 실행
uvicorn main:app --reload
```

✅ 실행 후 http://localhost:8000/docs 에서 Swagger UI 확인

### 3. 프론트엔드 실행

```bash
cd frontend
# VS Code Live Server 또는 브라우저에서 index.html 직접 열기
# API_BASE_URL을 http://localhost:8000 으로 설정 필요
```

---

## 🔐 환경 변수 목록

`.env.example`을 복사하여 `.env` 파일을 생성하고 값을 입력하세요.

```env
# ✅ 필수 — Google Gemini API 키
# https://aistudio.google.com/app/apikey 에서 무료 발급
GEMINI_API_KEY=AIza...

# ✅ 필수 — Firebase 서비스 계정 키 (JSON 전체를 한 줄 문자열로)
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"your-project",...}

# ✅ 필수 — CORS 허용 도메인 (쉼표 구분)
ALLOWED_ORIGINS=http://localhost:3000,https://n3-m1-2.vercel.app
```

**프론트엔드 API 주소 설정 (`frontend/env.js`):**

```js
// 로컬 개발: http://localhost:8000
// 배포 환경: https://n3-m1-2.onrender.com
window.ENV_API_BASE_URL = 'https://n3-m1-2.onrender.com';
```

---

## 📡 API 명세

### 데이터 API (`/api/data`)

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/data` | 새 승하차 데이터 추가 |
| `GET` | `/api/data` | 데이터 목록 전체 조회 |
| `PUT` | `/api/data/{id}` | 특정 데이터 수정 |
| `DELETE` | `/api/data/{id}` | 특정 데이터 삭제 |
| `GET` | `/api/data/summary` | 데이터 요약 (AI 프롬프트 주입용) |

**요약 응답 예시:**
```json
{
  "period": "2024-01 ~ 2024-11",
  "count": 3240,
  "metrics": {
    "average": 182345,
    "max": 312000,
    "min": 45000
  },
  "trend": "상승 (월평균 +5.2%)",
  "top_stations": ["강남역_2호선", "홍대입구역_2호선", "신림역_2호선"]
}
```

### 대화 기록 API (`/api/conversations`)

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/conversations` | 대화 저장 |
| `GET` | `/api/conversations` | 대화 목록 조회 |
| `GET` | `/api/conversations/{id}` | 특정 대화 전체 메시지 조회 |
| `DELETE` | `/api/conversations/{id}` | 대화 삭제 |

### AI 채팅 API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| `POST` | `/api/chat` | 질문 전송 → 요약 주입 → GPT 응답 → 자동 저장 |

---

## 🗄️ Firestore 컬렉션 구조

```
Firestore
├── data/                          # 지하철 승하차 데이터
│   └── {doc_id}
│       ├── date: "2024-11-01"     # 날짜 (YYYY-MM-DD)
│       ├── value: 182345          # 승하차 합계 (정수)
│       └── memo: "강남역_2호선"   # 역명_노선 메모
│
└── conversations/                 # 대화 기록
    └── {doc_id}
        ├── title: "강남역 이용객 분석"
        ├── created_at: timestamp
        └── messages: [
              { "role": "user",      "content": "강남역 요즘 어때?" },
              { "role": "assistant", "content": "최근 30일 평균 18만 명..." }
            ]
```

---

## 🔄 AI 컨텍스트 주입 흐름

```
사용자 질문 입력
       │
       ▼
POST /api/chat
       │
       ▼
GET /api/data/summary  ◄── Firestore data 컬렉션 집계
       │
       ▼  요약 데이터
┌──────────────────────────────────┐
│ 시스템 프롬프트 구성             │
│                                  │
│ "당신은 서울 지하철 데이터       │
│  분석 AI 비서입니다.             │
│                                  │
│  [사용자 데이터 요약]            │
│  - 데이터 기간: 2024-01~2024-11  │
│  - 총 레코드: 3,240개            │
│  - 일평균 승하차: 182,345명      │
│  - 최근 트렌드: 상승 (+5.2%)     │
│  - TOP 역: 강남, 홍대, 신림      │
│                                  │
│  위 데이터를 기반으로 답변하세요" │
└──────────────────────────────────┘
       │
       ▼
OpenAI GPT-4o API 호출
       │
       ▼
맞춤형 AI 답변 반환
       │
       ▼
POST /api/conversations  ◄── 대화 내용 자동 저장
```

---

## ⭐ 보너스 과제 구현

### 1. AI 도구 호출 (Function Calling) + 멀티채널 연동

GPT가 사용자 질문의 의도를 판단하여 필요 시 내부 API를 **도구(Tool)** 로 자동 호출합니다.

**정의된 도구 스키마:**

| 도구명 | 호출 조건 | 연결 API |
|--------|----------|---------|
| `get_data_summary` | 통계/요약 정보 질문 시 | `GET /api/data/summary` |
| `get_recent_data` | 최근 데이터 조회 요청 시 | `GET /api/data?limit=30` |
| `get_conversations` | 이전 대화 검색 요청 시 | `GET /api/conversations` |

**Function Calling 흐름:**
```
1. 사용자: "지난 달 가장 붐볐던 역 알려줘"
2. GPT: get_data_summary 도구 호출 판단
3. 서버: /api/data/summary 실행 → 결과 반환
4. GPT: 결과를 자연어로 변환하여 최종 답변
```

**멀티채널 연동:** MCP Server 방식으로 동일 기능을 외부 클라이언트(Claude Desktop 등)에서도 호출 가능하도록 구현

---

### 2. 인사이트·UX 고도화

| 기능 | 구현 내용 |
|------|----------|
| 📊 추가 통계 지표 | `GET /api/data/statistics` — 노선별 비교, 요일별 평균, 계절별 트렌드 |
| 📈 데이터 시각화 | Chart.js 활용 — 월별 승하차 추이 라인 차트 |
| 💾 데이터 내보내기 | CSV / JSON 다운로드 버튼 |
| 🌙 다크 모드 토글 | CSS 변수 기반 테마 전환 |

---

## 📷 제출 스크린샷

### 채팅 화면 — 데이터 요약 + AI 답변
<!-- 스크린샷 추가 예정 (배포 후) -->

### 데이터 관리 화면 — CRUD 동작
<!-- 스크린샷 추가 예정 (배포 후) -->

### 대화 기록 화면 — 불러오기 동작
<!-- 스크린샷 추가 예정 (배포 후) -->

---

## 📦 requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
firebase-admin==6.5.0
google-genai>=1.0.0
python-dotenv==1.0.1
pydantic==2.7.0
```

---

## 🔒 보안 및 운영 원칙

- API 키 / Firebase 서비스 계정 키는 **환경 변수**로만 관리, 코드에 하드코딩 금지
- 모든 요청 값은 **Pydantic 스키마**로 검증, 잘못된 입력 시 422 에러 반환
- OpenAI 호출 시 `max_tokens` 제한으로 과금 방지
- CORS는 `ALLOWED_ORIGINS` 환경 변수로 허용 도메인만 제한

---

## 👤 작성자

- 과정: 코디세이 AI 네이티브 과정 N3
- 미션: M1-2 AI Agent 개발 — 나만의 AI 비서 구축
