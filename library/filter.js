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
      if (key === 'areas' || key === 'bands') {
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
  if (more) more.addEventListener('click', function () { shown += PAGE; apply(); });

  // Links such as library-watch.html?areas=7 open with that filter already set.
  var initial = new URLSearchParams(location.search);
  selects.forEach(function (s) {
    var v = initial.get(s.getAttribute('data-filter'));
    if (v && Array.prototype.some.call(s.options, function (o) { return o.value === v; })) s.value = v;
  });
  if (initial.get('text')) text.value = initial.get('text');

  form.hidden = false;
  apply();
})();
