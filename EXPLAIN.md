# 프로젝트 설명 (EXPLAIN)

## 배경
- 아내가 서울특별시 공공서비스예약(https://yeyak.seoul.go.kr)에서 우리 아들 수현이가 들을 만한 교육 프로그램을 꾸준히 확인하고 싶다고 요청했습니다.
- 처음에는 웹사이트의 상세 검색 페이지(https://yeyak.seoul.go.kr/web/search/selectPageListDetailSearchImg.do)에서 개발자도구 네트워크 패널로 어떤 API가 호출되는지 파악하려 했으나, 해당 페이지는 개발자도구 접근이 제한되어 있어 분석이 어려웠습니다.
- GPT-5에 문의한 결과, 동일 정보를 제공하는 서울시 공공데이터 Open API가 있음을 알게 되었고, 브라우저 크롤링 대신 공공 API 연동으로 방향을 전환했습니다.

## 목적
- 서울시 공공예약 교육 서비스(데이터셋: OA-2271, `ListPublicReservationEducation`)를 매일 자동으로 수집합니다.
- 특정 구, 상태, 대상 필터를 적용해 두 가지 리스트(v12, v123)로 나눠 보관합니다.
- 요약 본문과 JSON 첨부를 이메일로 받아 빠르게 확인할 수 있게 합니다.

## 접근 전환 스토리
- 시도: 웹페이지 네트워크 호출을 직접 캡처 → 개발자도구 차단으로 실패.
- 전환: GPT-5가 서울시 Open API를 제안 → API로 데이터 수집/필터/알림 아키텍처 구상.
- 구현: 인프라 없이 GitHub Actions의 cron 스케줄러로 매일 실행, 이메일 발송은 Gmail App Password 사용.
- 개인 역할: 파이썬으로 코어 로직은 에이전트가 작성했고, 저는 GitHub Actions 워크플로우에서 `env` 글로벌 설정 한 줄 추가 정도만 직접 손봤습니다.

## 설계 개요
- 실행 주기: 매일 1회(수동 실행도 가능)
- 수집: OA-2271 API 페이지네이션/재시도 처리 후 전량 수집
- 필터: 조건에 따라 v12, v123 리스트 생성
- 산출물: JSON 3종 + 요약 CSV 1종
- 알림: 본문에 최대 10건씩 요약, v12/v123 JSON 파일 첨부하여 이메일 발송

## 기술 스택과 규칙
- 언어: Python 3.10+
- 의존성: `requests`만 사용 (requirements.txt)
- 인코딩: UTF-8 고정, JSON 저장 시 `ensure_ascii=False`, `indent=2`
- 재시도: 5xx/연결 오류 시 최대 3회 지수 백오프
- 방어적 파싱: 누락 필드는 빈 문자열로 처리
- 날짜 파싱: 여러 형식을 수용하는 헬퍼, 실패 시 `None` 반환

## 주요 파일
- `fetch_reservations.py`
  - OA-2271 호출(페이지네이션/재시도), 필터링, 산출물 저장
  - 입력 키: 환경변수 `SEOUL_API_KEY`
  - 출력 파일명:
    - `seoul_education_all.json`
    - `seoul_education_v12.json`
    - `seoul_education_v123.json`
    - `seoul_education_summary.csv`
- `compose_email.py`
  - `seoul_education_v12.json`, `seoul_education_v123.json`를 읽어 콘솔에 이메일 본문(plain text) 출력
  - 섹션별 최대 10건, `RCPTBGNDT` 기준 오름차순 정렬
- `.github/workflows/daily-email.yml`
  - cron+수동 트리거, Gmail SMTP(SSL 465)로 메일 발송
  - 첨부: v12/v123 JSON
  - GitHub Secrets 우선, 필요 시 `.env`로 보완
- `requirements.txt`: `requests`
- `README.md`: 로컬 실행/시크릿 설정 방법
- `.env`(커밋 제외): 로컬 비공개 설정 관리용. `MAIL_TO` 등 비민감 항목 보관, 민감정보는 GitHub Secrets 권장

## 데이터셋과 필터 조건
- 데이터셋: OA-2271 `ListPublicReservationEducation` (필드: `list_total_count`, `row` 등)
- 필터 조건:
  1) `AREANM` ∈ {"강남구", "서초구", "송파구"}
  2) `SVCSTATNM` ∈ {"접수중", "안내중"}
  3) `USETGTINFO` 내 포함어 ∈ {"유아", "제한없음", "가족"}
- 리스트 정의:
  - v12 = (1) AND (2)
  - v123 = (1) AND (2) AND (3)

## 동작 흐름
1) `.env` 자동 로드(이미 설정된 환경변수는 보존)
2) `fetch_reservations.py` 실행 → OA-2271 전체 수집 → 필터링 → JSON/CSV 저장
3) `compose_email.py` 실행 → 본문 생성(콘솔 출력)
4) GitHub Actions에서 위 스크립트 순서로 실행 후, 본문+첨부로 이메일 전송

## 이메일 본문 구성
- 섹션: v12(지역+상태), v123(지역+상태+대상)
- 각 섹션 최대 10건, `RCPTBGNDT` 오름차순
- 항목 표시 예: `[접수중] 프로그램명 | 기관명 | 시작일 ~ 종료일 | 링크`
- 첨부: `seoul_education_v12.json`, `seoul_education_v123.json`

## 로컬 개발/실행
- 환경 준비
  - Python 3.10+, `pip install -r requirements.txt`
  - `SEOUL_API_KEY`를 환경변수로 지정하거나 `.env`에 저장
  - `.env`에 `MAIL_TO` 등 비민감 값을 둘 수 있음
- 실행
  - 데이터 수집: `python fetch_reservations.py`
  - 미리보기: `python compose_email.py | less`

## CI와 시크릿 관리
- GitHub Secrets 권장: `SEOUL_API_KEY`, `MAIL_USERNAME`(Gmail 주소), `MAIL_PASSWORD`(Gmail App Password)
- 워크플로는 Secrets를 우선 사용, 미설정 시 `.env` 로드 값으로 보완
- 메일 수신자 `MAIL_TO`는 `.env`에 두고 필요 시 워크플로에서 주입
- 메일 발송 액션: `dawidd6/action-send-mail@v3` (SMTP 465/SSL)

## 한계와 향후 개선 아이디어
- 한계
  - Open API 스키마/가용성 변경 시 영향 가능
  - 호출 쿼터 제한 시 누락 위험
  - Gmail 일일 발송 제한 고려 필요
- 개선
  - 이전 발송 대비 변경분(diff) 하이라이트
  - 관심 키워드/나이대 커스터마이징
  - 중복/종료 항목 자동 제거 및 알림 억제
  - 캘린더(ICS) 첨부 생성, 슬랙/텔레그램 알림 연동

## 크레딧
- 아이디어/요청: 아내
- 구현 보조: GPT-5 + Codex CLI 에이전트
- 직접 작업: GitHub Actions 워크플로우 `env` 글로벌 설정 일부 수정, 시크릿 구성 등 운영 세팅

