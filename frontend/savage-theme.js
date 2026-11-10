/* Savage Grill · tema compartido Claro / Oscuro / Sistema.
   Compatible con la clave anterior `savage-tema`, y con `body.light-mode` existente.
   Se integra por <div data-savage-theme="inline"></div>; no modifica la API ni sesiones. */
(() => {
    'use strict';
    if (window.SavageTheme) return;
    const CLAVE = 'savage-tema';
    const preferidos = new Set(['light','dark','system']);
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const iconos = {
        sun: '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>',
        moon:'<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z"/></svg>',
        system:'<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>'
    };
    let elegido = leer();
    let hostActual = null;
    let botonActual = null;
    let menuActual = null;
    function leer() {
        try {
            const guardado = localStorage.getItem(CLAVE);
            return preferidos.has(guardado) ? guardado : 'dark'; // compatibilidad con predeterminado anterior
        } catch { return 'dark'; }
    }
    function activo() { return elegido === 'system' ? (media.matches ? 'dark' : 'light') : elegido; }
    function nombre(v) { return ({light:'Claro',dark:'Oscuro',system:'Sistema'})[v]; }
    function aplicar() {
        if (!document.body) return;
        document.body.classList.toggle('light-mode', activo() === 'light');
        document.body.classList.add('sg-theme-active');
        document.querySelectorAll('body > .btn-tema').forEach(b => b.remove());
        if (botonActual) {
            botonActual.innerHTML = activo() === 'dark' ? iconos.moon : iconos.sun;
            botonActual.setAttribute('aria-label', `Elegir tema. Modo actual: ${nombre(elegido)}`);
            botonActual.title = `Tema: ${nombre(elegido)}`;
        }
        if (menuActual) {
            menuActual.querySelectorAll('[data-sg-theme-option]').forEach(b =>
                b.setAttribute('aria-checked', String(b.dataset.sgThemeOption === elegido))
            );
        }
    }
    function elegir(nuevo) {
        if (!preferidos.has(nuevo)) return;
        elegido = nuevo;
        try { localStorage.setItem(CLAVE,nuevo); } catch {}
        aplicar();
    }
    function cerrar({focus=false}={}) {
        if (!menuActual || menuActual.hidden) return;
        menuActual.hidden = true;
        botonActual?.setAttribute('aria-expanded','false');
        if (focus) botonActual?.focus();
    }
    // Ancla el extremo derecho del menú al del botón: abre hacia la izquierda.
    // Si el botón está en el borde izquierdo de un teléfono, desplaza el panel
    // lo mínimo indispensable hacia dentro de la pantalla para que sea usable.
    function posicionarMenu() {
        if (!menuActual || menuActual.hidden) return;
        menuActual.style.removeProperty('--sg-theme-shift');
        const rect = menuActual.getBoundingClientRect();
        const margen = 8;
        const ancho = document.documentElement.clientWidth || window.innerWidth;
        let desplazamiento = 0;
        if (rect.left < margen) desplazamiento = margen - rect.left;
        else if (rect.right > ancho - margen) desplazamiento = ancho - margen - rect.right;
        if (desplazamiento) {
            menuActual.style.setProperty('--sg-theme-shift', `${Math.round(desplazamiento)}px`);
        }
    }
    function abrir() {
        if (!menuActual || !botonActual) return;
        menuActual.hidden = false;
        botonActual.setAttribute('aria-expanded','true');
        posicionarMenu();
        menuActual.querySelector('[aria-checked="true"]')?.focus();
    }
    function montar() {
        const host = document.querySelector('[data-savage-theme]');
        if (!host || hostActual === host) { aplicar(); return; }
        hostActual = host;
        host.classList.add('sg-theme-host');
        host.innerHTML = '';
        const boton = document.createElement('button');
        boton.type='button'; boton.className='sg-theme-trigger';
        boton.setAttribute('aria-haspopup','menu'); boton.setAttribute('aria-expanded','false');
        const menu = document.createElement('div');
        menu.id = 'sg-theme-menu'; menu.className = 'sg-theme-popup';
        menu.setAttribute('role','menu'); menu.setAttribute('aria-label','Elegir modo de apariencia');
        menu.hidden = true;
        boton.setAttribute('aria-controls',menu.id);
        const opciones = [
            ['light','Modo Claro',iconos.sun],['dark','Modo Oscuro',iconos.moon],['system','Usar tema del sistema',iconos.system]
        ];
        for (const [valor,texto,svg] of opciones) {
            const item=document.createElement('button');
            item.type='button'; item.className='sg-theme-option';
            item.dataset.sgThemeOption=valor;
            item.setAttribute('role','menuitemradio'); item.setAttribute('aria-checked','false');
            item.innerHTML=svg;
            const label=document.createElement('span'); label.textContent=texto;
            const check=document.createElement('span'); check.className='sg-theme-check'; check.textContent='✓'; check.setAttribute('aria-hidden','true');
            item.append(label,check);
            item.addEventListener('click',() => { elegir(valor); cerrar({focus:true}); });
            item.addEventListener('keydown',ev => {
                const items=[...menu.querySelectorAll('[data-sg-theme-option]')];
                const idx=items.indexOf(item);
                if (ev.key==='ArrowDown' || ev.key==='ArrowUp') {
                    ev.preventDefault(); items[(idx+(ev.key==='ArrowDown'?1:items.length-1))%items.length].focus();
                } else if (ev.key==='Escape') { ev.preventDefault(); cerrar({focus:true}); }
            });
            menu.appendChild(item);
        }
        host.append(boton,menu);
        botonActual=boton;menuActual=menu;
        boton.addEventListener('click',() => menu.hidden ? abrir() : cerrar());
        window.addEventListener('resize',posicionarMenu,{passive:true});
        document.addEventListener('click',ev => { if (!host.contains(ev.target)) cerrar(); });
        document.addEventListener('keydown',ev => { if (ev.key==='Escape' && !menu.hidden) { ev.preventDefault(); cerrar({focus:true}); } });
        aplicar();
    }
    if (media.addEventListener) media.addEventListener('change',() => { if (elegido==='system') aplicar(); });
    else media.addListener(() => { if (elegido==='system') aplicar(); });
    window.addEventListener('storage',ev => { if (ev.key===CLAVE) { elegido=leer(); aplicar(); } });
    // Oculta el botón anterior agregado por app.js si se inserta después del montaje.
    const observador=new MutationObserver(() => {
        if (document.body?.classList.contains('sg-theme-active')) {
            document.querySelectorAll('body > .btn-tema').forEach(b => b.remove());
        }
    });
    const inicio=() => { montar(); observador.observe(document.body,{childList:true}); };
    if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',inicio,{once:true});
    else inicio();
    window.SavageTheme={ seleccionar:elegir, preferencia:()=>elegido, apariencia:activo, montar };
})();
