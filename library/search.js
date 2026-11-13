// Library search: filters the published entries in the visitor's browser. Nothing is sent anywhere.
(function () {
  var form = document.getElementById('libSearch');
  var input = document.getElementById('q');
  var section = document.getElementById('results');
  var list = document.getElementById('resultsList');
  var note = document.getElementById('resultsNote');
  var heading = document.getElementById('resultsHeading');
  var clear = document.getElementById('clearSearch');
  if (!form || !input || !section) return;

  var LABELS = { watch: 'Watch', listen: 'Listen', read: 'Read', research: 'Research', voice: 'Voices', curriculum: 'Curriculum' };
  var MAX = 60;
  var index = null;
  var loading = null;

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch('library-search.json')
        .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)); })
        .then(function (data) {
          index = data.map(function (x) {
            x.hay = [x.t, x.b, (x.m || []).join(' '), (x.a || []).join(' '), LABELS[x.y] || '', x.d].join(' ').toLowerCase();
            return x;
          });
          return index;
        });
    }
    return loading;
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  function card(x) {
    var a = el('article', 'lib-card');
    a.appendChild(el('span', 'lib-type lib-type-' + x.y, LABELS[x.y] || ''));
    var h = el('h3', 'lib-card-title');
    var link = el('a', '', x.t);
    link.href = x.u; link.target = '_blank'; link.rel = 'noopener';
    link.appendChild(el('span', 'sr-only', ' (opens in a new tab)'));
    h.appendChild(link); a.appendChild(h);
    var line = [x.b].concat(x.m || []).filter(Boolean).join(' · ');
    if (line) a.appendChild(el('p', 'lib-by', line));
    var foot = el('p', 'lib-card-foot');
    (x.g || []).forEach(function (g) { foot.appendChild(el('span', 'lib-tag' + (/^free/i.test(g) ? ' lib-tag-free' : ''), g)); });
    foot.appendChild(el('span', 'lib-source', 'Opens at ' + x.d));
    a.appendChild(foot);
    return a;
  }

  function run(q, focus) {
    q = (q || '').trim();
    if (q.length < 2) { section.hidden = true; return; }
    var words = q.toLowerCase().split(/\s+/);
    load().then(function (data) {
      // Match each word at the start of a word, so "hinge" does not match inside another word.
      var tests = words.map(function (w) { return new RegExp('(^|[^a-z0-9])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')); });
      var hits = data.filter(function (x) { return tests.every(function (re) { return re.test(x.hay); }); });
      list.textContent = '';
      var grid = el('div', 'lib-grid');
      hits.slice(0, MAX).forEach(function (x) { grid.appendChild(card(x)); });
      list.appendChild(grid);
      heading.textContent = 'Search results for "' + q + '"';
      if (!hits.length) {
        note.textContent = 'Nothing found yet. Try a broader word, or browse by type or area below. If something is missing, email a suggestion.';
      } else {
        note.textContent = hits.length + (hits.length === 1 ? ' entry' : ' entries') + (hits.length > MAX ? ', showing the first ' + MAX : '') + '.';
      }
      section.hidden = false;
      if (focus) { heading.focus(); section.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }).catch(function () {
      note.textContent = 'Search could not load. Please browse by type or area below.';
      list.textContent = '';
      section.hidden = false;
    });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var q = input.value;
    try { history.replaceState(null, '', q.trim() ? '?q=' + encodeURIComponent(q.trim()) : location.pathname); } catch (e) {}
    run(q, true);
  });
  var timer;
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { run(input.value, false); }, 200); });
  clear.addEventListener('click', function () {
    input.value = ''; section.hidden = true;
    try { history.replaceState(null, '', location.pathname); } catch (e) {}
    input.focus();
  });

  var initial = new URLSearchParams(location.search).get('q');
  if (initial) { input.value = initial; run(initial, false); }
})();
