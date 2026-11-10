/* Reorganizacion visual no destructiva de login.html: se conservan form, ids y listeners. */
(function () {
  'use strict';
  function iniciar() {
    const form = document.querySelector('form');
    if (!form) { console.warn('[Savage Grill] Login: no se encontro el formulario.'); return; }
    let panel = null;
    for (let node = form.parentElement; node && node !== document.body; node = node.parentElement) {
      const text = (node.innerText || '').toLowerCase();
      if (text.includes('bienvenido') && node.querySelectorAll('form').length === 1) {
        panel = node; break;
      }
    }
    if (!panel) panel = form.parentElement;
    if (!panel || panel === document.body) return;

    // Reutilizar la misma foto que ya usa el login, sin descargar ni inventar recursos.
    let imagen = '';
    const elts = [document.body, ...document.body.querySelectorAll('*')];
    let mejorPuntaje = -1;
    for (const element of elts) {
      if (panel.contains(element) || element === panel) continue;
      const css = getComputedStyle(element);
      const bg = css.backgroundImage;
      let candidato = bg && bg !== 'none' && bg.includes('url(') ? bg : '';
      if (!candidato && element.tagName === 'IMG' && element.currentSrc) candidato = `url("${element.currentSrc.replaceAll('"','%22')}")`;
      if (!candidato) continue;
      const rect = element.getBoundingClientRect();
      const area = Math.max(0, rect.width * rect.height);
      if (area > mejorPuntaje) { imagen = candidato; mejorPuntaje = area; }
    }
    if (imagen) document.body.style.setProperty('--sg-login-fondo', imagen);
    document.body.classList.add('sg-login-centralizado');
    panel.classList.add('sg-login-panel-central');
    if (!/savage\s*grill/i.test(panel.innerText || '')) {
      const marca = document.createElement('div');
      marca.className = 'sg-login-marca';
      marca.innerHTML = 'SAVAGE<strong>GRILL.</strong>';
      panel.insertBefore(marca, panel.firstChild);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
