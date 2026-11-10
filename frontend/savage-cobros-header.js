/* Savage Grill · navegación contextual de cobros, nunca envía al login al usar Volver con sesión vigente. */
(()=>{
  'use strict';
  const page=document.body.dataset.sgPortal;
  if(!['cliente','personal'].includes(page))return;
  const inicio=()=>{
    if(page==='cliente')return 'catalogo.html';
    let user=null;
    try{user=JSON.parse(sessionStorage.getItem('savage_usuario')||'null')}catch{}
    const r=String(user?.rol?.nombre||user?.rol||user?.rol_nombre||user?.nombre_rol||'').toLowerCase();
    if(r.includes('gerente'))return 'gerente.html';
    if(r.includes('admin'))return 'admin.html';
    if(r.includes('cocina'))return 'cocina.html';
    if(r.includes('mozo'))return 'mozo.html';
    // Si el empleado entra a cobros sin una sesión previa, conservar un acceso operativo.
    return sessionStorage.getItem('savage_token')?'mozo.html':'login.html';
  };
  const actualizar=()=>{
    const ruta=inicio();
    document.querySelectorAll('[data-sg-regreso],[data-sg-inicio]').forEach(el=>{el.href=ruta;});
    const m=sessionStorage.getItem('savage-mesa-numero');
    const badge=document.querySelector('[data-sg-numero-mesa]');
    if(badge)badge.textContent=m&&/^\d+$/.test(m)?`Mesa ${m}`:'Mi mesa';
    const ident=document.querySelector('.sg-v5-rol');
    if(ident && page==='personal')ident.textContent=ruta==='gerente.html'?'Gerencia':ruta==='admin.html'?'Administración':'Mi salón';
  };
  actualizar();
  window.addEventListener('sg-personal-listo',actualizar);
  const salir=document.querySelector('[data-sg-salir]');
  salir?.addEventListener('click',()=>{
    if(page==='cliente'){
      ['savage-mesa-numero','savage-mesa-pin','savage-comensales','savage-carrito','savage-envio-pendiente'].forEach(k=>sessionStorage.removeItem(k));
      location.assign('pin.html');
    }else{
      ['savage_token','savage_usuario'].forEach(k=>sessionStorage.removeItem(k));
      location.assign('login.html');
    }
  });
  const menu=document.querySelector('.sg-v5-menu');
  if(menu){
    document.addEventListener('click',e=>{if(!menu.contains(e.target))menu.open=false;});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){menu.open=false;menu.querySelector('summary')?.focus();}});
  }
})();
