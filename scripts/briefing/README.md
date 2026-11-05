# 일일 항공 브리핑 스크립트

| 파일 | 역할 |
|---|---|
| `collect_weather.py` | 기상청 API허브(METAR/TAF/SIGMET) + NOAA + JTWC 수집, 상태 판정, 기상 보드 HTML·요약 JSON 생성 |
| `resolve_links.py` | Google News 중계 링크를 언론사 원문 URL로 변환(리디렉션 알림 제거) |
| `assemble.py` | brief.json + weather.json → 메일 HTML (뉴스 → 기상 순서) |
| `common.py` | 카드/타임라인/배지 렌더링 헬퍼 |
| `brief.example.json` | 모델이 작성하는 brief.json 예시 |

환경변수 `KMA_SERVICE_KEY` 필요(기상청 API허브 authKey). 키는 저장소에 넣지 않는다.
전체 절차는 저장소 루트의 `daily-briefing-prompt.md` 참고.
