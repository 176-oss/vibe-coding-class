# 바이브코딩 과학 수업 도구

시험 후 과학 시간 4차시 동안 학생들이 제미나이로 과학 개념 게임이나 학급 앱을 만들고, 반 안에서 함께 플레이하고 투표하는 수업을 위한 도구입니다. (16개 반 × 약 30명, 1인 1작품, 크롬북 기준)

| 구성 | 위치 | 설명 |
|---|---|---|
| 학생용 앱 (메인 화면) | `site/index.html` | 서약 서명, 기획서, 제작 일지, 게임 내보내기, 제출용 요약 복사 |
| 갤러리 | `site/gallery/` | 반별 작품 목록과 플레이 화면. 앱의 4차시 탭 안에도 들어가 있고, 단독 주소(`…/gallery/`)로도 열림 |
| 수합·공개 스크립트 | `tools/` | 제출 파일 점검(`ingest.py`)과 공개(`publish.py`) |
| 폼 구성안 | `docs/FORMS.md` | 구글 폼 4개 문항과 투표 집계 방법 |
| 명세 | `SPEC.md` | 요구사항과 결정 사항 |

## 전체 흐름

```
학생: 앱에서 서약·기획·제작 기록 → 요약을 구글 폼에 붙여넣기
      Canvas 코드를 앱에 붙여넣어 .html 내보내기 → 폼에 파일 업로드
교사: 폼 파일을 모아 내려받기 → ingest.py 로 점검 → review.csv 에서 승인(Y)
      → publish.py 로 공개 → git push → GitHub Pages 갤러리에 반영
학생: 갤러리에서 우리 반 작품 플레이 → 구글 폼으로 투표
```

공개되는 파일 이름과 갤러리 화면에는 **학번·이름이 나오지 않습니다.** 대응표(`private/mapping.csv`)는 선생님 컴퓨터에만 있고 저장소에 올라가지 않습니다(`.gitignore`로 제외).

## 처음 한 번만 하는 준비

1. **Python 확인:** 터미널에서 `python --version`(윈도우는 `py --version`)을 입력해 3.9 이상인지 확인합니다.
2. **저장소 받기:** `git clone https://github.com/176-oss/vibe-coding-class` 후 그 폴더로 이동합니다.
3. **학생 명단(선택):** `private/roster.csv`를 만들고 첫 줄에 `학번,이름`, 아래에 학생을 한 줄씩 적습니다. 미제출 명단과 다른 학생 이름 점검에 쓰입니다. (`private/`는 올라가지 않습니다.)
4. **금칙어(선택):** `tools/banned_words.example.txt`를 `private/banned_words.txt`로 복사해 한 줄에 하나씩 학교 기준에 맞게 채웁니다.
5. **GitHub Pages 켜기:** 저장소의 Settings → Pages → Source를 **GitHub Actions**로 선택합니다. 이후 `main`에 `site/` 변경이 올라가면 자동 배포됩니다. 주소는 보통 `https://176-oss.github.io/vibe-coding-class/` 입니다.
6. **앱 설정:** `site/index.html` 맨 위 `CONFIG`에 폼 주소(`FORM1_URL`, `FORM2_URL`, `FORM3_URL`, `VOTE_URL`)를 넣습니다. 비워 두면 해당 버튼이 비활성으로 보입니다. 학생 접속 주소는 `…/vibe-coding-class/` 입니다(앱이 메인 화면).
7. **구글 폼 4개 만들기:** `docs/FORMS.md`를 따라 만듭니다.

## 차시별 교사 할 일

| 시점 | 할 일 |
|---|---|
| 1차시 후 | 폼 1 응답으로 기획서와 서약을 확인하고 주제를 승인합니다. (서약 미확인 명단은 아래 `--form1` 사용) |
| 3차시 후 | 폼 2에서 올라온 게임 파일을 드라이브 폴더째 내려받아 `ingest.py`를 실행합니다. |
| 4차시 전 | `review.csv`를 확인·승인하고 `publish.py`로 공개한 뒤 push합니다. |
| 4차시 | 갤러리 주소를 안내하고, 반별 투표 폼으로 투표를 받습니다. |

## 명령어

