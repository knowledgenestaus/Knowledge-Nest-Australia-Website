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

  var LABELS = { watch: 'Watch', listen: 'Listen', read: 'Read', research: 'Research', voice: 'Voices', curriculum: 'Curriculum', learn: 'Learn' };
  var SUGGEST = 'mailto:jo@knowledgenest.com.au?subject=Library%20suggestion';
  var PAGE = 60;   // results shown at a time; "Show more" brings the next lot
  var index = null;
  var loading = null;

  // American and Australian spellings find each other: "behavior" also looks for "behaviour", and the reverse.
  // Each pair is the start of a word, so "organiz" covers organize, organizing and organization.
  var SPELLINGS = [
    ['behavior', 'behaviour'], ['color', 'colour'], ['favor', 'favour'], ['honor', 'honour'], ['labor', 'labour'],
    ['center', 'centre'], ['math', 'maths'], ['modeling', 'modelling'], ['modeled', 'modelled'],
    ['practice', 'practise'], ['practicing', 'practising'], ['judgment', 'judgement'], ['learned', 'learnt'],
    ['program', 'programme'], ['fulfill', 'fulfil'], ['skillful', 'skilful'], ['enrollment', 'enrolment'],
    ['organiz', 'organis'], ['recogniz', 'recognis'], ['summariz', 'summaris'], ['prioritiz', 'prioritis'],
    ['emphasiz', 'emphasis'], ['memoriz', 'memoris'], ['generaliz', 'generalis'], ['specializ', 'specialis'],
    ['visualiz', 'visualis'], ['personaliz', 'personalis'], ['analyz', 'analys'], ['dialog', 'dialogue'], ['catalog', 'catalogue']
  ];

  function spellings(word) {
    var out = [word];
    SPELLINGS.forEach(function (pair) {
      [[pair[0], pair[1]], [pair[1], pair[0]]].forEach(function (p) {
        if (word.indexOf(p[0]) === 0) {
          var other = p[1] + word.slice(p[0].length);
          if (out.indexOf(other) === -1) out.push(other);
        }
      });
    });
    return out;
  }

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch('library-search.json')
        .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)); })
        .then(function (data) {
          index = data.map(function (x) {
            // x.s is the card's topic line and summary: searched, but not shown in the results.
            x.hay = [x.t, x.b, (x.m || []).join(' '), (x.a || []).join(' '), LABELS[x.y] || '', x.k || '', x.d, x.s || ''].join(' ').toLowerCase();
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
    // Videos also say what kind they are (x.k): Lesson footage, Webinar, Explainer and so on.
    if (x.k) { a.firstChild.textContent += ': ' + x.k; }
    var h = el('h3', 'lib-card-title');
    // House style: the part of a title before its first colon is the bold lead-in (see .lead-in in styles.css).
    var link = el('a', '');
    var parts = /^([\s\S]*?[^\s:]:)(\s+\S[\s\S]*)$/.exec(x.t);
    if (parts) {
      link.appendChild(el('span', 'lead-in', parts[1]));
      // A lone "A", "An" or "The" stays with the word after it, as on the library pages.
      link.appendChild(el('span', 'lead-rest', parts[2].replace(/^(\s+(?:A|An|The))\s/, '$1 ')));
    }
    else { link.textContent = x.t; }
    link.href = x.u; link.target = '_blank'; link.rel = 'noopener';
    link.appendChild(el('span', 'sr-only', ' (opens in a new tab)'));
    h.appendChild(link); a.appendChild(h);
    var line = [x.b].concat(x.m || []).filter(Boolean).join(' · ');
    if (line) a.appendChild(el('p', 'lib-by', line));
    var foot = el('p', 'lib-card-foot');
    (x.g || []).forEach(function (g) { foot.appendChild(el('span', 'lib-tag' + (/^free/i.test(g) && g !== 'Free account needed' ? ' lib-tag-free' : ''), g)); });
    foot.appendChild(el('span', 'lib-source', 'Opens at ' + x.d));
    a.appendChild(foot);
    return a;
  }

  function setAddress(q) {
    try { history.replaceState(null, '', q ? '?q=' + encodeURIComponent(q) : location.pathname); } catch (e) {}
  }

  function message(q, text) {
    list.textContent = '';
    heading.textContent = 'Search results for "' + q + '"';
    note.textContent = text;
    section.hidden = false;
  }

  function run(q, focus) {
    q = (q || '').trim();
    // Words are matched without the punctuation around them, so "fluency." and "Ochre: maths" still find things.
    var words = q.toLowerCase().split(/\s+/).map(function (w) { return w.replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, ''); }).filter(Boolean);
    setAddress(q);
    if (!q) { section.hidden = true; return; }
    if (q.length < 2 || !words.length) { message(q, 'Type at least two letters.'); return; }
    load().then(function (data) {
      // Match each word at the start of a word, so "hinge" does not match inside another word.
      var tests = words.map(function (w) {
        var forms = spellings(w).map(function (f) { return f.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
        return new RegExp('(^|[^a-z0-9])(' + forms.join('|') + ')');
      });
      var hits = data.filter(function (x) { return tests.every(function (re) { return re.test(x.hay); }); });
      // Best matches first: the whole phrase in the title, then every word in the title, then the rest.
      // Inside each group the entries keep the library's own order.
      var phrase = ' ' + words.join(' ');
      var rank = function (x) {
        var t = x.t.toLowerCase();
        if ((' ' + t.replace(/[^a-z0-9]+/g, ' ')).indexOf(phrase) !== -1) return 0;
        return tests.every(function (re) { return re.test(t); }) ? 1 : 2;
      };
      hits = hits.map(function (x, i) { return [rank(x), i, x]; })
        .sort(function (p, q) { return p[0] - q[0] || p[1] - q[1]; })
        .map(function (r) { return r[2]; });
      var shown = 0;
      list.textContent = '';
      var grid = el('div', 'lib-grid');
      list.appendChild(grid);
      var moreWrap = el('p', 'lib-more');
      var more = el('button', 'btn btn-primary');
      more.type = 'button';
      moreWrap.appendChild(more);
      list.appendChild(moreWrap);

      function showMore(moveFocus) {
        var first = null;
        hits.slice(shown, shown + PAGE).forEach(function (x) { var c = grid.appendChild(card(x)); if (!first) first = c; });
        shown = Math.min(shown + PAGE, hits.length);
        moreWrap.hidden = shown >= hits.length;
        more.textContent = 'Show more (' + (hits.length - shown) + ' left)';
        note.textContent = hits.length + (hits.length === 1 ? ' entry' : ' entries') + (shown < hits.length ? ', showing the first ' + shown : '') + '.';
        // Keyboard and screen reader users carry on from the first new result.
        if (moveFocus && first) first.querySelector('.lib-card-title a').focus();
      }
      more.addEventListener('click', function () { showMore(true); });

      heading.textContent = 'Search results for "' + q + '"';
      if (!hits.length) {
        moreWrap.hidden = true;
        note.textContent = 'Nothing found yet. Try a broader word, or browse by type or area below. If something is missing, ';
        var mail = el('a', '', 'email a suggestion');
        mail.href = SUGGEST;
        note.appendChild(mail);
        note.appendChild(document.createTextNode('.'));
      } else {
        showMore(false);
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
    run(input.value, true);
  });
  var timer;
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { run(input.value, false); }, 200); });
  clear.addEventListener('click', function () {
    input.value = ''; section.hidden = true;
    setAddress('');
    input.focus();
  });

  var initial = new URLSearchParams(location.search).get('q');
  if (initial) { input.value = initial; run(initial, true); }
})();
