/* =========================================================================
   Savage Grill · Utilidades compartidas de las pantallas nuevas
   (Cobros del salón, Pagar, Reservas, Barra).
   No depende de app.js: usa la misma sesión (sessionStorage) y la misma API.
   ========================================================================= */
(() => {
    'use strict';
    if (window.SG) return;
    const SG = (window.SG = {});

    const BASE = (window.SAVAGE_CONFIG && window.SAVAGE_CONFIG.API_BASE_URL) || 'http://localhost:8080/api/v1';
    SG.BASE = BASE;

    /* Modo embebido: la pantalla se muestra dentro del panel de Admin/Gerente (iframe ?embebido=1). */
    SG.embebido = /[?&]embebido=1/.test(window.location.search) && window.parent !== window;
    if (SG.embebido) document.documentElement.classList.add('sg-embebido');
    const VENTANA = () => (SG.embebido ? window.top : window);

    /* ---------------------------------------------------------------- texto */
    SG.esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    SG.html = (txt) => { const t = document.createElement('template'); t.innerHTML = txt.trim(); return t.content.firstElementChild; };
    SG.$ = (sel, ctx = document) => ctx.querySelector(sel);
    SG.$$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
    SG.clave = () => {
        try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch { /* sigue */ }
        const h = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1);
        return `${h()}${h()}-${h()}-${h()}-${h()}-${h()}${h()}${h()}`;
    };
    SG.debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

    /* ---------------------------------------------------------------- iconos */
    const I = (d, extra = '') => `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;
    const ICONOS = {
        efectivo: I('<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v.01M18 14.5v.01"/>'),
        tarjeta: I('<rect x="2.5" y="5" width="19" height="14" rx="2.2"/><path d="M2.5 10h19M6.5 15h4"/>'),
        mercadopago: I('<rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><path d="M14 14h3v3m4 0v4h-4m-3-1v1m0-4v.01"/>'),
        check: I('<path d="M20 6 9 17l-5-5"/>'),
        alerta: I('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4v.01"/>'),
        info: I('<circle cx="12" cy="12" r="9.5"/><path d="M12 11v5m0-8.5v.01"/>'),
        x: I('<path d="M18 6 6 18M6 6l12 12"/>'),
        volver: I('<path d="M19 12H5m6-6-6 6 6 6"/>'),
        salir: I('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>'),
        refrescar: I('<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16m0 0v5m0-5h5M3 12A9 9 0 0 1 18.5 5.8L21 8m0 0V3m0 5h-5"/>'),
        buscar: I('<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.3-4.3"/>'),
        mas: I('<path d="M12 5v14M5 12h14"/>'),
        descargar: I('<path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5M4 20h16"/>'),
        imprimir: I('<path d="M6 9V3h12v6M6 18H4a1 1 0 0 1-1-1v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6a1 1 0 0 1-1 1h-2"/><rect x="6" y="14" width="12" height="7" rx="1"/>'),
        candado: I('<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>'),
        reloj: I('<circle cx="12" cy="12" r="9.5"/><path d="M12 7v5l3 2"/>'),
        usuario: I('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'),
        grupo: I('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 6.5 0 0 0-4-6"/>'),
        dividir: I('<path d="M12 3v18M4 7h16M4 17h16"/>'),
        campana: I('<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8Z"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/>'),
        calendario: I('<rect x="3" y="4.5" width="18" height="16.5" rx="2"/><path d="M3 10h18M8 2.5v4m8-4v4"/>'),
        trago: I('<path d="M5 4h14l-7 8.5L5 4Z"/><path d="M12 12.5V20m-4 0h8"/>'),
        mesa: I('<rect x="3" y="9" width="18" height="3" rx="1"/><path d="M6 12v8m12-8v8"/>'),
        recibo: I('<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6"/>'),
        caja: I('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V4h8v3M3 13h18"/>'),
        moneda: I('<circle cx="12" cy="12" r="9.5"/><path d="M14.8 9.2c-.5-.9-1.5-1.4-2.8-1.4-1.6 0-2.8.8-2.8 2 0 3 5.8 1.4 5.8 4.4 0 1.2-1.2 2-2.9 2-1.4 0-2.5-.6-3-1.6M12 6v1.8m0 8.4V18"/>'),
        lapiz: I('<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/>'),
        ojo: I('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>')
    };
    SG.ico = (n) => ICONOS[n] || '';

    /* -------------------------------------------------------------- sesión */
    SG.token = () => { try { return sessionStorage.getItem('savage_token'); } catch { return null; } };
    SG.usuario = () => { try { const u = sessionStorage.getItem('savage_usuario'); return u ? JSON.parse(u) : null; } catch { return null; } };
    SG.rol = () => (SG.usuario() || {}).rol || '';
    SG.cerrarSesion = () => {
        try { sessionStorage.removeItem('savage_token'); sessionStorage.removeItem('savage_usuario'); } catch { /* nada */ }
        VENTANA().location.href = 'login.html';
    };
    SG.PANEL = { Mozo: 'mozo.html', Admin: 'admin.html', Gerente: 'gerente.html', Cocina: 'cocina.html', Bartender: 'barra.html' };
    SG.panelDe = (rol) => SG.PANEL[rol] || 'login.html';
    /* Si no hay sesión o el rol no corresponde, vuelve al panel que le toca. */
    SG.exigirRol = (roles) => {
        const u = SG.usuario();
        if (!SG.token() || !u) { SG.cerrarSesion(); return false; }
        if (roles && !roles.includes(u.rol)) { VENTANA().location.replace(SG.panelDe(u.rol)); return false; }
        return true;
    };
    SG.esAdminGerente = () => ['Admin', 'Gerente'].includes(SG.rol());

    /* ------------------------------------------------------------------ API */
    function mensajeDe(data, status) {
        if (data && typeof data === 'object') {
            if (typeof data.error === 'string') return data.error;
            if (typeof data.detail === 'string') return data.detail;
            const partes = [];
            Object.keys(data).forEach((k) => {
                const v = data[k];
                if (Array.isArray(v)) partes.push(v.map(String).join(' '));
                else if (typeof v === 'string') partes.push(v);
            });
            if (partes.length) return partes.join(' ');
        }
        if (status === 403) return 'No tenés permiso para hacer esto.';
        if (status === 404) return 'No se encontró lo que buscabas.';
        if (status >= 500) return 'El sistema tuvo un problema. Probá de nuevo en unos segundos.';
        return 'No se pudo completar la acción.';
    }
    SG.mensajeDe = mensajeDe;

    /* Devuelve siempre {ok, status, data, error}; nunca lanza por un error de la API. */
    SG.api = async (ruta, { method = 'GET', body, auth = true, signal } = {}) => {
        const headers = {};
        if (body !== undefined) headers['Content-Type'] = 'application/json';
        if (auth && SG.token()) headers.Authorization = `Bearer ${SG.token()}`;
        let resp;
        try {
            resp = await fetch(BASE + ruta, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal });
        } catch (e) {
            if (e && e.name === 'AbortError') return { ok: false, status: 0, data: null, error: '', abortado: true };
            return { ok: false, status: 0, data: null, error: 'No hay conexión con el sistema. Revisá la red e intentá de nuevo.' };
        }
        if (resp.status === 401 && auth) { SG.cerrarSesion(); return { ok: false, status: 401, data: null, error: 'Tu sesión venció.' }; }
        let data = null;
        try { data = await resp.json(); } catch { data = null; }
        return { ok: resp.ok, status: resp.status, data, error: resp.ok ? '' : mensajeDe(data, resp.status) };
    };
    /* Descarga un archivo (PDF) con la sesión puesta y lo abre/baja. */
    SG.archivo = async (ruta, nombre) => {
        let resp;
        try { resp = await fetch(BASE + ruta, { headers: SG.token() ? { Authorization: `Bearer ${SG.token()}` } : {} }); }
        catch { return { ok: false, error: 'No hay conexión con el sistema.' }; }
        if (!resp.ok) {
            let d = null; try { d = await resp.json(); } catch { /* sin cuerpo */ }
            return { ok: false, error: mensajeDe(d, resp.status) };
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = nombre || 'comprobante.pdf'; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        return { ok: true };
    };

    /* --------------------------------------------------------------- dinero */
    const MONEDAS = {
        ARS: { sim: '$', dec: 2, nombre: 'Pesos argentinos', corto: 'Pesos' },
        USD: { sim: 'US$', dec: 2, nombre: 'Dólares', corto: 'Dólares' },
        BRL: { sim: 'R$', dec: 2, nombre: 'Reales', corto: 'Reales' },
        PYG: { sim: 'Gs.', dec: 0, nombre: 'Guaraníes', corto: 'Guaraníes' }
    };
    SG.MONEDAS = MONEDAS;
    SG.CODIGOS = ['ARS', 'USD', 'BRL', 'PYG'];
    SG.num = (v) => { const n = typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.')); return Number.isFinite(n) ? n : 0; };
    SG.numero = (valor, dec = 2) => {
        const n = SG.num(valor);
        const neg = n < 0;
        const [ent, fra] = Math.abs(n).toFixed(dec).split('.');
        const miles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        return (neg ? '-' : '') + miles + (dec > 0 ? ',' + fra : '');
    };
    SG.dinero = (valor, moneda = 'ARS') => {
        const m = MONEDAS[moneda] || MONEDAS.ARS;
        return `${m.sim} ${SG.numero(valor, m.dec)}`;
    };
    /* "1.500,50" / "1500.5" / "1.500" -> "1500.50" (texto con punto, listo para la API). null si no es válido. */
    SG.parseMonto = (txt) => {
        let t = String(txt ?? '').trim().replace(/^(US\$|R\$|Gs\.?|\$)/, '').replace(/\s/g, '');
        if (!t) return null;
        if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
        else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');
        if (!/^\d+(\.\d+)?$/.test(t)) return null;
        const n = parseFloat(t);
        return Number.isFinite(n) ? String(n) : null;
    };

    /* ---------------------------------------------------------------- fechas */
    const dosd = (n) => String(n).padStart(2, '0');
    SG.fechaHora = (iso) => {
        if (!iso) return '—';
        const d = new Date(iso); if (isNaN(d)) return '—';
        return `${dosd(d.getDate())}/${dosd(d.getMonth() + 1)}/${d.getFullYear()} ${dosd(d.getHours())}:${dosd(d.getMinutes())}`;
    };
    SG.hora = (iso) => { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : `${dosd(d.getHours())}:${dosd(d.getMinutes())}`; };
    SG.fecha = (iso) => {
        if (!iso) return '—';
        const s = String(iso).slice(0, 10).split('-');
        return s.length === 3 ? `${s[2]}/${s[1]}/${s[0]}` : '—';
    };
    SG.hoy = () => { const d = new Date(); return `${d.getFullYear()}-${dosd(d.getMonth() + 1)}-${dosd(d.getDate())}`; };
    SG.hace = (iso) => {
        if (!iso) return '';
        const seg = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
        if (seg < 60) return 'recién';
        const min = Math.round(seg / 60); if (min < 60) return `hace ${min} min`;
        const h = Math.floor(min / 60); return `hace ${h} h ${min % 60} min`;
    };

    /* ------------------------------------------------------- bloqueo scroll */
    let bloqueos = 0;
    const bloquear = (si) => {
        bloqueos = Math.max(0, bloqueos + (si ? 1 : -1));
        document.documentElement.style.overflow = bloqueos ? 'hidden' : '';
    };

    /* ---------------------------------------------------------------- avisos */
    let zonaAvisos = null;
    SG.aviso = (texto, tipo = 'info', ms = 5200) => {
        if (!zonaAvisos) {
            zonaAvisos = document.createElement('div');
            zonaAvisos.className = 'sg-avisos'; zonaAvisos.setAttribute('role', 'status'); zonaAvisos.setAttribute('aria-live', 'polite');
            document.body.appendChild(zonaAvisos);
        }
        const icono = tipo === 'ok' ? 'check' : tipo === 'mal' ? 'alerta' : 'info';
        const el = SG.html(`<div class="sg-aviso ${tipo}">${SG.ico(icono)}<span>${SG.esc(texto)}</span></div>`);
        zonaAvisos.appendChild(el);
        const quitar = () => el.remove();
        el.addEventListener('click', quitar);
        setTimeout(quitar, tipo === 'mal' ? Math.max(ms, 7000) : ms);
    };
    SG.ok = (t) => SG.aviso(t, 'ok');
    SG.mal = (t) => SG.aviso(t, 'mal');

    /* ---------------------------------------------------------- ventana flotante */
    const FOCO = 'button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])';
    /* Abre un nodo dentro de una ventana flotante. Devuelve {cerrar, el}. */
    SG.ventana = (contenido, { ancha = false, alCerrar, cerrarConFondo = true, etiqueta = '' } = {}) => {
        const previo = document.activeElement;
        const velo = SG.html('<div class="sg-velo"></div>');
        const modal = SG.html(`<div class="sg-modal ${ancha ? 'ancha' : ''}" role="dialog" aria-modal="true" ${etiqueta ? `aria-label="${SG.esc(etiqueta)}"` : ''}></div>`);
        modal.appendChild(contenido); velo.appendChild(modal); document.body.appendChild(velo); bloquear(true);
        let cerrada = false;
        const cerrar = (valor) => {
            if (cerrada) return; cerrada = true;
            document.removeEventListener('keydown', teclas, true);
            velo.remove(); bloquear(false);
            if (previo && previo.focus) { try { previo.focus(); } catch { /* nada */ } }
            if (alCerrar) alCerrar(valor);
        };
        function teclas(e) {
            if (!document.body.contains(velo)) return;
            // solo reacciona la ventana de más arriba
            const todas = document.querySelectorAll('.sg-velo');
            if (todas[todas.length - 1] !== velo) return;
            if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrar(null); return; }
            if (e.key !== 'Tab') return;
            const f = SG.$$(FOCO, modal).filter((x) => x.offsetParent !== null);
            if (!f.length) { e.preventDefault(); return; }
            const a = f[0], z = f[f.length - 1];
            if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
            else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
            else if (!modal.contains(document.activeElement)) { e.preventDefault(); a.focus(); }
        }
        document.addEventListener('keydown', teclas, true);
        if (cerrarConFondo) velo.addEventListener('mousedown', (e) => { if (e.target === velo) cerrar(null); });
        return { cerrar, el: modal };
    };

    /* Confirmación / aviso. Devuelve una promesa: {motivo} si aceptó, null si canceló.
       motivo: {etiqueta, placeholder, obligatorio, max}  ·  campos: [{id, etiqueta, placeholder, valor}] opcional */
    SG.dialogo = ({ titulo, texto = '', html = '', icono = 'alerta', peligro = false, aceptar = 'Aceptar', cancelar = 'Cancelar', motivo = null }) =>
        new Promise((resolver) => {
            const cont = document.createElement('div');
            cont.innerHTML = `
                <div class="sg-modal-icono ${peligro ? 'peligro' : ''}">${SG.ico(icono)}</div>
                <h3>${SG.esc(titulo)}</h3>
                ${texto ? `<p>${SG.esc(texto)}</p>` : ''}${html}
                ${motivo ? `<div class="sg-campo"><label for="sg-dlg-motivo">${SG.esc(motivo.etiqueta || 'Motivo')}</label>
                    <textarea id="sg-dlg-motivo" class="sg-input" maxlength="${motivo.max || 200}" placeholder="${SG.esc(motivo.placeholder || '')}"></textarea>
                    <span class="sg-error-campo" id="sg-dlg-error" role="alert"></span></div>` : ''}
                <div class="sg-botones">
                    ${cancelar ? `<button type="button" class="sg-btn" data-r="no">${SG.esc(cancelar)}</button>` : ''}
                    <button type="button" class="sg-btn ${peligro ? 'peligro' : 'principal'}" data-r="si">${SG.esc(aceptar)}</button>
                </div>`;
            let resuelto = false;
            const fin = (v) => { if (!resuelto) { resuelto = true; resolver(v); } };
            const v = SG.ventana(cont, { alCerrar: () => fin(null), etiqueta: titulo });
            const campo = SG.$('#sg-dlg-motivo', cont);
            const err = SG.$('#sg-dlg-error', cont);
            const confirmar = () => {
                let m = '';
                if (campo) {
                    m = campo.value.trim();
                    if (motivo.obligatorio !== false && !m) {
                        campo.setAttribute('aria-invalid', 'true'); err.textContent = 'Escribí el motivo para poder continuar.'; campo.focus(); return;
                    }
                }
                fin({ motivo: m }); v.cerrar();
            };
            SG.$('[data-r="si"]', cont).addEventListener('click', confirmar);
            const no = SG.$('[data-r="no"]', cont); if (no) no.addEventListener('click', () => { fin(null); v.cerrar(); });
            if (campo) campo.addEventListener('input', () => { campo.removeAttribute('aria-invalid'); err.textContent = ''; });
            cont.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'BUTTON') { e.preventDefault(); confirmar(); } });
            setTimeout(() => { (campo || (peligro && no) || SG.$('[data-r="si"]', cont)).focus(); }, 30);
        });
    SG.avisoModal = (titulo, texto, icono = 'info') => SG.dialogo({ titulo, texto, icono, cancelar: null, aceptar: 'Entendido' });

    /* --------------------------------------------------- desplegable propio */
    let listaAbierta = null;
    function cerrarLista() {
        if (!listaAbierta) return;
        const { lista, boton, quitar } = listaAbierta;
        lista.remove(); boton.setAttribute('aria-expanded', 'false'); boton.removeAttribute('aria-activedescendant');
        window.removeEventListener('resize', quitar); window.removeEventListener('scroll', quitar, true);
        document.removeEventListener('mousedown', fueraDeLista, true);
        listaAbierta = null;
    }
    function fueraDeLista(e) {
        if (!listaAbierta) return;
        if (listaAbierta.lista.contains(e.target) || listaAbierta.boton.contains(e.target)) return;
        cerrarLista();
    }
    SG.select = (nativo) => {
        if (!nativo) return null;
        if (nativo._sg) { nativo._sg.refrescar(); return nativo._sg; }
        const shell = document.createElement('div'); shell.className = 'sg-select-shell';
        nativo.parentNode.insertBefore(shell, nativo); shell.appendChild(nativo);
        nativo.classList.add('sg-select-native'); nativo.tabIndex = -1; nativo.setAttribute('aria-hidden', 'true');
        const boton = document.createElement('button');
        boton.type = 'button'; boton.className = 'sg-select-button';
        boton.setAttribute('aria-haspopup', 'listbox'); boton.setAttribute('aria-expanded', 'false');
        boton.innerHTML = '<span class="sg-select-value"></span><span class="sg-select-arrow" aria-hidden="true"></span>';
        shell.appendChild(boton);
        const valor = boton.firstElementChild;
        const rotulo = nativo.id ? document.querySelector(`label[for="${nativo.id}"]`) : null;
        if (rotulo) {
            if (!rotulo.id) rotulo.id = `${nativo.id}-rotulo`;
            boton.setAttribute('aria-labelledby', rotulo.id);
            rotulo.addEventListener('click', (e) => { e.preventDefault(); boton.focus(); });
        }
        let resaltado = -1;
        const opciones = () => Array.from(nativo.options).filter((o) => !o.hidden);
        const pintar = () => {
            const o = nativo.options[nativo.selectedIndex];
            const vacio = !o || o.value === '';
            valor.textContent = o ? o.textContent : (nativo.dataset.placeholder || 'Elegí una opción');
            boton.classList.toggle('vacio', vacio);
            boton.disabled = nativo.disabled;
        };
        const colocar = (lista) => {
            const r = boton.getBoundingClientRect();
            const abajo = window.innerHeight - r.bottom - 12;
            const arriba = r.top - 12;
            const alto = Math.min(lista.scrollHeight, 300);
            const sube = abajo < Math.min(alto, 220) && arriba > abajo;
            lista.style.width = `${r.width}px`; lista.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - r.width - 8))}px`;
            lista.style.maxHeight = `${Math.max(120, Math.min(300, (sube ? arriba : abajo)))}px`;
            if (sube) { lista.style.top = ''; lista.style.bottom = `${window.innerHeight - r.top + 6}px`; }
            else { lista.style.bottom = ''; lista.style.top = `${r.bottom + 6}px`; }
        };
        const marcar = (i, scroll = true) => {
            if (!listaAbierta || listaAbierta.boton !== boton) return;
            const items = SG.$$('.sg-select-option', listaAbierta.lista);
            items.forEach((x, k) => x.classList.toggle('res', k === i));
            resaltado = i;
            if (items[i]) { boton.setAttribute('aria-activedescendant', items[i].id); if (scroll) items[i].scrollIntoView({ block: 'nearest' }); }
        };
        const elegir = (opt) => {
            if (!opt || opt.disabled) return;
            const cambio = nativo.value !== opt.value;
            nativo.value = opt.value; pintar(); cerrarLista(); boton.focus();
            if (cambio) nativo.dispatchEvent(new Event('change', { bubbles: true }));
        };
        const abrir = () => {
            if (nativo.disabled) return;
            cerrarLista();
            const ops = opciones();
            const lista = document.createElement('div');
            lista.className = 'sg-select-list'; lista.setAttribute('role', 'listbox');
            ops.forEach((o, k) => {
                const b = document.createElement('button');
                b.type = 'button'; b.className = 'sg-select-option'; b.id = `${nativo.id || 'sg'}-op-${k}`;
                b.setAttribute('role', 'option'); b.setAttribute('aria-selected', String(o.value === nativo.value)); b.disabled = o.disabled;
                b.textContent = o.textContent;
                b.addEventListener('mouseenter', () => marcar(k, false));
                b.addEventListener('click', () => elegir(o));
                lista.appendChild(b);
            });
            document.body.appendChild(lista);
            const quitar = () => colocar(lista);
            window.addEventListener('resize', quitar); window.addEventListener('scroll', quitar, true);
            document.addEventListener('mousedown', fueraDeLista, true);
            listaAbierta = { lista, boton, quitar };
            boton.setAttribute('aria-expanded', 'true');
            colocar(lista);
            marcar(Math.max(0, ops.findIndex((o) => o.value === nativo.value)));
        };
        boton.addEventListener('click', () => (listaAbierta && listaAbierta.boton === boton ? cerrarLista() : abrir()));
        boton.addEventListener('keydown', (e) => {
            const abierta = listaAbierta && listaAbierta.boton === boton;
            const ops = opciones();
            if (['ArrowDown', 'ArrowUp'].includes(e.key)) {
                e.preventDefault();
                if (!abierta) { abrir(); return; }
                marcar(Math.max(0, Math.min(ops.length - 1, resaltado + (e.key === 'ArrowDown' ? 1 : -1))));
            } else if (e.key === 'Home' && abierta) { e.preventDefault(); marcar(0); }
            else if (e.key === 'End' && abierta) { e.preventDefault(); marcar(ops.length - 1); }
            else if ((e.key === 'Enter' || e.key === ' ') && abierta) { e.preventDefault(); elegir(ops[resaltado]); }
            else if (e.key === 'Escape' && abierta) { e.preventDefault(); e.stopPropagation(); cerrarLista(); }
            else if (e.key === 'Tab' && abierta) cerrarLista();
        });
        nativo.addEventListener('change', pintar);
        new MutationObserver(pintar).observe(nativo, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled'] });
        pintar();
        nativo._sg = { refrescar: pintar, boton };
        return nativo._sg;
    };
    SG.selectsEn = (ctx = document) => SG.$$('select[data-sg-select]', ctx).forEach((s) => SG.select(s));
    /* Rellena un <select> (ya mejorado o no) con [{valor, texto}] y conserva la selección si sigue existiendo. */
    SG.llenarSelect = (sel, items, { vacio = null, valor = undefined } = {}) => {
        const actual = valor !== undefined ? valor : sel.value;
        sel.innerHTML = '';
        if (vacio !== null) sel.appendChild(new Option(vacio, ''));
        items.forEach((it) => sel.appendChild(new Option(it.texto, it.valor)));
        const existe = Array.from(sel.options).some((o) => o.value === String(actual));
        sel.value = existe ? String(actual) : (sel.options[0] ? sel.options[0].value : '');
        if (sel._sg) sel._sg.refrescar();
    };

    /* ------------------------------------------------- actualización periódica */
    /* Ejecuta fn ya y cada `ms`. Se detiene con la pestaña oculta y no se pisa a sí misma. */
    SG.sondeo = (fn, ms = 8000) => {
        let t = null, corriendo = false, activo = true;
        const vuelta = async () => {
            if (!activo) return;
            if (!document.hidden && !corriendo) { corriendo = true; try { await fn(); } catch { /* sigue */ } corriendo = false; }
            t = setTimeout(vuelta, ms);
        };
        document.addEventListener('visibilitychange', () => { if (!document.hidden && activo) { clearTimeout(t); vuelta(); } });
        vuelta();
        return { parar: () => { activo = false; clearTimeout(t); }, ahora: async () => { if (!corriendo) { corriendo = true; try { await fn(); } finally { corriendo = false; } } } };
    };

    /* ---------------------------------------------------- botón con espera */
    /* Deshabilita el botón mientras corre la tarea, para que no se envíe dos veces. */
    SG.conEspera = async (boton, tarea) => {
        if (boton) { if (boton.dataset.espera === '1') return undefined; boton.dataset.espera = '1'; boton.disabled = true; boton.dataset.txt = boton.innerHTML; boton.innerHTML = `<span class="sg-giro" aria-hidden="true"></span><span>Procesando…</span>`; }
        try { return await tarea(); }
        finally { if (boton) { boton.innerHTML = boton.dataset.txt; boton.disabled = false; delete boton.dataset.espera; } }
    };

    /* ------------------------------------------------------------ cabecera */
    /* Completa la cabecera común: enlace "Volver a mi panel" según el rol y el botón de salir. */
    SG.iniciarCabecera = () => {
        const volver = document.getElementById('sg-volver');
        if (volver) { volver.href = SG.panelDe(SG.rol()); }
        const salir = document.getElementById('sg-salir');
        if (salir) salir.addEventListener('click', SG.cerrarSesion);
        SG.$$('[data-ico]').forEach((e) => { e.innerHTML = SG.ico(e.dataset.ico); });
    };
    SG.cabeceraHtml = (titulo) => `
        <header class="sg-top">
            <div class="sg-top-izq"><a id="sg-volver" class="sg-btn chico" href="login.html">${SG.ico('volver')}<span>Volver a mi panel</span></a></div>
            <div class="sg-top-centro"><h1 class="logo-restaurante sg-brand-unified">SAVAGE<span>GRILL.</span></h1><div class="sg-role-unified">${SG.esc(titulo)}</div></div>
            <div class="sg-top-der"><div data-savage-theme="inline"></div>
                <button id="sg-salir" type="button" class="sg-logout-unificado">${SG.ico('salir')}<span>Cerrar sesión</span></button></div>
        </header>`;
})();
