// menu_tcm.js — collapsible navigation menu behaviour.
//
// Modernised from the original IE-era script: no eval(), no document.all,
// no browser sniffing. The public showmenu(id) API is unchanged so the
// existing menu markup keeps working.
'use strict';

/**
 * Toggle the visibility of a collapsible menu section by element id.
 * @param {string} id - The id of the sub-menu container to toggle.
 * @returns {boolean} false, so inline handlers can prevent default navigation.
 */
function showmenu(id) {
  var el = document.getElementById(id);
  if (!el) {
    return false;
  }

  var isHidden = el.hidden || el.getAttribute('aria-hidden') === 'true' ||
    getComputedStyle(el).display === 'none';

  el.hidden = !isHidden;
  el.style.display = isHidden ? '' : 'none';
  el.setAttribute('aria-hidden', String(!isHidden));

  // Keep any triggering control's expanded state in sync for assistive tech.
  var trigger = document.querySelector('[aria-controls="' + id + '"]');
  if (trigger) {
    trigger.setAttribute('aria-expanded', String(isHidden));
  }

  return false;
}

// Backwards-compatible alias for the old Opera-specific entry point.
function showmenu_opera(id) {
  return showmenu(id);
}

// Progressive enhancement: let keyboard users operate menu triggers that
// were originally wired up with mouse-only inline handlers.
document.addEventListener('keydown', function (event) {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return;
  }
  var target = event.target;
  var controls = target && target.getAttribute && target.getAttribute('aria-controls');
  if (controls) {
    event.preventDefault();
    showmenu(controls);
  }
});
