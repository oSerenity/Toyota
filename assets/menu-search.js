// menu-search.js — adds an "All manuals" link and a search box to a manual's menu.
//
// Shared by every manual's menu page. It indexes the menu's document links
// (links to .pdf files), labels each one with the menu sections it sits in, and
// while a search is active shows a flat list of matches instead of the tree.
// Result links are copies of the originals, so they open in the same frame.
//
// Usage: <script src="…/assets/menu-search.js" data-home="…/index.html" defer></script>
// Put <div data-menu-search></div> where the box should go (default: top of body).
(function () {
  'use strict';

  var script = document.currentScript;
  var homeHref = script && script.getAttribute('data-home');
  var MAX_RESULTS = 200;

  var css =
    '.ms-box{position:sticky;top:0;z-index:5;margin:0 0 8px;padding:8px 6px;border-bottom:1px solid rgba(0,0,0,.12)}' +
    '.ms-home{display:inline-block;margin-bottom:6px;font-size:12px;color:#cf0000!important;text-decoration:none}' +
    '.ms-home:hover{text-decoration:underline}' +
    '.ms-field{display:flex;gap:4px}' +
    '.ms-input{flex:1;min-width:0;padding:6px 8px;border:1px solid #9aa5ab;border-radius:6px;font:inherit;font-size:13px;background:#fff;color:#000}' +
    '.ms-input:focus{outline:2px solid #cf0000;outline-offset:0;border-color:transparent}' +
    '.ms-status{margin:6px 2px 0;font-size:12px;color:#3d4a52}' +
    '.ms-results{list-style:none;margin:0;padding:0}' +
    '.ms-results li{padding:5px 2px;border-bottom:1px solid rgba(0,0,0,.08)}' +
    '.ms-results a{font-size:13px}' +
    '.ms-crumb{display:block;font-size:11px;color:#5b6670}' +
    'body.ms-searching>*:not(.ms-box):not(script):not(style){display:none!important}' +
    'a[aria-current="page"]{font-weight:bold}';

  function textOf(el) {
    return (el ? el.textContent : '').replace(/\s+/g, ' ').trim();
  }

  // Label of a collapsible menu section: a <details> summary, or the trigger
  // link of an old-style showmenu('id') section.
  function sectionLabel(el) {
    if (el.tagName === 'DETAILS') {
      return textOf(el.querySelector(':scope > summary'));
    }
    if (el.tagName === 'DIV' && el.id) {
      var trigger = document.querySelector('[onmousedown*="\'' + el.id + '\'"]');
      return textOf(trigger);
    }
    return '';
  }

  function breadcrumb(link) {
    var parts = [];
    for (var el = link.parentElement; el && el !== document.body; el = el.parentElement) {
      var label = sectionLabel(el);
      if (label) parts.unshift(label);
    }
    return parts.join(' › ');
  }

  function init() {
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    var box = document.querySelector('[data-menu-search]');
    if (!box) {
      box = document.createElement('div');
      document.body.insertBefore(box, document.body.firstChild);
    }
    box.className = 'ms-box';
    // Match the page background so the sticky bar hides the list scrolling under it.
    var bg = getComputedStyle(document.body).backgroundColor;
    box.style.backgroundColor = (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') ? '#fff' : bg;
    box.setAttribute('role', 'search');

    if (homeHref) {
      var home = document.createElement('a');
      home.className = 'ms-home';
      home.href = homeHref;
      home.target = '_top';
      home.textContent = '← All manuals';
      box.appendChild(home);
    }

    var field = document.createElement('div');
    field.className = 'ms-field';
    var input = document.createElement('input');
    input.type = 'search';
    input.className = 'ms-input';
    input.placeholder = 'Search this manual…';
    input.setAttribute('aria-label', 'Search this manual');
    input.autocomplete = 'off';
    field.appendChild(input);
    box.appendChild(field);

    var status = document.createElement('p');
    status.className = 'ms-status';
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;
    box.appendChild(status);

    var results = document.createElement('ul');
    results.className = 'ms-results';
    box.appendChild(results);

    // Index every document link that has a visible label.
    var index = [];
    Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (a) {
      var href = a.getAttribute('href') || '';
      var label = textOf(a);
      if (!label || !/\.pdf(?:[?#]|$)/i.test(href) || box.contains(a)) return;
      var crumb = breadcrumb(a);
      index.push({ link: a, label: label, crumb: crumb, haystack: (label + ' ' + crumb).toLowerCase() });
    });

    function render() {
      var terms = input.value.toLowerCase().split(/\s+/).filter(Boolean);
      results.textContent = '';
      if (!terms.length) {
        document.body.classList.remove('ms-searching');
        status.hidden = true;
        return;
      }
      document.body.classList.add('ms-searching');
      var matches = index.filter(function (entry) {
        return terms.every(function (t) { return entry.haystack.indexOf(t) !== -1; });
      });
      matches.slice(0, MAX_RESULTS).forEach(function (entry) {
        var li = document.createElement('li');
        var copy = entry.link.cloneNode(true);
        copy.removeAttribute('id');
        li.appendChild(copy);
        if (entry.crumb) {
          var crumb = document.createElement('span');
          crumb.className = 'ms-crumb';
          crumb.textContent = entry.crumb;
          li.appendChild(crumb);
        }
        results.appendChild(li);
      });
      status.hidden = false;
      status.textContent = !matches.length ? 'No matches.' :
        matches.length > MAX_RESULTS ? 'Showing the first ' + MAX_RESULTS + ' of ' + matches.length + ' matches.' :
        matches.length + (matches.length === 1 ? ' match.' : ' matches.');
    }

    input.addEventListener('input', render);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && input.value) {
        input.value = '';
        render();
      }
    });

    // Highlight the document currently open, in the tree and in results.
    document.addEventListener('click', function (event) {
      var a = event.target.closest && event.target.closest('a[href]');
      if (!a || !/\.pdf(?:[?#]|$)/i.test(a.getAttribute('href') || '')) return;
      var href = a.getAttribute('href');
      Array.prototype.forEach.call(document.querySelectorAll('a[aria-current="page"]'), function (el) {
        el.removeAttribute('aria-current');
      });
      Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (el) {
        if (el.getAttribute('href') === href && textOf(el) === textOf(a)) el.setAttribute('aria-current', 'page');
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
