"""공개할 게임의 첫 화면을 찍어 갤러리용 그림(JPEG)으로 저장한다.

publish.py 가 자동으로 부른다. 직접 실행할 때:  python tools/thumbs.py
처음 한 번 설치가 필요하다:  pip install playwright  →  playwright install chromium
설치가 안 되어 있으면 그림 없이 공개되고, 갤러리는 제목 카드로 대신 보여 준다.

- 그림은 site/thumbs/<반>/<코드>.jpg 에 저장되고, 게임 파일이 바뀐 경우에만 다시 찍는다.
- 게임은 보안 규칙(CSP)이 들어간 공개용 파일로 열고, 인터넷 요청은 모두 막는다.
"""
from pathlib import Path

try:
    import common as C
except ImportError:  # 다른 위치에서 불러올 때
    from tools import common as C

W, H = 800, 600          # 게임을 여는 화면 크기 (4:3)
SCALE = 0.5              # 저장 그림은 400x300
WAIT_MS = 1200           # 첫 화면이 그려질 때까지 기다리는 시간
QUALITY = 70


def thumb_path(game_rel):
    """games/03/abcde.html → thumbs/03/abcde.jpg"""
    p = Path(game_rel)
    return Path('thumbs') / p.parent.name / (p.stem + '.jpg')


def make(game_rels, out=print):
    """game_rels: site 기준 상대 경로 목록. 새로 찍은 개수를 돌려준다. 실패하면 None."""
    todo = []
    for rel in game_rels:
        g, t = C.SITE / rel, C.SITE / thumb_path(rel)
        if not t.exists() or t.stat().st_mtime < g.stat().st_mtime:
            todo.append((g, t))
    if not todo:
        return 0
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out('  (첫 화면 그림 생략: playwright 가 설치되지 않았어요. pip install playwright 후 playwright install chromium)')
        return None
    done = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': W, 'height': H}, device_scale_factor=SCALE,
                                  java_script_enabled=True, offline=True)
        ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
        page = ctx.new_page()
        page.on('dialog', lambda d: d.dismiss())          # alert/confirm 가 있어도 멈추지 않게
        for i, (g, t) in enumerate(todo, 1):
            try:
                page.goto(g.resolve().as_uri(), wait_until='load', timeout=10000)
                page.wait_for_timeout(WAIT_MS)
                t.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(t), type='jpeg', quality=QUALITY, timeout=10000)
                done += 1
            except Exception as e:  # 한 작품이 실패해도 나머지는 계속
                out(f'  첫 화면 그림 실패: {g.name} ({type(e).__name__})')
                page.close()
                page = ctx.new_page()
                page.on('dialog', lambda d: d.dismiss())
            if i % 50 == 0:
                out(f'  첫 화면 그림 {i}/{len(todo)}')
        browser.close()
    return done


def clean(keep_games):
    """공개 목록에 없는 게임의 그림을 지운다."""
    keep = {thumb_path(r).as_posix() for r in keep_games}
    d = C.SITE / 'thumbs'
    if d.exists():
        for p in d.rglob('*.jpg'):
            if p.relative_to(C.SITE).as_posix() not in keep:
                p.unlink()


if __name__ == '__main__':
    rels = [p.relative_to(C.SITE).as_posix() for p in sorted((C.SITE / 'games').rglob('*.html'))]
    n = make(rels)
    print(f'첫 화면 그림 {n or 0}개를 새로 만들었어요.')
