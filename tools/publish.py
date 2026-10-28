#!/usr/bin/env python3
"""review.csv 에서 '승인'(Y)된 작품만 site/ 에 공개 파일로 만든다.

사용법:
  python tools/publish.py                 승인된 작품 공개 (승인에서 빠진 작품은 공개 목록에서 제거)
  python tools/publish.py --dry-run       실제로 쓰지 않고 결과만 보기
  python tools/publish.py --approve-pass  '통과' 작품 전체를 승인으로 표시한 뒤 공개 (직접 플레이해 본 뒤에 사용)
  python tools/publish.py --remove 20315  해당 학번 작품을 비공개로 전환

공개 파일 이름은 반 번호와 무작위 코드(예: site/games/03/k7x2q.html)이고, 학번·이름은 쓰지 않는다.
학번 ↔ 코드 대응표는 private/mapping.csv (저장소에 올라가지 않음).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# 공개되는 게임이 인터넷으로 요청을 보내거나 다른 곳으로 이동·전송하지 못하게 막는 보안 규칙.
# 이미지·소리·글꼴은 파일 안에 포함된 것(data:, blob:)만 허용한다.
CSP = ("default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline'; "
       "img-src data: blob:; media-src data: blob:; font-src data:; worker-src blob:; "
       "connect-src 'none'; form-action 'none'; frame-src 'none'; base-uri 'none'")
CSP_META = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'


def harden(body):
    """게임 파일 맨 앞(<head> 바로 뒤)에 CSP 메타 태그를 넣는다. 게임 내용은 바꾸지 않는다."""
    for pat in (r'<head[^>]*>', r'<html[^>]*>'):
        m = re.search(pat, body, re.I)
        if m:
            return body[:m.end()] + CSP_META + body[m.end():]
    return CSP_META + body


def approved(r):
    return (r.get('승인') or '').strip().lower() in C.YES


def blocked_reason(r, body):
    """공개해도 되는지 판단. 막아야 하면 이유를 돌려준다."""
    if r['상태'] == '실패':
        codes = {c for c in (r.get('실패코드') or '').split(';') if c}
        size_ok = codes <= {'SIZE'} and (r.get('크기예외') or '').strip().lower() in C.YES and C.size_of(body) <= C.SIZE_EXCEPT
        if not size_ok:
            return '점검 실패: ' + (r.get('사유') or '')
    title = (r.get('제목') or '').strip()
    sid, name = r['학번'], r['이름']
    if sid in title or (len(name) >= 2 and name in title):
        return '제목에 학번 또는 이름이 있음'
    if sid in body or (len(name) >= 2 and name in body):
        return '코드에 학번 또는 이름이 있음'
    if 'vibe-submit' in body:
        return '제출 표식이 남아 있음'
    return None


def run(dry=False, approve_pass=False, remove=(), out=print):
    rows = C.read_csv(C.REVIEW)
    if not rows:
        out('review.csv 가 없습니다. 먼저 python tools/ingest.py 를 실행하세요.')
        return None
    if approve_pass:
        n = 0
        for r in rows:
            if r['상태'] == '통과' and not approved(r):
                r['승인'] = 'Y'
                n += 1
        out(f"통과 작품 {n}개를 승인으로 표시했습니다. (직접 플레이해 확인하는 것을 권장합니다)")
    for sid in remove:
        for r in rows:
            if r['학번'] == sid:
                r['승인'] = ''
                out(f'{sid} 비공개로 전환')

    secret = C.load_secret()
    mapping = {r['학번']: r for r in C.read_csv(C.MAPPING)}
    taken = {m['코드'] for m in mapping.values()}
    nums = defaultdict(int)
    for m in mapping.values():
        nums[int(m['반'])] = max(nums[int(m['반'])], int(m['번호']))

    publish, skipped = [], []
    for r in rows:
        if not approved(r):
            continue
        f = C.SUBMISSIONS / f"{r['학번']}.html"
        if not f.exists():
            skipped.append((r['학번'], '원본 파일 없음'))
            continue
        body = f.read_text(encoding='utf-8')
        why = blocked_reason(r, body)
        if why:
            skipped.append((r['학번'], why))
            continue
        sid = r['학번']
        c = C.parse_id(sid)[1]
        m = mapping.get(sid)
        if not m:
            code = C.make_code(secret, sid, taken)
            taken.add(code)
            nums[c] += 1
            m = mapping[sid] = {'학번': sid, '이름': r['이름'], '반': c, '번호': nums[c], '코드': code, '해시': '', '공개': ''}
        publish.append((r, m, body))

    games = defaultdict(list)
    keep = set()
    for r, m, body in publish:
        c = int(m['반'])
        rel = Path('games') / f'{c:02d}' / f"{m['코드']}.html"
        keep.add(rel.as_posix())
        title = re.sub(r'\s+', ' ', (r.get('제목') or '').strip())[:40] or '제목 없음'
        final = harden(body)
        games[c].append({'n': int(m['번호']), 'title': title, 'code': m['코드'], 'size': C.size_of(final)})
        if not dry:
            p = C.SITE / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(final, encoding='utf-8')
        m['해시'] = r['해시']
        m['공개'] = 'Y'

    # 승인에서 빠졌거나 비공개로 바뀐 작품 파일 제거
    removed = 0
    gdir = C.SITE / 'games'
    if gdir.exists():
        for p in gdir.rglob('*.html'):
            if p.relative_to(C.SITE).as_posix() not in keep:
                removed += 1
                if not dry:
                    p.unlink()
    pub_sids = {r['학번'] for r, _, _ in publish}
    for sid, m in mapping.items():
        if sid not in pub_sids:
            m['공개'] = ''

    if not dry:
        (C.SITE / 'data').mkdir(parents=True, exist_ok=True)
        for c in range(1, 17):
            lst = sorted(games.get(c, []), key=lambda g: g['n'])
            (C.SITE / 'data' / f'class{c:02d}.json').write_text(
                json.dumps({'class': c, 'games': lst}, ensure_ascii=False, indent=1), encoding='utf-8')
        idx = {'updated': date.today().isoformat(), 'classes': [{'c': c, 'count': len(games.get(c, []))} for c in range(1, 17)]}
        (C.SITE / 'data' / 'index.json').write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding='utf-8')
        C.write_csv(C.REVIEW, C.REVIEW_FIELDS, rows)
        C.write_csv(C.MAPPING, C.MAPPING_FIELDS, sorted(mapping.values(), key=lambda m: (int(m['반']), int(m['번호']))))

    total = sum(f.stat().st_size for f in C.SITE.rglob('*') if f.is_file()) if C.SITE.exists() else 0
    out(f"\n{'[미리보기] ' if dry else ''}공개 {len(publish)}개, 제거 {removed}개, 건너뜀 {len(skipped)}개")
    for sid, why in skipped[:20]:
        out(f'  건너뜀 {sid}: {why}')
    out(f'사이트 총 용량 {total / 1024 / 1024:.1f}MB / 한도 1GB ({total / C.SITE_BUDGET * 100:.1f}%)')
    if total > C.SPLIT_AT:
        out('⚠ 600MB를 넘었습니다. 저장소를 반 묶음별로 나누는 것을 고려하세요.')
    return {'published': len(publish), 'skipped': skipped, 'removed': removed, 'total': total}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--approve-pass', action='store_true')
    ap.add_argument('--remove', nargs='*', default=[], metavar='학번')
    a = ap.parse_args(argv)
    run(a.dry_run, a.approve_pass, a.remove)


if __name__ == '__main__':
    main()
