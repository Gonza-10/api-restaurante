/* Compatible con menus que usan .open/.active o toggles nativos; detecta antes de aplicar. */
(function () {
 'use strict';
 const media = matchMedia('(max-width: 900px)');
 const selectores = ['.sidebar', '[class*="sidebar"]', '#sidebar', '[id*="sidebar"]',
   '.side-nav', '.menu-lateral', '.drawer', '[class*="drawer"]', 'aside'];
 const estados = /(^|\s)(open|opened|active|show|shown|visible|is-open|is-active|expanded|menu-open|sidebar-open)(\s|$)/i;
 const texto = e => (e.textContent || '').toLowerCase();
 function iniciar() {
   const candidatos = [...new Set(selectores.flatMap(s => [...document.querySelectorAll(s)]))];
   const panel = candidatos.find(e => e !== document.body && !e.closest('dialog') &&
     /gesti[oó]n de men[uú]|proveedores|insumos|secciones|cerrar sesi[oó]n|administraci[oó]n|gerencia/i.test(texto(e)) &&
     (e.querySelectorAll('a,button').length >= 2));
   if (!panel) { console.warn('[Savage Grill] No se identifico el lateral: se conserva el original.'); return; }
   panel.classList.add('sg-panel-lateral-derecha');
   document.body.classList.add('sg-menu-derecha');
   const btn = [...document.querySelectorAll('button,[role="button"]')].find(e =>
      !panel.contains(e) && (/men[uú]|abrir/i.test((e.getAttribute('aria-label') || '') + ' ' + texto(e)) ||
      /menu|hamburger/i.test(e.id + ' ' + e.className)));
   if (!btn) { console.warn('[Savage Grill] No se detecto el boton del menu; se preserva funcionamiento original.');
      panel.classList.remove('sg-panel-lateral-derecha'); document.body.classList.remove('sg-menu-derecha'); return; }
   let aperturaClick = false;
   function evaluar() {
     const aria = btn.getAttribute('aria-expanded');
     const hayEstado = estados.test(panel.className) || estados.test(document.body.className) ||
       estados.test(document.documentElement.className);
     const estaAbierto = aria === 'true' || hayEstado || (aria == null && aperturaClick);
     panel.classList.toggle('sg-panel-lateral-abierto', !!estaAbierto);
     if (!media.matches) panel.classList.remove('sg-panel-lateral-abierto');
   }
   let pendiente = false;
   function programar() { if (pendiente) return; pendiente=true; setTimeout(()=>{ pendiente=false; evaluar(); },30); }
   btn.addEventListener('click', () => {aperturaClick = !aperturaClick; programar();});
   panel.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{ aperturaClick=false;programar(); }));
   const obs = new MutationObserver(programar);
   [panel, btn, document.body, document.documentElement].forEach(el=>obs.observe(el,{attributes:true, attributeFilter:['class','aria-expanded','style']}));
   media.addEventListener?.('change', programar);
   evaluar();
 }
 if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',iniciar); else iniciar();
})();
