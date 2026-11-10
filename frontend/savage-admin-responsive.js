/* Savage Grill P41: menú accesible y selector de tema compartido en Administración.
   No modifica acciones, datos, rutas, endpoints ni lógica de administración. */
(() => {
  'use strict';
  const iniciar = () => {
    const sidebar = document.getElementById('sg-admin-nav');
    const abrir = document.getElementById('sg-admin-menu-open');
    const cerrar = document.getElementById('sg-admin-menu-close');
    const fondo = document.getElementById('sg-admin-mobile-overlay');
    const titulo = document.getElementById('sg-admin-mobile-title');
    // Replica la visibilidad determinada por admin-panel.js; no decide permisos por su cuenta.
    const volverMenu = document.getElementById('admin-ir-gerente');
    const volverDirecto = document.getElementById('sg-admin-manager-return');
    const volverBoton = document.getElementById('sg-admin-manager-return-btn');
    if (volverMenu && volverDirecto && volverBoton) {
      const sincronizarAcceso = () => { volverDirecto.hidden = volverMenu.hidden; };
      volverBoton.addEventListener('click', () => {
        if (!volverMenu.hidden) volverMenu.click();
      });
      new MutationObserver(sincronizarAcceso).observe(volverMenu, {attributes:true,attributeFilter:['hidden']});
      sincronizarAcceso();
    }
    const slotMovil = document.getElementById('sg-admin-theme-mobile-slot');
    const slotDesktop = document.getElementById('sg-admin-theme-desktop-slot');
    const tema = document.querySelector('[data-savage-theme]');
    if (![sidebar,abrir,cerrar,fondo,titulo,slotMovil,slotDesktop,tema].every(Boolean)) return;
    const media = window.matchMedia('(max-width:1100px)');
    let anterior = null;
    let abierto = false;
    function actualizarSeccion() {
      const seleccionado = sidebar.querySelector('[data-admin-tab].active');
      titulo.textContent = seleccionado?.querySelector('.sg-nav-label')?.textContent?.trim() || 'Administración general';
    }
    function setAbierto(valor, {devolverFoco=true}={}) {
      abierto = Boolean(valor && media.matches);
      document.body.classList.toggle('sg-admin-nav-open', abierto);
      fondo.hidden = !abierto;
      abrir.setAttribute('aria-expanded',String(abierto));
      sidebar.setAttribute('aria-hidden',String(!abierto && media.matches));
      if ('inert' in sidebar) sidebar.inert = Boolean(!abierto && media.matches);
      if (abierto) {
        anterior = document.activeElement;
        cerrar.focus();
      } else if (devolverFoco && anterior && media.matches) {
        (anterior.isConnected ? anterior : abrir).focus();
        anterior=null;
      }
    }
    function ubicarTema() {
      if (media.matches) slotMovil.appendChild(tema);
      else slotDesktop.appendChild(tema);
      // Mantiene el selector compartido, que ya está montado, y evita cerrarlo por un reflow.
      window.SavageTheme?.montar();
    }
    abrir.addEventListener('click',()=>setAbierto(true));
    cerrar.addEventListener('click',()=>setAbierto(false));
    fondo.addEventListener('click',()=>setAbierto(false));
    sidebar.addEventListener('click',ev=>{
      if (ev.target.closest('[data-admin-tab],#admin-ir-gerente')) {
        actualizarSeccion();
        setAbierto(false,{devolverFoco:false});
        if (media.matches) abrir.focus();
      }
    });
    document.addEventListener('keydown',ev=>{
      if (ev.key!=='Escape' || !abierto) return;
      ev.preventDefault();setAbierto(false);
    });
    // El foco de teclado no puede escapar del menú abierto hacia el fondo.
    sidebar.addEventListener('keydown',ev=>{
      if (ev.key!=='Tab' || !abierto) return;
      const controles=[...sidebar.querySelectorAll('button:not([disabled]):not([hidden]),[href],input,select,[tabindex="0"]')].filter(x=>x.getClientRects().length && !x.closest('[hidden]'));
      if (!controles.length) return;
      const primero=controles[0],ultimo=controles.at(-1);
      if (ev.shiftKey && document.activeElement===primero) {ev.preventDefault();ultimo.focus();}
      else if (!ev.shiftKey && document.activeElement===ultimo) {ev.preventDefault();primero.focus();}
    });
    function cambioViewport() { setAbierto(false,{devolverFoco:false}); ubicarTema(); actualizarSeccion(); }
    if (media.addEventListener) media.addEventListener('change',cambioViewport);
    else media.addListener(cambioViewport);
    const observador = new MutationObserver(actualizarSeccion);
    sidebar.querySelectorAll('[data-admin-tab]').forEach(b => observador.observe(b,{attributes:true,attributeFilter:['class','aria-current']}));
    actualizarSeccion();ubicarTema();setAbierto(false,{devolverFoco:false});
  };
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',iniciar,{once:true});
  else iniciar();
})();
