/* Savage Grill · accesos contextuales a cuentas y cobros. */
(() => {
 'use strict';
 const iniciar=()=>{
   const pagina=location.pathname.split('/').pop().toLowerCase();
   const cliente=['catalogo.html','carrito.html'].includes(pagina);
   if(!cliente&&!['mozo.html','admin.html','gerente.html'].includes(pagina))return;
   if(document.querySelector('.sg-enlace-cobros'))return;
   const enlace=document.createElement('a');enlace.className='sg-enlace-cobros';
   enlace.href=cliente?'mi-cuenta.html':'cobros.html';
   enlace.textContent=cliente?'Mi cuenta':'Caja y cobros';
   enlace.style.cssText='display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:10px 14px;border-radius:11px;border:1px solid rgba(255,122,0,.5);background:rgba(255,122,0,.1);color:#ff861d;font-size:13px;font-weight:800;text-decoration:none;line-height:1.3;max-width:100%;';
   if(pagina==='catalogo.html'){
     const header=document.querySelector('.sg-header');
     if(header){const anchor=header.querySelector('.sg-header-actions,.header-actions');if(anchor){anchor.prepend(enlace);return;}}
     const main=document.querySelector('main');if(main){enlace.style.marginBottom='14px';main.prepend(enlace);}return;
   }
   if(pagina==='carrito.html'){
     const header=document.querySelector('header');if(header){enlace.style.margin='10px 16px';header.insertAdjacentElement('afterend',enlace);}return;
   }
   if(pagina==='mozo.html'){
     const h=document.querySelector('header');if(h){enlace.style.margin='12px 18px';h.insertAdjacentElement('afterend',enlace);}return;
   }
   const nav=document.querySelector('.sg-admin-sidebar,.g-sidebar,aside,.sidebar');
   if(nav){enlace.style.margin='12px 8px';nav.append(enlace);return;}
   document.querySelector('header')?.append(enlace);
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',iniciar,{once:true});else iniciar();
})();
