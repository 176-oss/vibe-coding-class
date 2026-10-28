"""공통 함수: 경로, 학번 해석, 제출 표식, 점검 규칙, CSV 입출력 (Python 3.9+, 표준 라이브러리만 사용)"""
import csv
import hashlib
import hmac
import html as htmllib
import os
import re
import secrets
from pathlib import Path

ROOT = Path(os.environ.get('VIBE_ROOT') or Path(__file__).resolve().parent.parent)
PRIVATE = ROOT / 'private'          # 저장소에 올라가지 않는 교사용 폴더
SUBMISSIONS = PRIVATE / 'submissions'
REVIEW = PRIVATE / 'review.csv'
MAPPING = PRIVATE / 'mapping.csv'
SECRET = PRIVATE / 'secret.txt'
BANNED = PRIVATE / 'banned_words.txt'
ROSTER = PRIVATE / 'roster.csv'
SITE = ROOT / 'site'

SIZE_WARN = 500 * 1024          # 경고 크기
SIZE_MAX = 1024 * 1024          # 상한 크기
SIZE_EXCEPT = 2 * 1024 * 1024   # 교사 예외 승인 최대 크기
SITE_BUDGET = 1024 ** 3         # GitHub Pages 사이트 한도 1GB
SPLIT_AT = 600 * 1024 ** 2      # 이 용량을 넘으면 저장소 분리 권장

REVIEW_FIELDS = ['학번', '이름', '반', '번호', '상태', '사유', '실패코드', '제목', '크기', '승인', '크기예외', '해시', '파일']
MAPPING_FIELDS = ['학번', '이름', '반', '번호', '코드', '해시', '공개']
YES = {'y', 'yes', 'o', 'ㅇ', '1', 'true', '승인', '허용'}

ID_RE = re.compile(r'^([1-3])(0[1-9]|1[0-6])(0[1-9]|[1-3]\d|40)$')
MARK_RE = re.compile(r'^﻿?\s*<!--\s*vibe-submit:([^|>]*)\|([^>]*?)\s*-->\s*', re.S)
URL_RE = re.compile(r'https?://(?!www\.w3\.org/)[^\s"\'<>)]+', re.I)
REL_RE = re.compile(r'(?:src|href)\s*=\s*["\']//[^"\']+', re.I)
EXTFILE_RES = [re.compile(r'<script[^>]*\ssrc\s*=', re.I), re.compile(r'<link[^>]*\shref\s*=', re.I), re.compile(r'@import', re.I)]
API_RE = re.compile(r'\b(fetch|XMLHttpRequest|WebSocket|sendBeacon|window\.open|document\.cookie)\b')
EVAL_RE = re.compile(r'\beval\s*\(|new\s+Function\s*\(')
STORE_RE = re.compile(r'\b(localStorage|sessionStorage|indexedDB)\b')
# 글자 수에 상한을 두어, 아주 긴 문자열(base64 이미지 등)에서도 검사 시간이 폭증하지 않게 한다
EMAIL_RE = re.compile(r'[\w.+-]{1,64}@[\w-]{1,63}\.[\w.-]{2,63}')
PHONE_RE = re.compile(r'01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}')
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)


