/* Savage Grill · navegación de cobros según función del empleado. */
(()=>{'use strict';
 if(document.body.dataset.sgPortal!=='personal')return;
 const nav=document.getElementById('sg-cobros-nav');
 const botones=[...document.querySelectorAll('[data-sg-panel]')];
 function activar(nombre){
   if(!botones.some(b=>b.dataset.sgPanel===nombre&&!b.hidden))nombre='mesas';
   for(const b of botones){const ok=b.dataset.sgPanel===nombre;b.classList.toggle('activo',ok);b.setAttribute('aria-pressed',String(ok));}
   for(const p of document.querySelectorAll('[data-sg-contenido]'))p.hidden=p.dataset.sgContenido!==nombre;
 }
 botones.forEach(b=>b.addEventListener('click',()=>activar(b.dataset.sgPanel)));
 window.addEventListener('sg-personal-listo',e=>{
   const rol=String(e.detail?.rol||'');const gerente=/admin|gerente/i.test(rol);
   document.querySelectorAll('.sg-solo-gerencia').forEach(el=>el.hidden=!gerente);
   nav.hidden=false;activar('mesas');
 });
 const exit=document.getElementById('personal-salir');
 exit?.addEventListener('click',()=>{nav.hidden=true;activar('mesas');});
})();
