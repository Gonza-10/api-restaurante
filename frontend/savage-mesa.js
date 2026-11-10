/* =========================================================================
   Savage Grill · Mesa del cliente
   Lo comparten pin.html, catalogo.html y carrito.html:
   - tipo de mesa (Familiar / Grupo de amigos) y nombre del comensal;
   - PIN nuevo (lo da el mozo) sin perder el pedido en curso;
   - "Seguridad de la mesa": pedir un PIN nuevo cuando alguien se va.
   No depende del resto de los scripts de la página.
   ========================================================================= */
(() => {
    'use strict';
    if (window.SGM) return;
    const SGM = (window.SGM = {});
    const original = window.fetch.bind(window);

    const BASE = (() => {
        const base = String(window.SAVAGE_CONFIG?.API_BASE_URL || '/api/v1').replace(/\/+$/, '');
        if (location.protocol === 'file:' && !/^https?:\/\//i.test(base)) return 'http://localhost:8080/api/v1';
        return base;
    })();
    SGM.base = BASE;

    /* ------------------------------------------------------------ almacenamiento */
    const K = {
        numero: 'savage-mesa-numero', pin: 'savage-mesa-pin', modalidad: 'savage-mesa-modalidad',
        comensal: 'savage-comensal', lista: 'savage-comensales-lista',
    };
    const leer = (k) => { try { return sessionStorage.getItem(k); } catch (_) { return null; } };
    const guardar = (k, v) => { try { sessionStorage.setItem(k, v); } catch (_) { /* nada */ } };
    const borrar = (k) => { try { sessionStorage.removeItem(k); } catch (_) { /* nada */ } };
    const json = (k, def) => { try { const v = JSON.parse(leer(k)); return v ?? def; } catch (_) { return def; } };

    SGM.numero = () => Number(leer(K.numero)) || null;
    SGM.pin = () => leer(K.pin) || '';
    SGM.modalidad = () => leer(K.modalidad) || '';
    SGM.esGrupal = () => SGM.modalidad() === 'Grupal';
    SGM.comensal = () => { const c = json(K.comensal, null); return c && c.id ? c : null; };
    /* Comensales activos de la mesa [{id, nombre}] según la última consulta. */
    SGM.comensales = () => { const l = json(K.lista, []); return Array.isArray(l) ? l : []; };
    SGM.sincronizar = (datosMesa) => {
        if (datosMesa && typeof datosMesa.modalidad === 'string' && datosMesa.modalidad) guardar(K.modalidad, datosMesa.modalidad);
    };
    SGM.salir = () => { try { sessionStorage.clear(); } catch (_) { /* nada */ } location.href = 'pin.html'; };

    /* Nombre usado la última vez en esta mesa (para no volver a escribirlo si el PIN cambia o se cierra la pestaña). */
    const CLAVE_RECUERDO = 'savage-ultimo-nombre';
    function recordarNombre(nombre) {
        try { localStorage.setItem(CLAVE_RECUERDO, JSON.stringify({ mesa: SGM.numero(), nombre, ts: Date.now() })); } catch (_) { /* nada */ }
    }
    SGM.nombreRecordado = () => {
        try {
            const r = JSON.parse(localStorage.getItem(CLAVE_RECUERDO));
            if (r && r.mesa === SGM.numero() && Date.now() - r.ts < 6 * 3600 * 1000) return String(r.nombre || '');
        } catch (_) { /* nada */ }
        return '';
    };

    /* ----------------------------------------------------------------------- API */
    SGM.llamar = async (ruta, cuerpo) => {
        try {
            const resp = await original(`${BASE}/${ruta}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo), cache: 'no-store',
            });
            let data = {};
            try { data = await resp.json(); } catch (_) { /* sin cuerpo */ }
            return { ok: resp.ok, status: resp.status, data };
        } catch (_) {
            return { ok: false, status: 0, data: { error: 'No hay conexión con el servidor. Probá de nuevo.' } };
        }
    };
    const credenciales = () => ({ numero_mesa: SGM.numero(), pin: SGM.pin() });

    function guardarLista(comensales) {
        const activos = (Array.isArray(comensales) ? comensales : []).filter((c) => c.estado !== 'Retirado')
            .map((c) => ({ id: c.id, nombre: c.nombre }));
        guardar(K.lista, JSON.stringify(activos));
    }

    /* Registra a este dispositivo en la mesa con su nombre. Devuelve {ok, situacion, data}. */
    SGM.registrar = async (nombre) => {
        const r = await SGM.llamar('mesa/comensales', { ...credenciales(), nombre });
        if (r.ok && r.data.comensal) {
            guardar(K.comensal, JSON.stringify({ id: r.data.comensal.id, nombre: r.data.comensal.nombre }));
            guardarLista(r.data.comensales);
            recordarNombre(r.data.comensal.nombre);
            if (r.data.modalidad) guardar(K.modalidad, r.data.modalidad);
        }
        return { ok: r.ok, situacion: r.data.situacion, data: r.data, status: r.status };
    };

    SGM.refrescar = async () => {
        if (!SGM.numero() || !SGM.pin()) return null;
        const r = await SGM.llamar('mesa/comensales/estado', credenciales());
        if (r.ok) { guardarLista(r.data.comensales); return r.data; }
        return null;
    };

    /* En una mesa Grupo de amigos nadie ve el menú sin haber puesto su nombre. */
    SGM.exigirComensal = () => {
        if (SGM.esGrupal() && !SGM.comensal()) { location.replace('pin.html?paso=nombre'); return false; }
        return true;
    };

    /* ------------------------------------------------------------------ interfaz */
    const css = document.createElement('style');
    css.textContent = `
    .sgm-overlay{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,.86);backdrop-filter:blur(8px)}
    .sgm-card{width:min(420px,100%);max-height:92vh;overflow-y:auto;padding:26px;border-radius:18px;border:1px solid var(--glass-border,rgba(255,255,255,.12));background:var(--surface,#111);color:var(--text-main,#fff);box-shadow:0 20px 60px rgba(0,0,0,.5)}
    .sgm-card h2{margin:0 0 8px;font-size:20px;line-height:1.25;color:var(--text-main,#fff)}
    .sgm-card p{margin:0 0 14px;font-size:14px;line-height:1.5;color:var(--text-muted,#9aa0a6)}
    .sgm-pin{width:100%;box-sizing:border-box;text-align:center;letter-spacing:.5em;font-size:30px;font-weight:900;padding:12px 8px;border-radius:12px;border:1px solid var(--glass-border,rgba(255,255,255,.2));background:rgba(255,255,255,.05);color:var(--text-main,#fff)}
    .sgm-pin:focus{outline:2px solid var(--primary-orange,#ff7a00);outline-offset:1px}
    .sgm-err{min-height:18px;margin:8px 0 0;font-size:13px;font-weight:700;color:#e74c3c}
    .sgm-btn{width:100%;margin-top:12px;padding:14px;border-radius:12px;border:1px solid transparent;font:inherit;font-size:15px;font-weight:800;cursor:pointer}
    .sgm-btn.principal{background:var(--primary-orange,#ff7a00);color:#fff}
    .sgm-btn.sec{background:transparent;color:var(--text-muted,#9aa0a6);border-color:var(--glass-border,rgba(255,255,255,.18))}
    .sgm-btn[disabled]{opacity:.6;cursor:wait}
    .sgm-lista{display:grid;gap:8px;margin:4px 0 6px}
    .sgm-op{display:flex;gap:10px;align-items:center;padding:11px 13px;border-radius:12px;border:1px solid var(--glass-border,rgba(255,255,255,.14));cursor:pointer;font-size:14px;font-weight:700}
    .sgm-op input{width:18px;height:18px;accent-color:var(--primary-orange,#ff7a00)}
    .sgm-op:has(input:checked){border-color:var(--primary-orange,#ff7a00);background:rgba(255,122,0,.1)}
    .sgm-fila{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--glass-border,rgba(255,255,255,.1));font-size:14px}
    .sgm-fila span:first-child{color:var(--text-muted,#9aa0a6)}
    .sgm-fila strong{text-align:right;overflow-wrap:anywhere}
    .sgm-link{margin-top:14px;width:100%;padding:12px;border-radius:12px;border:1px solid var(--glass-border,rgba(255,255,255,.18));background:transparent;color:var(--text-main,#fff);font:inherit;font-size:14px;font-weight:800;cursor:pointer}
    .sgm-link:hover{border-color:var(--primary-orange,#ff7a00);color:var(--primary-orange,#ff7a00)}
    `;
    document.head.appendChild(css);

    function el(html) { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; }
    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    /* ------------------------------------------------------- PIN nuevo (lo da el mozo) */
    SGM.pedirPinNuevo = (mensaje) => {
        if (document.getElementById('sgm-pin-nuevo')) return;
        const modal = el(`<div class="sgm-overlay" id="sgm-pin-nuevo" role="dialog" aria-modal="true" aria-labelledby="sgm-pn-t">
            <form class="sgm-card" novalidate>
                <h2 id="sgm-pn-t">El PIN de la mesa cambió</h2>
                <p>${esc(mensaje || 'Pedile el PIN nuevo al mozo e ingresalo acá. No perdés lo que ya pediste ni lo que tenés en el carrito.')}</p>
                <input class="sgm-pin" id="sgm-pn-in" type="text" inputmode="numeric" maxlength="4" autocomplete="off" aria-label="PIN nuevo de la mesa" placeholder="····">
                <p class="sgm-err" id="sgm-pn-err" role="alert"></p>
                <button class="sgm-btn principal" type="submit">Continuar</button>
                <button class="sgm-btn sec" type="button" id="sgm-pn-salir">Salir de la mesa</button>
            </form></div>`);
        document.body.appendChild(modal);
        const input = modal.querySelector('#sgm-pn-in');
        const err = modal.querySelector('#sgm-pn-err');
        const boton = modal.querySelector('button[type=submit]');
        input.addEventListener('input', () => { input.value = input.value.replace(/\D/g, '').slice(0, 4); });
        modal.querySelector('#sgm-pn-salir').addEventListener('click', SGM.salir);
        setTimeout(() => input.focus(), 40);
        modal.querySelector('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            err.textContent = '';
            const pin = input.value.trim();
            if (!/^\d{4}$/.test(pin)) { err.textContent = 'El PIN tiene 4 dígitos.'; return; }
            boton.disabled = true;
            const r = await SGM.llamar('acceso-mesa', { pin });
            if (!r.ok) {
                boton.disabled = false;
                err.textContent = r.data.codigo === 'pin_cambiado' ? 'Ese PIN ya no es el vigente. Pedile el actual al mozo.' : (r.data.error || 'PIN incorrecto.');
                return;
            }
            if (Number(r.data.numero_mesa) !== SGM.numero()) { boton.disabled = false; err.textContent = 'Ese PIN es de otra mesa.'; return; }
            guardar(K.pin, pin);
            SGM.sincronizar(r.data);
            if (SGM.esGrupal()) {
                const nombre = (SGM.comensal() || {}).nombre || SGM.nombreRecordado();
                if (!nombre) { borrar(K.comensal); location.replace('pin.html?paso=nombre'); return; }
                const reg = await SGM.registrar(nombre);
                if (!reg.ok) { boton.disabled = false; err.textContent = reg.data.error || 'No pudimos volver a registrarte en la mesa.'; return; }
            }
            location.reload();
        });
    };

    /* ----------------------------------------------- Seguridad: pedir un PIN nuevo */
    SGM.abrirSeguridad = async () => {
        if (document.getElementById('sgm-seguridad')) return;
        const modal = el(`<div class="sgm-overlay" id="sgm-seguridad" role="dialog" aria-modal="true" aria-labelledby="sgm-sg-t">
            <div class="sgm-card">
                <h2 id="sgm-sg-t">Seguridad de la mesa</h2>
                <p>Si alguien se fue y no querés que siga pidiendo, pedí un PIN nuevo. El mozo te lo da en persona y el PIN anterior deja de funcionar.</p>
                <div id="sgm-sg-lista"></div>
                <p class="sgm-err" id="sgm-sg-err" role="alert"></p>
                <button class="sgm-btn principal" type="button" id="sgm-sg-ok">Pedir PIN nuevo al mozo</button>
                <button class="sgm-btn sec" type="button" id="sgm-sg-cerrar">Cancelar</button>
            </div></div>`);
        document.body.appendChild(modal);
        const cerrar = () => modal.remove();
        modal.querySelector('#sgm-sg-cerrar').addEventListener('click', cerrar);
        modal.addEventListener('mousedown', (e) => { if (e.target === modal) cerrar(); });
        const lista = modal.querySelector('#sgm-sg-lista');
        const yo = SGM.comensal();
        if (SGM.esGrupal()) {
            await SGM.refrescar();
            const otros = SGM.comensales().filter((c) => !yo || c.id !== yo.id);
            if (otros.length) {
                lista.innerHTML = `<p style="margin-bottom:8px;color:var(--text-main,#fff);font-weight:800">¿Quién se fue?</p>
                    <div class="sgm-lista">${otros.map((c) => `<label class="sgm-op"><input type="checkbox" value="${Number(c.id)}"><span>${esc(c.nombre)}</span></label>`).join('')}</div>
                    <p style="font-size:12.5px">Lo que ya empezó a prepararse se mantiene; los pedidos de quien se fue que todavía no se empezaron a preparar se cancelan y se devuelve el stock. Si nadie se fue, no marques a nadie: no se cancela nada.</p>`;
            }
        }
        const err = modal.querySelector('#sgm-sg-err');
        const boton = modal.querySelector('#sgm-sg-ok');
        boton.addEventListener('click', async () => {
            err.textContent = '';
            boton.disabled = true;
            const retirados = [...lista.querySelectorAll('input:checked')].map((i) => Number(i.value));
            const cuerpo = { ...credenciales(), retirados };
            if (yo) cuerpo.id_comensal = yo.id;
            const r = await SGM.llamar('mesa/regenerar-pin', cuerpo);
            boton.disabled = false;
            if (!r.ok) { err.textContent = r.data.error || 'No pudimos pedir el PIN nuevo.'; return; }
            cerrar();
            SGM.pedirPinNuevo('Avisamos al mozo: te va a dar el PIN nuevo. Hasta entonces nadie puede pedir con el PIN anterior. Cuando lo tengas, ingresalo acá.');
        });
    };

    /* ------------------------------------------------ resumen dentro del modal "Mesa" */
    SGM.decorarModalMesa = async (contenedor) => {
        if (!contenedor) return;
        let extra = contenedor.querySelector('#sgm-extra');
        if (!extra) { extra = document.createElement('div'); extra.id = 'sgm-extra'; contenedor.appendChild(extra); }
        const pintar = () => {
            const yo = SGM.comensal();
            const filas = [`<div class="sgm-fila"><span>Tipo de mesa</span><strong>${SGM.esGrupal() ? 'Grupo de amigos' : 'Familiar'}</strong></div>`];
            if (SGM.esGrupal()) {
                filas.push(`<div class="sgm-fila"><span>Tu nombre</span><strong>${esc(yo ? yo.nombre : '—')}</strong></div>`);
                const otros = SGM.comensales().filter((c) => !yo || c.id !== yo.id).map((c) => esc(c.nombre));
                filas.push(`<div class="sgm-fila"><span>En la mesa</span><strong>${otros.length ? otros.join(', ') : 'Nadie más todavía'}</strong></div>`);
            }
            extra.innerHTML = filas.join('') + '<button type="button" class="sgm-link" id="sgm-abrir-seg">Seguridad de la mesa</button>';
            extra.querySelector('#sgm-abrir-seg').addEventListener('click', () => {
                const m = document.getElementById('modal-mesa'); if (m) m.style.display = 'none';
                SGM.abrirSeguridad();
            });
        };
        pintar();
        if (SGM.esGrupal()) { await SGM.refrescar(); pintar(); }
    };

    /* ------------------- Respuestas del servidor que cambian el rumbo (cualquier fetch de la página) */
    window.fetch = async (...args) => {
        const resp = await original(...args);
        try {
            if (SGM.numero() && (resp.status === 403 || resp.status === 409) && String(args[0] && args[0].url || args[0]).startsWith(BASE)) {
                const d = await resp.clone().json();
                if (d && (d.codigo === 'pin_cambiado' || d.codigo === 'comensal_retirado')) SGM.pedirPinNuevo(d.error);
                else if (d && (d.codigo === 'comensal_requerido' || d.codigo === 'comensal_desconocido')) {
                    borrar(K.comensal);
                    location.replace('pin.html?paso=nombre');
                }
            }
        } catch (_) { /* respuesta sin JSON: no hay nada que interpretar */ }
        return resp;
    };
})();
