# 바이브코딩 수업 도구

시험 후 과학 시간 4차시 수업(학생이 제미나이로 게임·앱을 만들고 반별로 공유·투표)을 위한 도구 모음. 16개 반 × 약 30명, 1인 1작품, 크롬북.
사용자는 한국어를 쓰는 과학 교사이며 코딩 비전문가다. 설명은 쉬운 한국어로, 명령어는 그대로 복사해 쓸 수 있게 쓴다.

## 문서 우선순위
`README.md`(사용법)와 실제 코드가 `SPEC.md`(초기 명세)보다 우선한다. 달라진 점은 SPEC.md 맨 아래 "구현 중 변경 사항"에 있다.
작업을 시작하기 전에 SPEC.md와 README.md를 읽고 현재 상태를 요약한다.

## 구조
- `site/app/index.html` 학생용 앱(단일 HTML, 외부 라이브러리·외부 요청 없음)
- `site/index.html, class.html, play.html, gallery.*` 갤러리 / `site/data/*.json` 작품 목록(publish.py가 생성)
- `site/games/<반2자리>/<코드>.html` 공개 게임(publish.py가 생성)
- `tools/ingest.py, publish.py, common.py` 교사용 스크립트 / `tools/make_forms.gs` 구글 폼 생성(미시험)
- `docs/FORMS.md` 폼 구성안 / `tests/` 테스트 / `private/` 교사 컴퓨터 전용(커밋 금지)

## 지켜야 할 규칙
1. 공개되는 것(파일 이름, 갤러리 화면, `site/data`, 커밋)에 학번·이름이 들어가면 안 된다. 대응표는 `private/mapping.csv`에만 둔다.
2. `private/`, `*.csv`는 절대 커밋하지 않는다(.gitignore). 학생 제출 원본도 마찬가지.
3. 학생용 앱은 단일 HTML 파일을 유지한다. 외부 CDN·폰트·이미지 요청 금지.
4. 갤러리의 게임 iframe은 `sandbox="allow-scripts allow-modals allow-pointer-lock"`만 쓴다(`allow-same-origin` 금지). 게임 제목은 항상 `textContent`로 넣는다.
5. 보안 규칙(CSP)은 `publish.py`의 `harden()`이 게임 파일에 meta로 넣는다. iframe `csp` 속성은 GitHub Pages에서 동작하지 않는다.
6. 코드를 바꾼 뒤에는 아래 테스트를 모두 돌려 통과를 확인한다.

## 테스트
```
python tests/test_tools.py                 # 표준 라이브러리만
pip install playwright && playwright install chromium
python tests/test_app.py
python tests/test_gallery.py <스크린샷 저장 폴더>
```

## 배포
`main`에 `site/` 변경을 push하면 `.github/workflows/pages.yml`이 GitHub Pages로 배포한다(Settings → Pages → Source: GitHub Actions).

## 아직 시험하지 못한 것 (학교에서 확인 필요)
폼 파일 업로드(.html, 1MB 이상 상한, 학교 DLP), 학생 계정으로 앱·갤러리 링크 열기, 크롬북 터치/터치패드 서명, `make_forms.gs` 실행, 실제 GitHub Pages 배포.
