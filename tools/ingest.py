#!/usr/bin/env python3
"""학생 제출 파일(.html)을 읽어 점검하고 private/review.csv 를 만든다.

사용법:
  python tools/ingest.py <제출 폴더 또는 .zip> [--roster private/roster.csv] [--form1 폼1응답.csv]

- 학번·이름은 파일 첫 줄의 제출 표식에서 읽는다 (파일 이름에 의존하지 않음).
- 표식을 뺀 원본은 private/submissions/<학번>.html 에 저장된다 (공개되지 않음).
- review.csv 의 '승인' 칸에 Y 를 적은 작품만 publish.py 로 공개할 수 있다.
"""
import argparse
import re
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def collect(src):
    src = Path(src)
    if src.is_file() and src.suffix.lower() == '.zip':
        tmp = Path(tempfile.mkdtemp(prefix='vibe_zip_'))
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        src = tmp
    if src.is_file():
        return [src]
    return sorted(p for p in src.rglob('*') if p.is_file() and p.suffix.lower() in ('.html', '.htm', '.txt'))


def guess_from_filename(path):
    m = re.match(r'^(\d{5})[_\-\s]*([^\-.]*)', path.name)
    return (m[1], m[2].strip()) if m else (None, None)


def build_roster_re(roster):
    names = sorted({n for n in roster.values() if len(n) >= 3})
    return re.compile('|'.join(re.escape(n) for n in names)) if names else None


def run(src, roster_path=None, form1=None, out=print):
    C.PRIVATE.mkdir(parents=True, exist_ok=True)
    C.SUBMISSIONS.mkdir(parents=True, exist_ok=True)
    banned = C.load_banned()
    roster = C.load_roster() if (roster_path is None and C.ROSTER.exists()) else {}
    if roster_path:
        C.ROSTER = Path(roster_path)  # noqa: N806
        roster = C.load_roster()
    roster_re = build_roster_re(roster)

    # 같은 학번이 여러 번 제출되면 가장 나중 파일만 쓴다
    latest, dupes, unknown = {}, defaultdict(int), []
    for p in collect(src):
        text = p.read_bytes().decode('utf-8', errors='replace')
        sid, name, body = C.split_marker(text)
        notes = []
        if not sid:
            sid, name = guess_from_filename(p)
            notes.append(('warn', 'MARKER', '제출 표식이 없어 파일 이름에서 학번을 추정함'))
        if not sid or not C.parse_id(sid):
            unknown.append(p.name)
            continue
        if sid in latest:
            dupes[sid] += 1
            if p.stat().st_mtime < latest[sid]['mtime']:
                continue
        latest[sid] = {'path': p, 'name': name or '', 'body': body, 'notes': notes, 'mtime': p.stat().st_mtime}

    old = {r['학번']: r for r in C.read_csv(C.REVIEW)}
    rows = []
    for sid, d in sorted(latest.items()):
        results = d['notes'] + C.check_html(d['body'], sid, d['name'], banned, roster_re)
        title = C.get_title(d['body'])
        if title and (sid in title or (len(d['name']) >= 2 and d['name'] in title)):
            results.append(('fail', 'NAME_IN_CODE', '제목에 학번 또는 이름이 있음'))
        h = C.sha(d['body'])
        (C.SUBMISSIONS / f'{sid}.html').write_text(d['body'], encoding='utf-8')
        g, c, n = C.parse_id(sid)
        prev = old.get(sid, {})
        same = prev.get('해시') == h  # 내용이 같을 때만 교사가 적은 승인·제목을 유지
        rows.append({
            '학번': sid, '이름': d['name'], '반': c, '번호': n,
            '상태': C.status_of(results),
            '사유': ' / '.join(r[2] for r in results),
            '실패코드': ';'.join(r[1] for r in results if r[0] == 'fail'),
            '제목': (prev.get('제목') if same and prev.get('제목') else title),
            '크기': C.size_of(d['body']),
            '승인': prev.get('승인', '') if same else '',
            '크기예외': prev.get('크기예외', '') if same else '',
            '해시': h, '파일': d['path'].name,
        })
    keep = [r for sid, r in old.items() if sid not in latest]  # 이번 폴더에 없던 이전 제출은 보존
    rows = sorted(rows + keep, key=lambda r: (int(r['반'] or 0), int(r['번호'] or 0)))
    C.write_csv(C.REVIEW, C.REVIEW_FIELDS, rows)

    cnt = Counter(r['상태'] for r in rows)
    out(f"\n점검 완료: {len(latest)}개 읽음 → 통과 {cnt['통과']} / 경고 {cnt['경고']} / 실패 {cnt['실패']}")
    if dupes:
        out(f"같은 학번이 여러 번 제출됨 (마지막 파일만 사용): {len(dupes)}명")
    if unknown:
        out(f"학번을 알 수 없어 건너뜀: {len(unknown)}개 {unknown[:5]}")
    per = Counter(int(r['반']) for r in rows)
    out('반별 제출: ' + ', '.join(f'{c}반 {per[c]}' for c in sorted(per)))
    if roster:
        miss = [s for s in sorted(roster) if s not in {r['학번'] for r in rows}]
        out(f'\n게임 미제출 {len(miss)}명 (명단 {len(roster)}명 기준)')
        by = defaultdict(list)
        for s in miss:
            by[C.parse_id(s)[1]].append(f"{C.parse_id(s)[2]}번 {roster[s]}")
        for c in sorted(by):
            out(f"  {c}반: " + ', '.join(by[c]))
    if form1:
        pledged = set()
        for r in C.read_csv(form1):
            cells = list(r.values())
            sid = next((str(v).strip() for k, v in r.items() if '학번' in k and v), '')
            if sid and any('서명 완료' in str(v) for v in cells):
                pledged.add(sid)
        if roster:
            miss = [s for s in sorted(roster) if s not in pledged]
            out(f'\n서약 미확인 {len(miss)}명: ' + ', '.join(f'{C.parse_id(s)[1]}반 {C.parse_id(s)[2]}번 {roster[s]}' for s in miss[:30]) + (' ...' if len(miss) > 30 else ''))
        else:
            out(f'\n1차시 폼 응답에서 서약이 확인된 학생: {len(pledged)}명 (roster.csv가 있으면 미확인 명단도 보여 줍니다)')
    out(f'\n다음 단계: {C.REVIEW} 을 열어 승인 칸에 Y 를 적고 python tools/publish.py 를 실행하세요.')
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', help='드라이브에서 내려받은 제출 폴더 또는 .zip')
    ap.add_argument('--roster', help='학번,이름 명단 CSV (미제출 명단과 다른 학생 이름 점검에 사용)')
    ap.add_argument('--form1', help='1차시 폼 응답 CSV (서약 확인에 사용)')
    a = ap.parse_args(argv)
    run(a.src, a.roster, a.form1)


if __name__ == '__main__':
    main()
