// Filters for long library lists (Watch and Listen). Without JavaScript the full list simply shows.
(function () {
  var form = document.getElementById('libFilters');
  var list = document.getElementById('libList');
  if (!form || !list) return;
  var cards = Array.prototype.slice.call(list.querySelectorAll('.lib-card'));
  var selects = Array.prototype.slice.call(form.querySelectorAll('select[data-filter]'));
  var text = document.getElementById('fText');
  var count = document.getElementById('fCount');
  var more = document.getElementById('libMore');
  var moreWrap = more ? more.parentNode : null;
  var empty = document.getElementById('libEmpty');
  var PAGE = 24;
  var shown = PAGE;

  function matches(card) {
    for (var i = 0; i < selects.length; i++) {
      var want = selects[i].value;
      if (!want) continue;
      var key = selects[i].getAttribute('data-filter');
      var have = card.getAttribute('data-' + key) || '';
      if (key === 'topics') {
        if (have.split('|').indexOf(want) === -1) return false;
      } else if (key === 'areas' || key === 'bands') {
        if (have.split(',').indexOf(want) === -1) return false;
      } else if (have !== want) {
        return false;
      }
    }
    var words = (text.value || '').toLowerCase().trim().split(/\s+/).filter(Boolean);
    var hay = card.getAttribute('data-text') || '';
    return words.every(function (w) { return hay.indexOf(w) !== -1; });
  }

  function apply() {
    var hits = 0;
    cards.forEach(function (card) {
      var ok = matches(card);
      if (ok) hits++;
      card.hidden = !ok || hits > shown;
    });
    count.textContent = hits === cards.length ? 'Showing all ' + hits + '.' : hits + ' of ' + cards.length + ' match.';
    if (moreWrap) moreWrap.hidden = hits <= shown;
    if (more) more.textContent = 'Show more (' + Math.max(hits - shown, 0) + ' left)';
    if (empty) empty.hidden = hits !== 0;
    try {
      var params = new URLSearchParams();
      selects.forEach(function (s) { if (s.value) params.set(s.getAttribute('data-filter'), s.value); });
      if (text.value.trim()) params.set('text', text.value.trim());
      var qs = params.toString();
      history.replaceState(null, '', qs ? '?' + qs : location.pathname);
    } catch (e) {}
  }

  function changed() { shown = PAGE; apply(); }
  selects.forEach(function (s) { s.addEventListener('change', changed); });
  var timer;
  text.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(changed, 200); });
  form.addEventListener('submit', function (ev) { ev.preventDefault(); });
  form.addEventListener('reset', function () { setTimeout(changed, 0); });
  if (more) more.addEventListener('click', function () {
    var before = shown;
    shown += PAGE;
    apply();
    // Carry on from the first card that has just appeared, so keyboard focus is not left on a button that has moved or gone.
    var next = cards.filter(function (card) { return !card.hidden; })[before];
    var link = next && next.querySelector('.lib-card-title a');
    if (link) link.focus();
  });

  // Links such as library-watch.html?areas=7 open with that filter already set.
  var initial = new URLSearchParams(location.search);
  selects.forEach(function (s) {
    var v = initial.get(s.getAttribute('data-filter'));
    if (v && Array.prototype.some.call(s.options, function (o) { return o.value === v; })) s.value = v;
  });
  if (initial.get('text')) text.value = initial.get('text');

  // Topic buttons set the Topic filter.
  var chipBox = document.getElementById('libChips');
  var topicSelect = document.getElementById('fTopic');
  var chips = chipBox ? Array.prototype.slice.call(chipBox.querySelectorAll('.lib-chip')) : [];
  function syncChips() {
    chips.forEach(function (c) { c.setAttribute('aria-pressed', String(topicSelect && c.getAttribute('data-topic') === topicSelect.value)); });
  }
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      var t = c.getAttribute('data-topic');
      topicSelect.value = topicSelect.value === t ? '' : t;
      changed(); syncChips();
    });
  });
  if (topicSelect) topicSelect.addEventListener('change', syncChips);
  form.addEventListener('reset', function () { setTimeout(syncChips, 0); });
  if (chipBox) chipBox.hidden = false;

  form.hidden = false;
  var tog = document.getElementById('libFilterToggle');
  if (tog) { tog.hidden = false; tog.addEventListener('click', function () { var open = form.classList.toggle('open'); tog.setAttribute('aria-expanded', String(open)); tog.textContent = open ? 'Hide filters' : 'Filter this list'; }); }
  syncChips();
  apply();
})();
