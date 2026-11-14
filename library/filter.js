// Filters for the long library lists (Watch, Learn and Listen). Without JavaScript the full list simply shows.
// Watch and Learn: "Topic" then "Area of practice" (only the areas inside the chosen topic), topic buttons, and a browse
// view (featured strip and topic sections, marked .lib-browse) that makes way for the list once anything is chosen.
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
  var topicSelect = document.getElementById('fTopic');
  var areaSelect = document.getElementById('fArea');
  var browse = Array.prototype.slice.call(document.querySelectorAll('.lib-browse'));
  var heading = document.getElementById('libListHeading');
  var headingLabel = document.getElementById('libListLabel');
  var headingCount = document.getElementById('libListCount');
  var moreFilters = document.getElementById('libMoreFilters');
  var PAGE = 24;
  var shown = PAGE;
  var LISTS = { topics: '|', domain: '|', areas: ',', bands: ',' };   // values that hold several items, and what separates them

  // The Area of practice menu depends on the Topic menu: it offers only the areas inside the chosen topic.
  var dependent = areaSelect && areaSelect.querySelector('option[data-domain]');
  var allAreas = dependent ? Array.prototype.slice.call(areaSelect.querySelectorAll('option[data-domain]')).map(function (o) {
    return { value: o.value, label: o.textContent, domain: o.getAttribute('data-domain') };
  }) : [];
  function fillAreas() {
    if (!dependent) return;
    var topic = topicSelect.value;
    var keep = areaSelect.value;
    var mine = allAreas.filter(function (a) { return a.domain === topic; });
    areaSelect.textContent = '';
    areaSelect.appendChild(new Option(topic ? 'All of ' + topic : 'Choose a topic first', ''));
    mine.forEach(function (a) { areaSelect.appendChild(new Option(a.label, a.value)); });
    // Nothing to choose until a topic is picked, or when the topic has a single area on this shelf.
    areaSelect.disabled = mine.length < 2;
    areaSelect.value = mine.some(function (a) { return a.value === keep; }) && mine.length > 1 ? keep : '';
  }

  function matches(card) {
    for (var i = 0; i < selects.length; i++) {
      var want = selects[i].value;
      if (!want) continue;
      var key = selects[i].getAttribute('data-filter');
      var have = card.getAttribute('data-' + key) || '';
      if (LISTS[key]) {
        if (have.split(LISTS[key]).indexOf(want) === -1) return false;
      } else if (have !== want) {
        return false;
      }
    }
    var words = (text.value || '').toLowerCase().trim().split(/\s+/).filter(Boolean);
    var hay = card.getAttribute('data-text') || '';
    return words.every(function (w) { return hay.indexOf(w) !== -1; });
  }

  function active() {
    return selects.some(function (s) { return s.value; }) || !!text.value.trim();
  }

  function apply() {
    var hits = 0;
    cards.forEach(function (card) {
      var ok = matches(card);
      if (ok) hits++;
      card.hidden = !ok || hits > shown;
    });
    var on = active();
    count.textContent = hits === cards.length ? 'Showing all ' + hits + '.' : hits + ' of ' + cards.length + ' match.';
    if (moreWrap) moreWrap.hidden = hits <= shown;
    if (more) more.textContent = 'Show more (' + Math.max(hits - shown, 0) + ' left)';
    if (empty) empty.hidden = hits !== 0;
    browse.forEach(function (b) { b.hidden = on; });
    if (headingLabel) {
      headingLabel.textContent = heading.getAttribute(on ? 'data-some' : 'data-all');
      headingCount.textContent = hits;
    }
    try {
      var params = new URLSearchParams();
      selects.forEach(function (s) { if (s.value) params.set(s.getAttribute('data-filter'), s.value); });
      if (text.value.trim()) params.set('text', text.value.trim());
      var qs = params.toString();
      history.replaceState(null, '', qs ? '?' + qs : location.pathname);
    } catch (e) {}
  }

  function changed() { shown = PAGE; apply(); }

  // Sets the menus from an address such as library-watch.html?domain=Literacy&areas=27.
  function setFrom(params) {
    if (dependent && params.get('areas') && !params.get('domain')) {   // an area on its own brings its topic with it
      var home = allAreas.filter(function (a) { return a.value === params.get('areas'); })[0];
      params = new URLSearchParams(params.toString());
      if (home) params.set('domain', home.domain);
    }
    selects.forEach(function (s) {
      var v = params.get(s.getAttribute('data-filter'));
      s.value = v && Array.prototype.some.call(s.options, function (o) { return o.value === v; }) ? v : '';
      if (s === topicSelect) fillAreas();
    });
    text.value = params.get('text') || '';
    // A choice made in a menu that is folded away should not be hidden from view.
    if (moreFilters && (text.value || Array.prototype.some.call(moreFilters.querySelectorAll('select'), function (s) { return s.value; }))) moreFilters.open = true;
  }

  selects.forEach(function (s) {
    s.addEventListener('change', function () { if (s === topicSelect) fillAreas(); changed(); });
  });
  var timer;
  text.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(changed, 200); });
  form.addEventListener('submit', function (ev) { ev.preventDefault(); });
  form.addEventListener('reset', function () {
    // "Clear filters" under an empty result disappears with the message, so focus goes back to the first menu.
    var lost = empty && empty.contains(document.activeElement);
    setTimeout(function () { fillAreas(); changed(); syncChips(); if (lost && topicSelect) topicSelect.focus(); }, 0);
  });
  if (more) more.addEventListener('click', function () {
    var before = shown;
    shown += PAGE;
    apply();
    // Carry on from the first card that has just appeared, so keyboard focus is not left on a button that has moved or gone.
    var next = cards.filter(function (card) { return !card.hidden; })[before];
    var link = next && next.querySelector('.lib-card-title a');
    if (link) link.focus();
  });

  // Topic buttons set the Topic menu.
  var chipBox = document.getElementById('libChips');
  var chips = chipBox ? Array.prototype.slice.call(chipBox.querySelectorAll('.lib-chip')) : [];
  function syncChips() {
    chips.forEach(function (c) { c.setAttribute('aria-pressed', String(!!topicSelect && c.getAttribute('data-topic') === topicSelect.value)); });
  }
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      var t = c.getAttribute('data-topic');
      topicSelect.value = topicSelect.value === t ? '' : t;
      fillAreas(); changed(); syncChips();
    });
  });
  if (topicSelect) topicSelect.addEventListener('change', syncChips);
  if (chipBox) chipBox.hidden = false;

  // Links in the topic sections ("See all 62 literacy videos", an area of practice) set the menus without a reload.
  // The section that held the link is then hidden, so focus moves to the heading of the list of matches.
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[data-set]') : null;
    if (!a || ev.metaKey || ev.ctrlKey || ev.shiftKey) return;
    ev.preventDefault();
    setFrom(new URL(a.href, location.href).searchParams);
    changed(); syncChips();
    form.scrollIntoView({ block: 'start' });
    if (heading) heading.focus({ preventScroll: true });
  });

  // On a phone the first two menus stay in view and the next two join "More filters".
  var mainRow = form.querySelector('.lib-filter-main');
  var moreRow = moreFilters ? moreFilters.querySelector('.lib-filter-row') : null;
  var extras = Array.prototype.slice.call(form.querySelectorAll('.lib-field-extra'));
  if (mainRow && moreRow && extras.length && window.matchMedia) {
    var narrow = window.matchMedia('(max-width: 640px)');
    var place = function () {
      extras.forEach(function (f, i) {
        if (narrow.matches) moreRow.insertBefore(f, moreRow.children[i] || null); else mainRow.appendChild(f);
      });
    };
    place();
    if (narrow.addEventListener) narrow.addEventListener('change', place); else if (narrow.addListener) narrow.addListener(place);
  }

  // Links such as library-watch.html?areas=27 open with that filter already set.
  setFrom(new URLSearchParams(location.search));

  form.hidden = false;
  var tog = document.getElementById('libFilterToggle');
  if (tog) { tog.hidden = false; tog.addEventListener('click', function () { var open = form.classList.toggle('open'); tog.setAttribute('aria-expanded', String(open)); tog.textContent = open ? 'Hide filters' : 'Filter this list'; }); }
  syncChips();
  apply();
})();
