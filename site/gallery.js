/* 갤러리 공통 스크립트. 작품 제목은 학생이 쓴 글이므로 항상 textContent 로만 넣는다. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var qs = new URLSearchParams(location.search);

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }
  function hue(i, total) { return total > 1 ? Math.round(i / (total - 1) * 270) : 0; } // 빨강 → 보라
  function intParam(name, lo, hi) {
    var v = parseInt(qs.get(name), 10);
    return v >= lo && v <= hi ? v : null;
  }
  function fail(box, title, text) {
    box.textContent = '';
    var m = el('div', 'msg');
    m.appendChild(el('b', null, title));
    m.appendChild(document.createTextNode(text));
    box.appendChild(m);
  }
  var LOAD_ERR = '주소(링크)로 접속했는지 확인하고, 그래도 안 되면 선생님께 알려 주세요.';

  /* ---- 반 선택 ---- */
  function pageIndex() {
    var box = $('#classes');
    getJSON('data/index.json').then(function (d) {
      box.textContent = '';
      d.classes.forEach(function (x, i) {
        var has = x.count > 0;
        var t = el(has ? 'a' : 'div', 'tile' + (has ? '' : ' empty'));
        t.style.setProperty('--h', hue(i, d.classes.length));
        if (has) t.href = 'class.html?c=' + x.c;
        var no = el('span', 'no', String(x.c));
        no.appendChild(el('small', null, '반'));
        t.appendChild(no);
        t.appendChild(el('span', 'meta', has ? '작품 ' + x.count + '개' : '아직 없어요'));
        var li = el('li');
        li.appendChild(t);
        box.appendChild(li);
      });
      if (d.updated) $('#updated').textContent = '목록 갱신: ' + d.updated;
    }).catch(function () { fail(box, '목록을 불러오지 못했어요.', LOAD_ERR); });
  }

  /* ---- 반별 작품 ---- */
  function pageClass() {
    var c = intParam('c', 1, 16), box = $('#games');
    if (!c) { fail(box, '반을 찾을 수 없어요.', ''); return; }
    document.title = c + '반 작품 · 과학 게임 갤러리';
    $('#cname').textContent = c + '반 작품';
    getJSON('data/class' + pad(c) + '.json').then(function (d) {
      var g = d.games || [], tiles = [];
      $('#count').textContent = g.length ? '작품 ' + g.length + '개가 있어요.' : '';
      box.textContent = '';
      if (!g.length) {
        $('#find').hidden = true;
        var m = el('div', 'msg');
        m.appendChild(el('b', null, '아직 올라온 작품이 없어요.'));
        m.appendChild(document.createTextNode('선생님이 점검을 마치면 이곳에 나타나요.'));
        box.replaceWith(m);
        return;
      }
      g.forEach(function (x, i) {
        var li = el('li'), a = el('a', 'tile');
        a.href = 'play.html?c=' + c + '&n=' + x.n;
        a.style.setProperty('--h', hue(i, g.length));
        a.appendChild(el('span', 'no', String(x.n)));
        a.appendChild(el('span', 'ttl', x.title));
        li.appendChild(a);
        box.appendChild(li);
        tiles.push({ li: li, n: String(x.n) });
      });
      $('#num').addEventListener('input', function () {
        var v = this.value.trim();
        tiles.forEach(function (t) { t.li.hidden = v !== '' && t.n.indexOf(v) !== 0; });
      });
    }).catch(function () { fail(box, '작품 목록을 불러오지 못했어요.', LOAD_ERR); });
    $('#back').href = './';
  }

  /* ---- 플레이 ---- */
  function pagePlay() {
    var c = intParam('c', 1, 16), n = intParam('n', 1, 999), stage = $('#stage');
    if (!c || !n) { fail(stage, '작품을 찾을 수 없어요.', ''); return; }
    var back = 'class.html?c=' + c;
    $('#back').href = back;
    $('#back').textContent = '← ' + c + '반 목록';
    getJSON('data/class' + pad(c) + '.json').then(function (d) {
      var g = d.games || [], i = g.findIndex(function (x) { return x.n === n; });
      if (i < 0 || !/^[a-z0-9]{5,10}$/.test(g[i].code)) throw new Error('none');
      var game = g[i];
      document.title = n + '번 ' + game.title + ' · 과학 게임 갤러리';
      $('#pno').textContent = String(n);
      $('#ptitle').textContent = game.title;
      var src = 'games/' + pad(c) + '/' + game.code + '.html';
      var f = el('iframe');
      f.title = game.title;
      // 게임은 갤러리와 분리된 상자(sandbox) 안에서 실행: 다른 작품·앱의 저장 데이터를 읽을 수 없다
      f.setAttribute('sandbox', 'allow-scripts allow-modals allow-pointer-lock');
      f.setAttribute('referrerpolicy', 'no-referrer');
      // 인터넷 요청 차단(CSP)은 publish.py 가 게임 파일 맨 앞에 넣는다 (GitHub Pages 는 서버 헤더를 설정할 수 없으므로)
      f.src = src;
      stage.textContent = '';
      stage.appendChild(f);
      $('#reload').onclick = function () { f.src = src; };
      $('#full').onclick = function () { (f.requestFullscreen || f.webkitRequestFullscreen || function () {}).call(f); };
      function nav(btn, x) {
        if (x) { btn.href = 'play.html?c=' + c + '&n=' + x.n; btn.setAttribute('aria-label', x.n + '번'); }
        else btn.setAttribute('aria-disabled', 'true');
      }
      nav($('#prev'), g[i - 1]);
      nav($('#next'), g[i + 1]);
    }).catch(function () { fail(stage, '작품을 불러오지 못했어요.', '목록으로 돌아가 다시 골라 보세요.'); });
  }

  var page = document.body.getAttribute('data-page');
  if (page === 'index') pageIndex();
  else if (page === 'class') pageClass();
  else if (page === 'play') pagePlay();
})();