def parse_id(sid):
    """학번 5자리 → (학년, 반, 번호). 형식이 틀리면 None."""
    m = ID_RE.match((sid or '').strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def split_marker(text):
    """파일 맨 앞의 제출 표식을 읽고 제거한다. → (학번, 이름, 표식 없는 본문)"""
    m = MARK_RE.match(text)
    if m:
        return m[1].strip(), m[2].strip(), text[m.end():]
    return None, None, text


def get_title(html):
    m = TITLE_RE.search(html)
    return re.sub(r'\s+', ' ', htmllib.unescape(m[1])).strip() if m else ''


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def size_of(text):
    return len(text.encode('utf-8'))


def load_banned():
    if not BANNED.exists():
        return []
    out = []
    for line in BANNED.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out


def check_html(html, sid, name, banned=(), roster_re=None):
    """점검 결과 목록 [(수준, 코드, 설명)]. 수준: fail(공개 불가) / warn(교사 확인)"""
    out = []
    size = size_of(html)
    if size > SIZE_EXCEPT:
        out.append(('fail', 'SIZE_HARD', '크기 2MB 초과 (예외도 불가)'))
    elif size > SIZE_MAX:
        out.append(('fail', 'SIZE', '크기 1MB 초과 (교사 예외 승인 가능)'))
    elif size >= SIZE_WARN:
        out.append(('warn', 'SIZE_WARN', '크기 500KB 이상'))
    if not re.search(r'<html[\s>]', html, re.I) or not re.search(r'</html>', html, re.I):
        out.append(('fail', 'INCOMPLETE', 'HTML 전체가 아님'))
    urls = sorted(set(URL_RE.findall(html))) + REL_RE.findall(html)
    if urls:
        out.append(('fail', 'EXT_URL', '외부 주소: ' + ', '.join(urls[:3])))
    if any(r.search(html) for r in EXTFILE_RES):
        out.append(('fail', 'EXT_FILE', '외부 파일(script/link/@import) 사용'))
    api = sorted(set(API_RE.findall(html)))
    if api:
        out.append(('fail', 'API', '네트워크·위험 코드: ' + ', '.join(api)))
    if EVAL_RE.search(html):
        out.append(('warn', 'EVAL', 'eval/new Function 사용'))
    if STORE_RE.search(html):
        out.append(('warn', 'STORAGE', '저장 기능(localStorage 등) 사용: 갤러리에서는 동작하지 않을 수 있음'))
    if EMAIL_RE.search(html) or PHONE_RE.search(html):
        out.append(('fail', 'PII', '이메일 또는 전화번호 형태가 있음'))
    if sid and sid in html or (name and len(name) >= 2 and name in html):
        out.append(('fail', 'NAME_IN_CODE', '작성자의 학번 또는 이름이 코드에 있음'))
    low = html.lower()
    hits = [w for w in banned if w.lower() in low]
    if hits:
        out.append(('fail', 'BANNED', '금칙어: ' + ', '.join(hits[:3])))
    if roster_re is not None:
        found = sorted(set(roster_re.findall(html)))
        if found:
            out.append(('warn', 'ROSTER_NAME', '다른 학생 이름처럼 보이는 글자: ' + ', '.join(found[:3])))
    title = get_title(html)
    if not title:
        out.append(('warn', 'TITLE', '<title>이 없거나 비어 있음'))
    return out


def status_of(results):
    if any(r[0] == 'fail' for r in results):
        return '실패'
    return '경고' if results else '통과'


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def load_secret():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if not SECRET.exists():
        SECRET.write_text(secrets.token_hex(16), encoding='utf-8')
    return SECRET.read_text(encoding='utf-8').strip()


ALPHA = '23456789abcdefghjkmnpqrstuvwxyz'


def make_code(secret, sid, taken, length=5):
    """학번 + 비밀 값으로 공개 코드를 만든다 (같은 학번이면 항상 같은 코드)."""
    n = int.from_bytes(hmac.new(secret.encode(), sid.encode(), hashlib.sha256).digest(), 'big')
    while True:
        x, s = n, ''
        for _ in range(length):
            x, r = divmod(x, len(ALPHA))
            s += ALPHA[r]
        if s not in taken:
            return s
        length += 1


def load_roster():
    """private/roster.csv (학번,이름) → {학번: 이름}"""
    out = {}
    for r in read_csv(ROSTER):
        keys = list(r.keys())
        sid = (r.get('학번') or r[keys[0]] or '').strip()
        name = (r.get('이름') or (r[keys[1]] if len(keys) > 1 else '') or '').strip()
        if parse_id(sid):
            out[sid] = name
    return out
