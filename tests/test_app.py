"""학생용 앱 자동 테스트. 실행: pip install playwright && playwright install chromium && python tests/test_app.py"""
import json, sys
from playwright.sync_api import sync_playwright
import pathlib, tempfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
URL=(ROOT/'site/index.html').as_uri()
OUT=tempfile.mkdtemp(prefix='vibe_test_')+'/'
res=[]
def ok(name,cond,extra=''):
    res.append((name,bool(cond),extra)); print(('PASS' if cond else 'FAIL'),name,extra)
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={'width':1100,'height':900},permissions=['clipboard-read','clipboard-write'],accept_downloads=True)
    pg=ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
    pg.goto(URL)
    ok('초기: 1차시 본문 잠김',pg.eval_on_selector('#t1body','e=>e.classList.contains("lock")'))
    ok('초기: 칩 서약 전',pg.inner_text('#pchip')=='서약 전')
    pg.fill('#sid','999'); ok('잘못된 학번 안내','5자리' in pg.inner_text('#idinfo'))
    pg.fill('#sid','20315'); pg.fill('#sname','김하늘')
    ok('학번 해석','2학년 3반 15번' in pg.inner_text('#idinfo'),pg.inner_text('#idinfo'))
    pg.click('#signbtn'); ok('팝업 열림',pg.eval_on_selector('#pov','e=>e.classList.contains("on")'))
    pg.screenshot(path=OUT+'modal.png')
    pg.click('#pok'); ok('체크 안 하면 막힘','①' in pg.inner_text('#perr'))
    pg.eval_on_selector_all('#pl input','es=>es.forEach(e=>e.click())')
    pg.click('#pok'); ok('이름 미입력 막힘','②' in pg.inner_text('#perr'))
    pg.fill('#pname','김하날'); pg.click('#pok'); ok('이름 불일치 막힘','②' in pg.inner_text('#perr'))
    pg.fill('#pname','김하늘'); pg.click('#pok'); ok('서명 없으면 막힘','③' in pg.inner_text('#perr'))
    bb=pg.locator('#sigc').bounding_box()
    pg.mouse.move(bb['x']+40,bb['y']+100); pg.mouse.down()
    for i in range(30): pg.mouse.move(bb['x']+40+i*15,bb['y']+100+(40 if i%2 else -40))
    pg.mouse.up()
    pg.screenshot(path=OUT+'modal_signed.png')
    pg.click('#pok')
    ok('서명 후 팝업 닫힘',not pg.eval_on_selector('#pov','e=>e.classList.contains("on")'))
    ok('칩 서약 완료',pg.inner_text('#pchip')=='서약 완료')
    ok('본문 잠금 해제',not pg.eval_on_selector('#t1body','e=>e.classList.contains("lock")'))
    st=json.loads(pg.evaluate('localStorage.getItem("vibe_class_v2")'))
    ok('서명 이미지는 저장 안 함','sign' not in st['f'] and 'data:image' not in json.dumps(st))
    # 이름 변경 시 해제
    pg.fill('#sname','홍길동'); ok('이름 바꾸면 서약 해제',pg.inner_text('#pchip')=='서약 전')
    pg.fill('#sname','김하늘'); ok('원래 이름이면 복구',pg.inner_text('#pchip')=='서약 완료')
    # 아이디어 상담 (1차시)
    pg.fill('#i1','원소와 주기율표'); pg.click('text=상담 프롬프트 만들기')
    ip=pg.input_value('#ideap'); ok('상담 프롬프트: 주제·코드 금지·안전 규칙','원소와 주기율표' in ip and '코드는 만들지 말고' in ip and '[안전 규칙]' in ip)
    # 기획서 (1차시) → 프롬프트 (2차시)
    pg.click('#nav button[data-t=t2]')
    ok('기획서 비었을 때 안내','1차시 기획서를 채우세요' in pg.inner_text('#planview'))
    pg.click('text=프롬프트로 합치기'); ok('기획서 없으면 합치기 막힘',pg.input_value('#prompt1')=='')
    pg.click('#nav button[data-t=t1]')
    pg.fill('[data-k=title]','원소 짝꿍 찾기'); pg.select_option('[data-k=kind]','과학 개념 게임')
    pg.fill('[data-k=concept]','원소 기호'); pg.fill('[data-k=user]','우리 반 친구들')
    pg.fill('[data-k=feat1]','카드 짝 맞추기'); pg.fill('[data-k=feat2]','점수'); pg.fill('[data-k=sketch]','파란색, 큰 카드')
    pg.click('#nav button[data-t=t2]')
    pv=pg.inner_text('#planview'); ok('기획서 내용이 2차시에 표시','원소 짝꿍 찾기' in pv and '카드 짝 맞추기' in pv and '비어 있어요' not in pv)
    pg.fill('#f1','웹 개발자'); pg.fill('#f6','난이도 선택'); pg.click('text=프롬프트로 합치기')
    v=pg.input_value('#prompt1')
    ok('프롬프트에 기획서·추가 요구사항·안전 규칙',all(x in v for x in ['너는 웹 개발자야','원소 짝꿍 찾기','우리 반 친구들','1) 카드 짝 맞추기','원소 기호','파란색, 큰 카드','난이도 선택','[Gemini Canvas용 개발 지침]','순수 JavaScript','첫 화면에 게임 제목과 시작 버튼','[안전 규칙]']),v)
    pg.screenshot(path=OUT+'t2_prompt.png',full_page=True)
    pg.fill('#prompt1','내 마음대로'); pg.click('#t2 >> text=📋 복사')
    ok('복사 시 개발 지침·안전 규칙 자동 복원','[안전 규칙]' in pg.input_value('#prompt1') and '[Gemini Canvas용 개발 지침]' in pg.input_value('#prompt1'))
    pv2=pg.input_value('#prompt1'); ok('복원해도 중복 없음',pv2.count('[안전 규칙]')==1 and pv2.count('[Gemini Canvas용 개발 지침]')==1)
    pg.click('#nav button[data-t=t1]')
    # 요약 복사
    pg.fill('[data-k=title]','원소 퀴즈'); pg.click("#t1 button:has-text('제출용 요약 복사')")
    pg.wait_for_timeout(300)
    clip=pg.evaluate('navigator.clipboard.readText()')
    ok('요약 복사 내용','[1차시 기획] 20315 김하늘 (2학년 3반 15번)' in clip and '서약서:' in clip and '원소 퀴즈' in clip and '불편할 사람 점검' in clip, clip[:80].replace('\n',' | '))
    # 2~3차시
    pg.click('#nav button[data-t=t2]')
    ok('2~3차시: 서명 배너 숨김',not pg.is_visible('#t2 .signbanner'))
    pg.screenshot(path=OUT+'t2_top.png',full_page=False)
    bad='<!DOCTYPE html><html><head><title>t</title><script src="https://cdn.x.com/a.js"></script></head><body>김하늘 20315 <script>fetch("http://evil.com/x");eval("1")</script></body></html>'
    pg.fill('#gcode',bad)
    ok('게임 이름 없으면 내려받기 막힘',pg.is_disabled('#gdl') and '게임 이름' in pg.inner_text('#gwarn'))
    pg.fill('#gtitle','김하늘 게임'); ok('이름에 내 이름 있으면 막힘',pg.is_disabled('#gdl'))
    pg.fill('#gtitle','원소 짝꿍'); pg.fill('#gdesc','원소 카드를 짝지어요')
    w=pg.inner_text('#gwarn'); ok('점검: 외부주소/외부파일/API/이름 경고','외부 주소' in w and '외부 파일' in w and 'fetch' in w and '학번이나 이름' in w, w[:100].replace('\n',' | '))
    ok('경고 있어도 내려받기는 가능(교사가 최종 판단)',not pg.is_disabled('#gdl'))
    pg.fill('#gcode','<p>조각 코드</p>'); ok('전체 코드 아님 경고','전체가 아닌' in pg.inner_text('#gwarn'))
    big='<!DOCTYPE html><html><head><title>t</title></head><body>'+('가'*400000)+'</body></html>'
    pg.fill('#gcode',big)
    ok('1MB 초과: 내려받기 비활성',pg.is_disabled('#gdl'),pg.inner_text('#barlbl'))
    ok('1MB 초과: 막대 빨강',pg.eval_on_selector('#barfill','e=>e.className')=='r')
    mid='<!DOCTYPE html><html><head><title>t</title></head><body>'+('a'*600000)+'</body></html>'
    pg.fill('#gcode',mid); ok('600KB: 노랑',pg.eval_on_selector('#barfill','e=>e.className')=='y',pg.inner_text('#barlbl'))
    good='<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>원소 퀴즈</title></head><body><h1>퀴즈</h1><svg xmlns="http://www.w3.org/2000/svg"></svg></body></html>'
    pg.fill('#gcode',good); ok('정상 코드: 통과 메시지','문제를 찾지 못했어요' in pg.inner_text('#gwarn'),pg.inner_text('#gwarn')); ok('막대 초록',pg.eval_on_selector('#barfill','e=>e.className')=='')
    pg.screenshot(path=OUT+'t2_export.png',full_page=True)
    with pg.expect_download() as d: pg.click('#gdl')
    dd=d.value; path=OUT+dd.suggested_filename; dd.save_as(path); txt=open(path,encoding='utf-8').read()
    ok('다운로드 파일 이름','20315_김하늘.html'==dd.suggested_filename,dd.suggested_filename)
    ok('첫 줄 제출 표식 + 게임 정보',txt.startswith('<!-- vibe-submit:20315|김하늘 -->\n<!-- vibe-info:') and '\n<!DOCTYPE html>' in txt[:300],txt[:120])
    import urllib.parse as up; info=json.loads(up.unquote(txt.split('vibe-info:')[1].split(' -->')[0])); ok('게임 정보 내용',info=={'t':'원소 짝꿍','d':'원소 카드를 짝지어요'},str(info))
    # 재내보내기 시 표식 중복 방지
    pg.fill('#gcode',txt)
    with pg.expect_download() as d2: pg.click('#gdl')
    t2=d2.value; t2.save_as(OUT+'re.html'); r=open(OUT+'re.html',encoding='utf-8').read()
    ok('표식 중복 없음',r.count('vibe-submit')==1 and r.count('vibe-info')==1)
    # 2~3차시 요약
    pg.click("#t2 >> text=제출용 요약 복사"); pg.wait_for_timeout(300)
    clip=pg.evaluate('navigator.clipboard.readText()'); ok('2~3차시 요약에 표 포함','제작 일지' in clip and '피드백 카드' in clip and '불편했던 부분' in clip)
    # 4차시
    pg.click('#nav button[data-t=t3]'); ok('4차시 탭에 갤러리 iframe',pg.locator('#galframe').count()==1)
    ok('폼 4개 링크 연결',all((pg.get_attribute(f'[data-link=FORM{i}_URL]','href') or '').startswith('https://forms.gle/') for i in (1,2,3,4)))
    pg.screenshot(path=OUT+'t3.png')
    # 백업
    with pg.expect_download() as d3: pg.click('.bk >> text=백업 저장')
    bj=json.load(open(d3.value.path(),encoding='utf-8')); ok('백업 JSON',bj['v']==2 and bj['f']['sid']=='20315' and 'sign' not in bj['f'])
    # 새로고침 시 유지
    pg.reload(); ok('새로고침 후 서약·학번 유지',pg.inner_text('#pchip')=='서약 완료' and pg.input_value('#sid')=='20315')
    # 모바일 팝업
    ctx2=b.new_context(viewport={'width':390,'height':780},has_touch=True,is_mobile=True)
    m=ctx2.new_page(); m.goto(URL); m.fill('#sid','10107'); m.fill('#sname','이서준'); m.click('#signbtn'); m.screenshot(path=OUT+'modal_mobile.png')
    # 미서명 상태 차단
    m.click('#pcancel'); ok('서명 전 1차시 본문 버튼은 잠김',m.eval_on_selector('#t1body','e=>getComputedStyle(e).pointerEvents')=='none'); m.click('#nav button[data-t=t2]'); m.click("#t2 button:has-text('제출용 요약 복사')"); m.wait_for_timeout(200); ok('미서명 요약 복사 차단','서약서에 서명' in m.inner_text('#toast'),m.inner_text('#toast'))
    errs=[e for e in errs if 'URL scheme "file"' not in e]  # 파일로 직접 열면 끼워 넣은 갤러리는 목록을 못 읽는다(정상)
    ok('JS 오류 없음',not errs,str(errs))
    b.close()
print('\nFAILED:',[r[0] for r in res if not r[1]])
