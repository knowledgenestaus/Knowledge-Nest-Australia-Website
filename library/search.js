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

  var LABELS = { watch: 'Watch', listen: 'Listen', read: 'Read', research: 'Research', voice: 'Voices', curriculum: 'Curriculum', learn: 'Learn', tool: 'Assessment tool' };
  var WORDS = { watch: 'video videos classroom footage', listen: 'podcast podcasts episode audio', read: 'article articles blog post reading', research: 'paper papers study report evidence', voice: 'voice person people blog', curriculum: 'curriculum materials lessons program', learn: 'webinar webinars session professional learning video', tool: 'assessment test screener' };
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

  // Short forms and the phrases they stand for find each other.
  var SAME = [
    ['mtss', 'multi tiered'], ['rti', 'response to intervention'], ['cfu', 'checking for understanding'], ['dld', 'developmental language disorder'],
    ['clt', 'cognitive load'], ['sor', 'science of reading'], ['sol', 'science of learning'], ['pd', 'professional learning'], ['pl', 'professional learning'],
    ['di', 'direct instruction'], ['edi', 'explicit direct instruction'], ['mwb', 'mini whiteboard'], ['otr', 'opportunities to respond'],
    ['pa', 'phonemic awareness'], ['iep', 'individual education plan'], ['tlac', 'teach like a champion'], ['vtlm', 'victorian teaching and learning model'],
    ['whiteboards', 'mini whiteboard'], ['decodables', 'decodable'], ['screener', 'screening'], ['timestables', 'times tables']
  ];
  // Little words that say nothing about the topic are left out of a longer search.
  var SMALL = ['a', 'an', 'the', 'of', 'for', 'in', 'on', 'and', 'to', 'with', 'about', 'how', 'what', 'is', 'are', 'my', 'do', 'i', 'can', 'resources', 'resource'];

  // Every form a search word is looked for in: both spellings, singular for plural, and any short form or phrase it stands for.
  function forms(word) {
    var out = spellings(word);
    var add = function (w) { if (w && out.indexOf(w) === -1) out.push(w); };
    if (/ies$/.test(word) && word.length > 4) add(word.slice(0, -3) + 'y');
    if (/(ch|sh|ss|x)es$/.test(word)) add(word.slice(0, -2));
    if (/[^s]s$/.test(word) && word.length > 3) add(word.slice(0, -1));
    SAME.forEach(function (pair) { if (pair[0] === word) add(pair[1]); });
    return out;
  }

  // Text is compared without hyphens, apostrophes or other punctuation, so "check-in", "check in" and "checkin" all meet.
  function plain(text) {
    var t = (text || '').toLowerCase().replace(/[\u2018\u2019']/g, '');
    return t.replace(/[^a-z0-9]+/g, ' ') + ' ' + t.replace(/[-\u2010-\u2015]/g, '').replace(/[^a-z0-9]+/g, ' ');
  }

  // How many single-letter changes turn one word into another (used to offer "Did you mean").
  function distance(a, b) {
    if (Math.abs(a.length - b.length) > 2) return 9;
    var prev = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i];
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev[j - 1]);   // swapped letters: one slip
      }
      prev = cur;
    }
    return prev[b.length];
  }
  var vocab = null;

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch('library-search.json')
        .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)); })
        .then(function (data) {
          index = data.map(function (x) {
            // x.s is the card's topic line and summary: searched, but not shown in the results.
            // x.who: the creator plus any "with ..." guest or presenter, shown in bold and used to rank a search for a person.
            x.guests = (x.m || []).filter(function (m) { return /^with\s/i.test(m); });
            x.who = [x.b].concat(x.guests).filter(Boolean).join(', ');
            x.hay = ' ' + plain([x.t, x.b, (x.m || []).join(' '), (x.a || []).join(' '), LABELS[x.y] || '', WORDS[x.y] || '', x.k || '', (x.g || []).join(' '), x.d, x.s || ''].join(' '));
            return x;
          });
          // The words in titles and names, for "Did you mean".
          vocab = {};
          index.forEach(function (x) { plain(x.t + ' ' + x.who).split(' ').forEach(function (w) { if (w.length > 3) vocab[w] = (vocab[w] || 0) + 1; }); });
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
    // Who is responsible for it comes first, in bold, then the other details.
    var rest = (x.m || []).filter(function (m) { return x.guests.indexOf(m) === -1; });
    if (x.who || rest.length) {
      var by = el('p', 'lib-by');
      if (x.who) {
        var who = el('span', 'lib-who');
        if (x.b) { who.appendChild(el('span', 'lib-who-by', 'By')); who.appendChild(document.createTextNode(' ' + x.who)); }
        else { who.textContent = x.who.charAt(0).toUpperCase() + x.who.slice(1); }
        by.appendChild(who);
      }
      if (rest.length) by.appendChild(document.createTextNode((x.who ? ' · ' : '') + rest.join(' · ')));
      a.appendChild(by);
    }
    if (x.p) a.appendChild(el('p', 'lib-summary', x.p));
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
    var words = q.toLowerCase().replace(/[\u2018\u2019']/g, '').split(/[^a-z0-9]+/).filter(Boolean);
    if (words.length > 1) { var kept = words.filter(function (w) { return SMALL.indexOf(w) === -1; }); if (kept.length) words = kept; }
    setAddress(q);
    if (!q) { if (focus) { message('', 'Type a topic, a practice or a name.'); heading.textContent = 'Search the library'; } else { section.hidden = true; } return; }
    if (q.length < 2 || !words.length) { message(q, 'Type at least two letters.'); return; }
    load().then(function (data) {
      // Match each word at the start of a word, so "hinge" does not match inside another word.
      var tests = words.map(function (w) { return new RegExp(' (' + forms(w).join('|') + ')'); });
      var find = function (res) { return data.filter(function (x) { return res.every(function (re) { return re.test(x.hay); }); }); };
      var hits = find(tests);
      // Nothing has every word: show what matches all but one, and say so.
      var close = false;
      if (!hits.length && words.length > 2) {
        var seen = {};
        tests.forEach(function (skip) { find(tests.filter(function (re) { return re !== skip; })).forEach(function (x) { if (!seen[x.u]) { seen[x.u] = 1; hits.push(x); } }); });
        close = hits.length > 0;
      }
      // Still nothing: look for a slip of the fingers and offer the nearest word from the library's titles and names.
      var meant = '';
      if (!hits.length) {
        var fixed = words.map(function (w, i) {
          if (tests[i].test(' ' + Object.keys(vocab).join(' '))) return w;
          var best = w, bestD = w.length > 5 ? 3 : 2, bestN = 0;
          Object.keys(vocab).forEach(function (v) { var dd = distance(w, v); if (dd < bestD || (dd === bestD && dd < 3 && vocab[v] > bestN && best !== w)) { best = v; bestD = dd; bestN = vocab[v]; } });
          return best;
        });
        if (fixed.join(' ') !== words.join(' ') && find(fixed.map(function (w) { return new RegExp(' (' + forms(w).join('|') + ')'); })).length) meant = fixed.join(' ');
        // A name is offered the way it is written in the library.
        var opts = document.getElementById('libPeople');
        if (meant && opts) Array.prototype.forEach.call(opts.options, function (o) { if (o.value.toLowerCase() === meant) meant = o.value; });
      }
      // Best matches first: the whole phrase in the title or in who made it (so a person's name finds their work first),
      // then every word in the title, then the rest.
      // Inside each group the entries keep the library's own order.
      // For a person: their own card on the Voices shelf, then what they made, then where they appear as a guest.
      var phrase = ' ' + words.join(' ');
      var rank = function (x) {
        var t = ' ' + plain(x.t);
        if (x.y === 'voice' && t.indexOf(phrase) !== -1) return 0;
        if ((' ' + plain(x.b)).indexOf(phrase) !== -1) return 1;
        if (t.indexOf(phrase) !== -1) return 2;
        if ((' ' + plain(x.who)).indexOf(phrase) !== -1) return 2;
        return tests.every(function (re) { return re.test(t); }) ? 3 : 4;
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
        note.textContent = (close ? 'Nothing has every word, so these match most of them. ' : '') + hits.length + (hits.length === 1 ? ' entry' : ' entries') + (shown < hits.length ? ', showing the first ' + shown : '') + '.';
        // Keyboard and screen reader users carry on from the first new result.
        if (moveFocus && first) first.querySelector('.lib-card-title a').focus();
      }
      more.addEventListener('click', function () { showMore(true); });

      // A search for someone in the library's list of people says so in the heading.
      var people = document.getElementById('libPeople');
      var person = people && Array.prototype.filter.call(people.options, function (o) { return o.value.toLowerCase() === q.toLowerCase(); })[0];
      heading.textContent = person ? 'By or featuring ' + person.value : 'Search results for "' + q + '"';
      if (!hits.length) {
        moreWrap.hidden = true;
        note.textContent = '';
        if (meant) {
          note.appendChild(document.createTextNode('Nothing found for that spelling. Did you mean '));
          var again = el('button', 'lib-meant', meant);
          again.type = 'button';
          again.addEventListener('click', function () { input.value = meant; run(meant, true); });
          note.appendChild(again);
          note.appendChild(document.createTextNode('? '));
        }
        note.appendChild(document.createTextNode((meant ? 'Or try' : 'Nothing found yet. Try') + ' a broader word, or browse by type or area below. If something is missing, '));
        var mail = el('a', 'lib-textlink', 'email a suggestion');
        mail.href = SUGGEST;
        note.appendChild(mail);
        note.appendChild(document.createTextNode('.'));
      } else {
        showMore(false);
      }
      section.hidden = false;
      if (focus) { heading.focus({ preventScroll: true }); reveal(focus === 'load'); }
    }).catch(function () {
      note.textContent = 'Search could not load. Please browse by type or area below.';
      list.textContent = '';
      section.hidden = false;
    });
  }

  // Bring the results into view below the sticky menu. The results section has a scroll margin
  // for the menu. A search that arrives in the address (from the home page or the 404 page) runs
  // before images and fonts finish loading, which pushes the results down, so it scrolls again
  // once the page has loaded, unless the visitor has already scrolled themselves.
  function reveal(onLoad) {
    var smooth = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    section.scrollIntoView({ behavior: smooth && !onLoad ? 'smooth' : 'auto', block: 'start' });
    if (!onLoad) return;
    var moved = false;
    var mark = function () { moved = true; };
    ['wheel', 'touchstart', 'keydown'].forEach(function (t) { window.addEventListener(t, mark, { once: true, passive: true }); });
    var again = function () { if (!moved) section.scrollIntoView({ behavior: 'auto', block: 'start' }); };
    if (document.readyState === 'complete') setTimeout(again, 0);
    else window.addEventListener('load', again, { once: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(again);
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
  if (initial) { input.value = initial; run(initial, 'load'); }
})();
