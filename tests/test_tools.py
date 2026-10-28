"""교사용 스크립트 테스트. 실행: python tests/test_tools.py  (표준 라이브러리만 사용)"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='vibe_tools_'))
os.environ['VIBE_ROOT'] = str(TMP / 'root')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import common as C  # noqa: E402
import ingest  # noqa: E402
import publish  # noqa: E402

QUIET = lambda *a, **k: None  # noqa: E731


def page(title='원소 퀴즈', body='<h1>퀴즈</h1>', extra=''):
    return f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title></head><body>{body}{extra}</body></html>'


def submit(folder, sid, name, html, marker=True):
    folder.mkdir(parents=True, exist_ok=True)
    text = (f'<!-- vibe-submit:{sid}|{name} -->\n' if marker else '') + html
    p = folder / f'{sid}_{name}.html'
    p.write_text(text, encoding='utf-8')
    return p


def reset():
    for d in (C.PRIVATE, C.SITE, TMP / 'in'):
        shutil.rmtree(d, ignore_errors=True)


def approve(rows_filter=None, **extra):
    rows = C.read_csv(C.REVIEW)
    for r in rows:
        if rows_filter is None or rows_filter(r):
            r['승인'] = 'Y'
            r.update(extra)
    C.write_csv(C.REVIEW, C.REVIEW_FIELDS, rows)


def review():
    return {r['학번']: r for r in C.read_csv(C.REVIEW)}


class Checks(unittest.TestCase):
    def test_marker(self):
        sid, name, body = C.split_marker('<!-- vibe-submit:20315|김하늘 -->\n<!DOCTYPE html><html></html>')
        self.assertEqual((sid, name), ('20315', '김하늘'))
        self.assertTrue(body.startswith('<!DOCTYPE'))
        self.assertEqual(C.split_marker('<html></html>')[0], None)

    def test_parse_id(self):
        self.assertEqual(C.parse_id('20315'), (2, 3, 15))
        for bad in ('999', '20015', '21715', '20300', '2031a', ''):
            self.assertIsNone(C.parse_id(bad), bad)

    def codes(self, html, name='김하늘', banned=()):
        return {c for _, c, _ in C.check_html(html, '20315', name, banned)}

    def test_rules(self):
        self.assertEqual(self.codes(page()), set())
        self.assertIn('EXT_URL', self.codes(page(extra='<a href="https://x.com">x</a>')))
        self.assertNotIn('EXT_URL', self.codes(page(extra='<svg xmlns="http://www.w3.org/2000/svg"></svg>')))
        self.assertIn('EXT_FILE', self.codes(page(extra='<script src="a.js"></script>')))
        self.assertIn('API', self.codes(page(extra='<script>fetch("/x")</script>')))
        self.assertIn('NAME_IN_CODE', self.codes(page(extra='김하늘')))
        self.assertIn('NAME_IN_CODE', self.codes(page(extra='20315')))
        self.assertIn('PII', self.codes(page(extra='010-1234-5678')))
        self.assertIn('PII', self.codes(page(extra='a@b.com')))
        self.assertIn('STORAGE', self.codes(page(extra='<script>localStorage.x=1</script>')))
        self.assertIn('BANNED', self.codes(page(extra='금칙어예시'), banned=['금칙어예시']))
        self.assertIn('INCOMPLETE', self.codes('<p>조각</p>'))
        self.assertIn('TITLE', self.codes(page(title='')))


class Pipeline(unittest.TestCase):
    def setUp(self):
        reset()
        self.inp = TMP / 'in'

    def test_small_flow(self):
        submit(self.inp, '20301', '가나다', page('좋은 게임'))
        submit(self.inp, '20302', '나다라', page('외부', extra='<script src="https://cdn.x/a.js"></script>'))
        submit(self.inp, '20303', '다라마', page('표식 없음'), marker=False)
        submit(self.inp, '20304', '라마바', page('큼', body='가' * 600000))        # 1.7MB → 크기 예외 대상
        submit(self.inp, '20305', '마바사', page('초과', body='가' * 900000))       # 2.7MB → 예외도 불가
        submit(self.inp, '20306', '바사아', page('제목에 이름', extra='') .replace('제목에 이름', '바사아의 게임'))
        ingest.run(self.inp, out=QUIET)
        r = review()
        self.assertEqual(r['20301']['상태'], '통과')
        self.assertEqual(r['20302']['상태'], '실패')
        self.assertIn('EXT_FILE', r['20302']['실패코드'])
        self.assertEqual(r['20303']['상태'], '경고')           # 표식이 없어도 파일 이름에서 추정
        self.assertEqual(r['20304']['실패코드'], 'SIZE')
        self.assertIn('SIZE_HARD', r['20305']['실패코드'])
        self.assertEqual(r['20306']['상태'], '실패')           # 제목에 이름
        # 승인하지 않으면 공개되지 않는다
        res = publish.run(out=QUIET)
        self.assertEqual(res['published'], 0)
        # 전부 승인해도 실패 작품은 막힌다 (크기 예외 표시가 없으면 20304도 막힘)
        approve()
        res = publish.run(out=QUIET)
        self.assertEqual(sorted(s for s, _ in res['skipped']), ['20302', '20304', '20305', '20306'])
        self.assertEqual(res['published'], 2)
        # 크기 예외: 1~2MB 는 교사가 허용하면 공개, 2MB 초과는 불가
        approve(lambda x: x['학번'] in ('20304', '20305'), 크기예외='Y')
        res = publish.run(out=QUIET)
        self.assertEqual(sorted(s for s, _ in res['skipped']), ['20302', '20305', '20306'])
        self.assertEqual(res['published'], 3)

    def test_resubmit_resets_approval_and_remove_keeps_number(self):
        submit(self.inp, '20301', '가나다', page('첫 버전'))
        submit(self.inp, '20302', '나다라', page('둘째'))
        ingest.run(self.inp, out=QUIET)
        approve()
        publish.run(out=QUIET)
        m = {x['학번']: x for x in C.read_csv(C.MAPPING)}
        self.assertEqual((m['20301']['번호'], m['20302']['번호']), ('1', '2'))
        # 비공개 전환 → 파일 제거, 번호는 유지
        publish.run(remove=['20301'], out=QUIET)
        data = json.loads((C.SITE / 'data' / 'class03.json').read_text(encoding='utf-8'))
        self.assertEqual([g['n'] for g in data['games']], [2])
        self.assertEqual(len(list((C.SITE / 'games' / '03').glob('*.html'))), 1)
        approve(lambda x: x['학번'] == '20301')
        publish.run(out=QUIET)
        m = {x['학번']: x for x in C.read_csv(C.MAPPING)}
        self.assertEqual(m['20301']['번호'], '1')
        # 내용이 바뀐 재제출은 승인이 초기화된다
        submit(self.inp, '20301', '가나다', page('수정 버전', body='<h1>바뀜</h1>'))
        ingest.run(self.inp, out=QUIET)
        self.assertEqual(review()['20301']['승인'], '')
        self.assertEqual(review()['20302']['승인'], 'Y')   # 그대로인 작품은 유지

    def test_480_students(self):
        names, sids = {}, []
        for c in range(1, 17):
            for n in range(1, 31):
                sid = f'2{c:02d}{n:02d}'
                name = '김이박최정강조윤장임'[(c * n) % 10] + '하늘서준지우민재도윤예은'[(c + n) % 12] + '진아현'[n % 3]
                names[sid] = name
                sids.append(sid)
                submit(self.inp, sid, name, page(f'게임 {c}-{n}', body=f'<p>{c}반 작품입니다 점수 {n * 7}</p>'))
        ingest.run(self.inp, out=QUIET)
        rows = C.read_csv(C.REVIEW)
        self.assertEqual(len(rows), 480)
        self.assertTrue(all(r['상태'] == '통과' for r in rows), [r['사유'] for r in rows if r['상태'] != '통과'][:3])
        res = publish.run(approve_pass=True, out=QUIET)
        self.assertEqual(res['published'], 480)
        for c in range(1, 17):
            d = json.loads((C.SITE / 'data' / f'class{c:02d}.json').read_text(encoding='utf-8'))
            self.assertEqual([g['n'] for g in d['games']], list(range(1, 31)))
        idx = json.loads((C.SITE / 'data' / 'index.json').read_text(encoding='utf-8'))
        self.assertTrue(all(x['count'] == 30 for x in idx['classes']))
        # 신원 비노출: 공개 폴더 어디에도 학번·이름이 없고, 파일 이름은 코드뿐이다
        files = [p for p in C.SITE.rglob('*') if p.is_file()]
        self.assertEqual(len(list((C.SITE / 'games').rglob('*.html'))), 480)
        for p in files:
            text = p.read_text(encoding='utf-8')
            self.assertNotIn('vibe-submit', text, p)
            for sid in sids:
                self.assertNotIn(sid, p.name)
                self.assertNotIn(sid, text, (p, sid))
            for nm in set(names.values()):
                self.assertNotIn(nm, text, (p, nm))
        codes = [p.stem for p in (C.SITE / 'games').rglob('*.html')]
        self.assertEqual(len(set(codes)), 480)
        self.assertTrue(all(len(c) >= 5 and set(c) <= set(C.ALPHA) for c in codes))
        # 같은 비밀 값이면 다시 실행해도 코드·번호가 그대로다
        before = sorted(codes)
        publish.run(out=QUIET)
        self.assertEqual(sorted(p.stem for p in (C.SITE / 'games').rglob('*.html')), before)
        # private 는 저장소에서 제외된다
        gi = (Path(__file__).resolve().parent.parent / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('private/', gi)

    def test_roster_and_zip(self):
        import zipfile
        submit(self.inp, '20301', '가나다', page())
        z = TMP / 'sub.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            for f in self.inp.glob('*.html'):
                zf.write(f, f.name)
        (C.PRIVATE).mkdir(parents=True, exist_ok=True)
        (C.PRIVATE / 'roster.csv').write_text('학번,이름\n20301,가나다\n20302,나다라\n', encoding='utf-8')
        lines = []
        ingest.run(z, out=lines.append)
        text = '\n'.join(lines)
        self.assertIn('게임 미제출 1명', text)
        self.assertIn('나다라', text)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
