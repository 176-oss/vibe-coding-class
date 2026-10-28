"""갤러리 통합 테스트: 가상 제출 480개 → ingest → publish → 브라우저로 갤러리 확인.
실행: pip install playwright && playwright install chromium && python tests/test_gallery.py [스크린샷 폴더]
"""
import functools
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

REPO = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix='vibe_gal_'))
ROOT = TMP / 'root'
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else TMP / 'shots'
SHOTS.mkdir(parents=True, exist_ok=True)
ENV = dict(os.environ, VIBE_ROOT=str(ROOT))
res = []


def ok(name, cond, extra=''):
    res.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name, extra)


QUIZ = '''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:sans-serif;text-align:center;background:#e0f2fe;padding:20px}}button{{font-size:20px;margin:6px;padding:12px 22px;border:0;border-radius:10px;background:#38bdf8}}</style></head>
<body><h1>⚗️ 원소 기호 퀴즈</h1><p>점수: <b id="s">0</b></p><div id="q">수소의 원소 기호는?</div><button onclick="document.getElementById('s').textContent=1">H</button><button>He</button><button>O</button></body></html>'''
PROBE = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>probe</title></head><body><ul id="r"></ul><script>
function log(k,v){var li=document.createElement('li');li.id=k;li.textContent=v;document.getElementById('r').appendChild(li)}
try{localStorage.setItem('x','1');log('ls','allowed')}catch(e){log('ls','blocked')}
try{var t=parent.document.title;log('parent','allowed')}catch(e){log('parent','blocked')}
try{log('cookie',document.cookie===''?'empty':'has')}catch(e){log('cookie','blocked')}
setTimeout(function(){log('done','1')},1500);
</script></body></html>'''


def build_site():
    (ROOT / 'site').mkdir(parents=True)
    for f in ('index.html', 'class.html', 'play.html', 'gallery.css', 'gallery.js'):
        shutil.copy(REPO / 'site' / f, ROOT / 'site' / f)
    inp = TMP / 'in'
    inp.mkdir()
    for c in range(1, 17):
        for n in range(1, 31):
            if c == 16 and n > 12:
                continue          # 16반은 12개만
            if c == 15:
                continue          # 15반은 작품 없음
            sid = f'2{c:02d}{n:02d}'
            title = f'{c}반 {n}번째 게임'
            body = QUIZ.format(title=title)
            if (c, n) == (3, 1):
                body = QUIZ.format(title='원소 기호 퀴즈')
            if (c, n) == (3, 2):
                body = QUIZ.format(title='&lt;b&gt;굵게&lt;/b&gt; 제목이 아주 길어지면 어떻게 보이는지 확인하는 긴 제목 입니다 정말 길어요')
            (inp / f'{sid}.html').write_text(f'<!-- vibe-submit:{sid}|학생{c}-{n} -->\n' + body, encoding='utf-8')
    for cmd in (['tools/ingest.py', str(inp)], ['tools/publish.py', '--approve-pass']):
        r = subprocess.run([sys.executable, str(REPO / cmd[0])] + cmd[1:], env=ENV, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        print(r.stdout.strip().splitlines()[-3:])
    return inp


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Cors(Quiet):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


def serve(handler, directory):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(handler, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    os.environ['VIBE_ROOT'] = str(ROOT)
    import publish
    build_site()
    site = ROOT / 'site'
    # 프로브 게임(보안 시험용): 점검을 거치지 않고 직접 넣어 둔다 (3반 5번 코드를 덮어씀)
    import json
    d = json.loads((site / 'data' / 'class03.json').read_text(encoding='utf-8'))
    code = d['games'][4]['code']
    (site / 'games' / '03' / f'{code}.html').write_text(publish.harden(PROBE), encoding='utf-8')
    other = TMP / 'other'
    other.mkdir()
    (other / 'secret.txt').write_text('ok', encoding='utf-8')
    s1, s2 = serve(Quiet, site), serve(Cors, other)
    base = f'http://127.0.0.1:{s1.server_address[1]}/'
    net = f'http://127.0.0.1:{s2.server_address[1]}/secret.txt'
    # 네트워크 시험 프로브: 외부(다른 포트, CORS 허용) 서버로 요청하는 게임
    code7 = d['games'][6]['code']
    (site / 'games' / '03' / f'{code7}.html').write_text(publish.harden(
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>net</title></head><body><p id="r">대기</p><script>'
        f'fetch("{net}").then(function(r){{return r.text()}}).then(function(t){{document.getElementById("r").textContent="reached:"+t}})'
        f'.catch(function(e){{document.getElementById("r").textContent="blocked"}})</script></body></html>'), encoding='utf-8')

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1100, 'height': 800})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(base + 'index.html')
        pg.wait_for_selector('#classes .tile')
        ok('반 타일 16개', pg.locator('#classes li').count() == 16)
        ok('작품 있는 반은 링크, 없는 반(15반)은 비활성', pg.locator('#classes a.tile').count() == 15 and 'class.html?c=3' in pg.get_attribute('#classes a.tile >> nth=2', 'href'))
        ok('15반 아직 없어요', '아직 없어요' in pg.locator('#classes li').nth(14).inner_text())
        pg.screenshot(path=str(SHOTS / 'gallery_index.png'), full_page=True)

        pg.goto(base + 'class.html?c=3')
        pg.wait_for_selector('#games .tile')
        ok('3반 작품 30개, 번호 1~30', pg.locator('#games .tile').count() == 30 and pg.locator('#games .no').nth(29).inner_text() == '30')
        ok('제목의 HTML이 글자 그대로 보임(XSS 방지)', pg.locator('#games .tile').nth(1).locator('.ttl').inner_text().startswith('<b>굵게</b>') and pg.locator('#games .ttl b').count() == 0)
        ok('화면 어디에도 학번·이름이 없음', not any(s in pg.inner_text('body') for s in ('20301', '학생3-1')))
        pg.screenshot(path=str(SHOTS / 'gallery_class.png'), full_page=True)
        pg.fill('#num', '1')
        ok('번호로 찾기: 1, 10~19', sum(1 for i in range(30) if pg.locator('#games li').nth(i).is_visible()) == 11)
        pg.fill('#num', '')

        pg.goto(base + 'class.html?c=15'); pg.wait_for_selector('.msg')
        ok('작품 없는 반 안내', '아직 올라온 작품이 없어요' in pg.inner_text('main'))
        pg.goto(base + 'class.html?c=16'); pg.wait_for_selector('#games .tile')
        ok('16반 12개', pg.locator('#games .tile').count() == 12)

        pg.goto(base + 'play.html?c=3&n=1'); pg.wait_for_selector('iframe')
        fr = pg.frame_locator('iframe')
        ok('게임이 갤러리 안에서 실행됨', fr.locator('h1').inner_text() != '' and '퀴즈' in fr.locator('h1').inner_text())
        fr.get_by_role('button', name='H', exact=True).click()
        ok('게임 조작이 동작함', fr.locator('#s').inner_text() == '1')
        ok('제목과 번호 표시', pg.inner_text('#pno') == '1' and pg.inner_text('#ptitle') == '원소 기호 퀴즈')
        ok('이전 작품 없음/다음 작품 있음', pg.get_attribute('#prev', 'aria-disabled') == 'true' and 'n=2' in pg.get_attribute('#next', 'href'))
        sb = pg.get_attribute('iframe', 'sandbox')
        ok('iframe sandbox 에 allow-same-origin 이 없음', 'allow-scripts' in sb and 'allow-same-origin' not in sb, sb)
        pg.screenshot(path=str(SHOTS / 'gallery_play.png'))

        pg.goto(base + 'play.html?c=3&n=5'); pg.wait_for_selector('iframe')
        fr = pg.frame_locator('iframe'); fr.locator('#done').wait_for(timeout=5000)
        ok('게임에서 localStorage 사용 불가(앱·다른 작품 데이터 보호)', fr.locator('#ls').inner_text() == 'blocked')
        ok('게임에서 갤러리 페이지 접근 불가', fr.locator('#parent').inner_text() == 'blocked')
        pg.goto(base + 'play.html?c=3&n=7'); pg.wait_for_selector('iframe')
        fr = pg.frame_locator('iframe'); pg.wait_for_timeout(1500)
        txt = fr.locator('#r').inner_text()
        ok('게임에서 외부 서버로 요청 불가(CSP)', txt == 'blocked', txt)

        raw = (site / 'games' / '03' / f'{code7}.html').read_text(encoding='utf-8').replace(publish.CSP_META, '')
        (site / 'games' / '03' / f'{code7}.html').write_text(raw, encoding='utf-8')
        pg.goto(base + 'play.html?c=3&n=7'); pg.wait_for_selector('iframe'); pg.wait_for_timeout(1500)
        txt = pg.frame_locator('iframe').locator('#r').inner_text()
        ok('(대조) CSP 를 빼면 외부 요청이 통과함 → 위 시험이 의미 있음', txt.startswith('reached'), txt)

        for bad in ('play.html?c=3&n=99', 'play.html?c=99&n=1', 'play.html'):
            pg.goto(base + bad); pg.wait_for_selector('.msg')
            ok('잘못된 주소 안내 ' + bad, 'iframe' not in pg.content().split('<script')[0] or pg.locator('iframe').count() == 0)

        m = b.new_context(viewport={'width': 390, 'height': 800}, is_mobile=True, has_touch=True).new_page()
        m.goto(base + 'class.html?c=3'); m.wait_for_selector('#games .tile')
        m.screenshot(path=str(SHOTS / 'gallery_class_mobile.png'))
        m.goto(base + 'index.html'); m.wait_for_selector('#classes .tile')
        ok('모바일 가로 스크롤 없음', m.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        ok('JS 오류 없음', not errs, str(errs))
        b.close()
    s1.shutdown(); s2.shutdown()
    bad = [n for n, c in res if not c]
    print('\nFAILED:', bad)
    shutil.rmtree(TMP / 'root', ignore_errors=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