```bash
# 1) 제출 파일 점검 (폴더 또는 .zip)
python tools/ingest.py 내려받은폴더 --roster private/roster.csv --form1 폼1응답.csv

# 2) private/review.csv 를 엑셀·구글 시트로 열어 확인하고 승인 칸에 Y 입력
#    (직접 플레이해 본 작품만 승인하세요. 상태가 '실패'인 작품은 승인해도 공개되지 않습니다.)

# 3) 공개 (승인에서 빠진 작품은 공개 목록에서 제거됩니다)
python tools/publish.py
python tools/publish.py --dry-run          # 실제로 쓰지 않고 결과만 보기
python tools/publish.py --approve-pass     # 점검 '통과' 작품을 한꺼번에 승인 (직접 확인한 뒤에만)
python tools/publish.py --remove 20315     # 한 작품 비공개로 전환

# 4) 올리기
git add site && git commit -m "작품 공개" && git push
```

`review.csv` 칸 설명: **상태**(통과/경고/실패), **사유**(점검 내용), **제목**(갤러리에 보일 제목, 직접 고칠 수 있음), **승인**(Y), **크기예외**(1~2MB 작품을 허용할 때 Y).
같은 학생이 다시 제출해 파일 내용이 바뀌면 승인이 자동으로 지워져 다시 확인해야 합니다.

## 자동 점검 항목

| 점검 | 결과 |
|---|---|
| 외부 주소, 외부 파일(script·link·@import) | 실패 |
| fetch·XMLHttpRequest·WebSocket·window.open·document.cookie | 실패 |
| 이메일·전화번호 형태, 작성자의 학번·이름이 코드나 제목에 있음 | 실패 |
| 금칙어 | 실패 |
| 크기 1MB 초과 | 실패 (1~2MB는 크기예외 Y로 허용 가능, 2MB 초과는 불가) |
| HTML 전체가 아님 | 실패 |
| 크기 500KB 이상, 제목 없음, eval, 저장 기능(localStorage), 다른 학생 이름처럼 보이는 글자 | 경고 |

자동 점검은 **보조 장치**입니다. 글이나 그림이 부적절한지는 점검하지 못하므로, 공개 전에 선생님이 직접 플레이해 보세요.

## 공개 게임의 보호 장치

- 갤러리는 게임을 분리된 상자(`sandbox`, `allow-same-origin` 없음) 안에서 실행합니다. 게임은 다른 작품이나 학생 앱의 저장 데이터를 읽을 수 없습니다.
- `publish.py`가 공개 파일 맨 앞에 보안 규칙(CSP)을 넣어 게임이 인터넷으로 요청을 보내지 못하게 합니다. 그래서 게임 안의 점수 저장(localStorage)은 갤러리에서 동작하지 않을 수 있습니다.
- 게임 제목은 항상 글자로만 표시되어, 제목에 코드가 들어 있어도 실행되지 않습니다.

## 용량

작품 1개 상한은 1MB입니다. GitHub Pages 사이트 한도는 1GB이고, `publish.py`가 실행할 때마다 총 용량을 알려 줍니다. 600MB를 넘으면 저장소를 반 묶음별로 나누세요. 같은 작품을 여러 번 바꿔 올리면 git 기록이 쌓이므로, 공개는 3차시가 끝난 뒤 한 번에 하는 것을 권합니다.

## 개발과 테스트

```bash
python tests/test_tools.py                    # 수합·공개 스크립트 (표준 라이브러리만 필요)
pip install playwright && playwright install chromium
python tests/test_app.py                      # 학생용 앱
python tests/test_gallery.py                  # 가상 제출 480개 → 갤러리까지 전체 확인
```

## 문제 해결

| 증상 | 확인할 것 |
|---|---|
| 갤러리에 "목록을 불러오지 못했어요" | 파일을 더블클릭해 연 것이 아니라 Pages 주소로 접속했는지 확인하세요. |
| 게임이 갤러리에서 안 움직임 | `review.csv`의 사유에서 `STORAGE`(저장 기능) 경고를 확인하고, 해당 기능을 빼도록 학생에게 안내하세요. |
| `ingest.py`가 학번을 못 읽음 | 학생이 앱의 [내려받기]로 만든 파일인지 확인하세요. 표식이 없으면 파일 이름에서 학번을 추정하고 경고를 표시합니다. |
| 폼이 .html 파일을 거부함 | 폼 파일 형식 선택과 학교 관리자의 업로드 제한(DLP)을 확인하세요. |
