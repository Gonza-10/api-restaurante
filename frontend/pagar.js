/* =========================================================================
   Savage Grill · Pantalla "Pagar" del cliente.
   - Entrar a Pagar toma el "gestor del pago": un solo celular de la mesa gestiona el pago a la vez
     (los demás ven que está ocupado; se libera solo a los 10 minutos, o con "Dejar de gestionar", o lo libera el mozo).
   - En mesas de Grupo de amigos se pregunta acá cómo se paga (cada uno lo que consumió / partes iguales).
   - Propina y medio de pago: todo efectivo, todo tarjeta, todo Mercado Pago, o combinando con un monto por medio.
     Efectivo y tarjeta quedan "al aire": los cobra y controla siempre el mozo. Mercado Pago se paga solo desde el celular.
   - La factura (nombre o razón social) se pregunta DESPUÉS de que la cuenta está paga.
   - La mesa no se cierra sola: la cierra el mozo.
   ========================================================================= */
(() => {
    'use strict';
    const { $, $$, esc } = SG;
    const D = SG.dinero;
    const $$$ = (v) => D(v, 'ARS');

    const numero = Number(sessionStorage.getItem('savage-mesa-numero'));
    const pin = sessionStorage.getItem('savage-mesa-pin');
    if (!numero || !pin) { location.replace('pin.html' + (new URLSearchParams(location.search).has('mp') ? location.search : '')); return; }
    $('#pg-mesa').textContent = String(numero);
    $$('[data-ico]').forEach((e) => { e.innerHTML = SG.ico(e.dataset.ico); });

    const leer = (k) => { try { return sessionStorage.getItem(k); } catch { return null; } };
    const guardar = (k, v) => { try { if (v == null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch { /* nada */ } };

    /* Identificador de este celular/pestaña para el bloqueo del pago (el back pide 8 a 64 letras, números, - o _). */
    function idDispositivo() {
        let v = leer('savage-dispositivo');
        if (!v || !/^[A-Za-z0-9_-]{8,64}$/.test(v)) { v = 'd' + SG.clave().replace(/-/g, '').slice(0, 20); guardar('savage-dispositivo', v); }
        return v;
    }
    const DISP = idDispositivo();
    const post = (ruta, extra = {}) => SG.api(ruta, { method: 'POST', body: { numero_mesa: numero, pin, dispositivo: DISP, ...extra }, auth: false });

    /* ---- Mercado Pago: en la computadora se abre en una pestaña nueva (esta queda esperando); en el celular se sigue en la misma
       pantalla para que el sistema abra la app de Mercado Pago. Se guarda un respaldo de la mesa (6 h) porque al volver desde la app
       el navegador puede abrir una pestaña sin sesión: así el cliente no pierde su mesa y puede pedir la factura. */
    const CLAVE_RESPALDO_MP = 'savage-mp-sesion';
    const esMovil = () => /Android|iPhone|iPad|iPod|Mobile|Opera Mini|IEMobile/i.test(navigator.userAgent || '')
        || (navigator.maxTouchPoints > 1 && /Macintosh/i.test(navigator.userAgent || ''));
    function respaldarMesaMp() {
        try {
            localStorage.setItem(CLAVE_RESPALDO_MP, JSON.stringify({ t: Date.now(), numero, pin, dispositivo: DISP,
                modalidad: leer('savage-mesa-modalidad'), comensal: leer('savage-comensal') }));
        } catch { /* nada */ }
    }
    function limpiarRespaldoMp() { try { localStorage.removeItem(CLAVE_RESPALDO_MP); } catch { /* nada */ } }
    /* Se abre ya, dentro del toque del cliente, para que el navegador no la bloquee; la dirección de Mercado Pago llega después. */
    function abrirPestanaMp() {
        if (esMovil()) return null;
        try {
            const w = window.open('about:blank', '_blank');
            if (w) { try { w.document.title = 'Mercado Pago'; w.document.body.style.cssText = 'font-family:sans-serif;padding:24px;background:#111;color:#eee'; w.document.body.textContent = 'Abriendo Mercado Pago…'; } catch { /* nada */ } }
            return w || null;
        } catch { return null; }
    }
    function irAMercadoPago(url, pestana) {
        respaldarMesaMp(); P.saliendoMp = true;
        if (pestana && !pestana.closed) {
            pestana.location.href = url; P.mpPestana = true;
            SG.aviso('Mercado Pago se abrió en otra pestaña. Cuando termines de pagar, volvé a esta pantalla para pedir tu factura.', 'info');
            return;
        }
        window.location.href = url;
    }
    function cerrarPestanaVacia(pestana) { try { if (pestana && !pestana.closed) pestana.close(); } catch { /* nada */ } }

    const esGrupal = () => !!(window.SGM && SGM.esGrupal());
    function nombreComensal() {
        try {
            const c = window.SGM && SGM.comensal();
            if (c && c.nombre) return String(c.nombre);
            const r = window.SGM && SGM.nombreRecordado && SGM.nombreRecordado();
            return (typeof r === 'string' ? r : (r && r.nombre)) || '';
        } catch { return ''; }
    }

    const METODOS = {
        efectivo: { txt: 'Efectivo', sub: 'Le pagás al mozo en la mesa', ico: 'efectivo' },
        tarjeta: { txt: 'Tarjeta', sub: 'El mozo te acerca el posnet', ico: 'tarjeta' },
        mercadopago: { txt: 'Mercado Pago', sub: 'Pagás desde tu celular', ico: 'mercadopago' }
    };
    const NOMBRE_METODO = { Efectivo: 'Efectivo', Tarjeta: 'Tarjeta', MercadoPago: 'Mercado Pago' };
    const ICO_METODO = { Efectivo: 'efectivo', Tarjeta: 'tarjeta', MercadoPago: 'mercadopago' };
    const CLAVES = Object.keys(METODOS);

    const retornoParams = new URLSearchParams(location.search);
    const P = {
        cuenta: null, cot: null,
        gestor: null, gestorNombre: '', soltado: false, saliendoMp: false,   // gestor: 'mio' | 'ocupado' | null (todavía no se sabe)
        division: null,                       // solo Grupo de amigos: 'consumo' | 'partes_iguales'
        propina: 0, propinaTxt: '',
        metodo: null,                         // 'efectivo' | 'tarjeta' | 'mercadopago' | 'combinar'
        combo: { efectivo: { on: false, txt: '' }, tarjeta: { on: false, txt: '' }, mercadopago: { on: false, txt: '' } },
        editarPlan: false, mpPestana: false,
        clave: null, firma: '', pendienteForm: false, detAbierto: false,
        retorno: retornoParams.get('mp') || null
    };
    if (P.retorno) { try { history.replaceState(null, '', location.pathname); } catch { /* nada */ } }

    const aviso = (tipo, icono, html, extra = '') => `<div class="sg-notice ${tipo}">${SG.ico(icono)}<div>${html}${extra}</div></div>`;
    const editando = (el) => !!(el && document.activeElement && el.contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));
    const saldoDe = () => SG.num(P.cuenta && P.cuenta.saldo);
    const centavos = (v) => Math.round(v * 100);
    const aPesos = (c) => (c / 100).toFixed(2);

    /* ---------------------------------------------------------------- carga */
    function armarEsqueleto() {
        $('#pg-main').innerHTML = `
            <div id="pg-estado" class="sg-apilado"></div>
            <div class="sg-box" id="pg-cuenta"></div>
            <div class="sg-box" id="pg-pagar" hidden></div>
            <div class="sg-box" id="pg-pagos" hidden></div>
            <div class="sg-box" id="pg-comp" hidden></div>`;
    }
    let armado = false;

    async function cargarCot() {
        const r = await SG.api('/cotizaciones', { auth: false });
        if (r.ok) P.cot = r.data;
    }
    const cotDe = (m) => { const c = ((P.cot && P.cot.cotizaciones) || []).find((x) => x.moneda === m); const v = c ? SG.num(c.valor) : 0; return v > 0 ? v : null; };

    function manejarError(r) {
        if ([401, 403, 404].includes(r.status) || (r.status === 409 && /sesi[oó]n|mesa/i.test(r.error))) {
            $('#pg-main').innerHTML = `<div class="sg-box"><div class="sg-vacio">${esc(r.error || 'Tu mesa ya no está activa.')}<div class="sg-botones" style="justify-content:center;margin-top:16px"><a class="sg-btn principal" href="pin.html" id="pg-reingreso">Ingresar con el PIN</a></div></div></div>`;
            $('#pg-reingreso').addEventListener('click', () => { guardar('savage-mesa-pin', null); guardar('savage-mesa-numero', null); });
            armado = false; return true;
        }
        return false;
    }

    /* Toma (o renueva) el bloqueo del pago. Se repite en cada vuelta de la actualización: mientras la pantalla está abierta
       el bloqueo se mantiene, y si estaba ocupado, apenas se libera lo toma este celular. */
    async function tomarGestor() {
        if (P.soltado) return;
        const r = await post('/cuenta/gestor', { nombre: nombreComensal() });
        if (r.ok) { P.gestor = 'mio'; P.gestorNombre = ''; return; }
        if (r.status === 409 && r.data && r.data.codigo === 'gestor_ocupado') {
            P.gestor = 'ocupado'; P.gestorNombre = (r.data.gestor && r.data.gestor.nombre) || 'Otro comensal';
        }
    }
    function bloqueado(r) {
        if (r.status === 409 && r.data && r.data.codigo === 'gestor_ocupado') {
            P.gestor = 'ocupado'; P.gestorNombre = (r.data.gestor && r.data.gestor.nombre) || 'Otro comensal'; P.firma = '';
            pintar(); SG.mal(r.error); return true;
        }
        return false;
    }

    async function cargar() {
        const gestorAntes = P.gestor;
        await tomarGestor();
        let r;
        const pen = P.cuenta && P.cuenta.pago_pendiente;
        if (pen && pen.metodo === 'MercadoPago') {
            r = await post('/cuenta/pagar/estado', { pago: pen.id });
            if (r.ok && r.data && r.data.cuenta) { r.data = r.data.cuenta; }
            if (!r.ok) r = await post('/cuenta');
        } else r = await post('/cuenta');
        if (!r.ok) {
            if (manejarError(r)) return;
            if (!P.cuenta) { $('#pg-main').innerHTML = `<div class="sg-box">${aviso('mal', 'alerta', esc(r.error))}</div>`; }
            return;
        }
        if (!armado) { armarEsqueleto(); armado = true; }
        P.cuenta = r.data;
        if (gestorAntes !== P.gestor) P.firma = '';
        pintar();
    }

    function pintar() {
        pintarEstado(); pintarCuenta(); pintarPagar(); pintarPagos(); pintarComprobante();
    }

    /* ------------------------------------------------------------- helpers del plan */
    const partesAire = (plan) => ((plan && plan.partes) || []).filter((p) => p.metodo === 'Efectivo' || p.metodo === 'Tarjeta');
    const textoAire = (plan) => partesAire(plan).map((p) => `${NOMBRE_METODO[p.metodo]} ${$$$(p.monto)}`).join(' + ');
    const hayPlanAire = (c) => c.estado_cuenta !== 'Pagada' && SG.num(c.saldo) > 0 && partesAire(c.plan_pago).length > 0;

    /* --------------------------------------------------------------- estado */
    function pintarEstado() {
        const c = P.cuenta; const a = [];
        const pen = c.pago_pendiente;
        const pagada = c.estado_cuenta === 'Pagada';
        const yoGestiono = P.gestor !== 'ocupado';
        if (pagada) {
            a.push(`<div class="sg-box"><div class="pg-gracias"><div class="sg-modal-icono">${SG.ico('check')}</div><h2>¡Gracias por tu visita!</h2>
                <p class="sg-nota" style="margin:0">Tu cuenta está paga. Ya podés retirarte cuando quieras. Si querés pedir algo más, pedile al mozo que abra una mesa nueva.</p></div></div>`);
        }
        if (P.gestor === 'ocupado' && !pagada) {
            a.push(aviso('aviso', 'candado', `<b>${esc(P.gestorNombre)} está gestionando el pago de la mesa.</b> Mientras tanto no se puede pagar desde este celular. Cuando termine o lo suelte, esta pantalla se habilita sola. Si no responde, pedile al mozo que lo libere.`));
        } else if (P.gestor === 'mio' && !pagada) {
            a.push(aviso('info', 'candado', '<b>Estás gestionando el pago de la mesa.</b> Mientras tengas esta pantalla abierta, los demás ven que lo estás haciendo vos. Si no vas a pagar ahora, soltalo para que otra persona pueda.',
                '<div class="sg-botones"><button type="button" class="sg-btn chico" data-act="soltar">Dejar de gestionar</button></div>'));
        }
        if (P.retorno === 'failure') a.push(aviso('mal', 'alerta', '<b>El pago no se completó.</b> No se te cobró nada. Podés intentarlo de nuevo o elegir otro método.'));
        else if (P.retorno && !pen && !pagada) a.push(aviso('info', 'reloj', '<b>Estamos confirmando tu pago con Mercado Pago.</b> En unos segundos se actualiza acá.'));
        if (pen && pen.metodo === 'MercadoPago') {
            const acciones = yoGestiono ? `<div class="sg-botones"><button type="button" class="sg-btn principal chico" data-act="continuar-mp">Continuar el pago</button>
                <button type="button" class="sg-btn chico" data-act="verificar-mp">Ya pagué, verificar</button>
                <button type="button" class="sg-btn peligro chico" data-act="cancelar-mp">Cancelar este pago</button></div>` : '';
            a.push(aviso('aviso', 'mercadopago', `<b>Hay un pago con Mercado Pago pendiente por ${$$$(pen.monto)}.</b> Si ya se pagó, se acredita solo en unos segundos.${P.mpPestana ? ' Mercado Pago está abierto en otra pestaña: cuando termines, volvé acá y esta pantalla se actualiza sola.' : ''}${yoGestiono ? ' Si no lo terminaste, podés continuar o cancelarlo.' : ''}`, acciones));
        }
        if (!pagada && c.pedidos_en_cocina > 0) {
            a.push(aviso('aviso', 'reloj', `<b>Todavía hay ${c.pedidos_en_cocina === 1 ? 'un pedido' : c.pedidos_en_cocina + ' pedidos'} en preparación.</b> Vas a poder pagar cuando estén listos.`));
        }
        if (hayPlanAire(c) && !pen) {
            a.push(aviso('ok', 'campana', `<b>Ya avisamos al mozo.</b> Se acerca a tu mesa a cobrar: ${esc(textoAire(c.plan_pago))}.`,
                yoGestiono && !P.editarPlan ? '<div class="sg-botones"><button type="button" class="sg-btn chico" data-act="cambiar-plan">Quiero cambiar cómo pago</button></div>' : ''));
        }
        $('#pg-estado').innerHTML = a.join('');
    }

    /* --------------------------------------------------------------- cuenta */
    function pintarCuenta() {
        const c = P.cuenta;
        const abierto = $('#pg-det') ? $('#pg-det').open : P.detAbierto;
        const total = SG.num(c.total), saldo = SG.num(c.saldo), pagado = Math.max(0, total - saldo);
        const eq = saldo > 0 ? ['USD', 'BRL', 'PYG'].map((m) => {
            const cot = cotDe(m); const v = cot ? saldo / cot : (c.equivalentes && c.equivalentes[m] != null && saldo === total ? SG.num(c.equivalentes[m]) : null);
            if (v == null) return '';
            return `<div class="sg-moneda mc-${m}"><div class="cod">${m} · ${SG.MONEDAS[m].corto}</div><div class="val">${D(v, m)}</div></div>`;
        }).join('') : '';
        const verPor = esGrupal() ? Object.entries(c.por_comensal || {}) : [];
        const renglones = (c.renglones || []).map((r) => `<div class="sg-renglon"><span class="cant">${esc(r.cantidad)}×</span><span>${esc(r.descripcion)}${esGrupal() && r.comensal ? `<small>${esc(r.comensal)}</small>` : ''}</span><span class="imp">${$$$(r.sub_total)}</span></div>`).join('');
        $('#pg-cuenta').innerHTML = `
            <div class="sg-box-cab"><h2>Tu cuenta</h2></div>
            <div class="sg-total-card"><div><small>${c.estado_cuenta === 'Pagada' ? 'Total pagado' : 'Falta pagar'}</small><strong>${$$$(c.estado_cuenta === 'Pagada' ? total : saldo)}</strong></div>
                <div style="text-align:right"><small>Total de la mesa</small><div style="font-weight:850;font-size:17px">${$$$(total)}</div></div></div>
            ${pagado > 0 && c.estado_cuenta !== 'Pagada' ? `<div class="sg-kv" style="margin-top:10px"><div><span>Ya se pagó</span><b>${$$$(pagado)}</b></div></div>` : ''}
            ${verPor.length > 1 ? `<div class="sg-subtitulo">Lo que consumió cada uno</div>
                <p class="sg-nota" style="margin-bottom:8px">Los platos compartidos se reparten en partes iguales entre quienes los comparten.</p>
                <div class="sg-kv">${verPor.map(([n, m]) => `<div><span>${esc(n)}</span><b>${$$$(m)}</b></div>`).join('')}</div>` : ''}
            ${eq ? `<div class="sg-subtitulo">El saldo en otras monedas</div>
                <p class="sg-nota" style="margin-bottom:10px">Es una referencia con la cotización del día. Si pagás en efectivo con otra moneda, el mozo te cobra al cambio de hoy.</p>
                <div class="sg-monedas tres">${eq}</div>` : ''}
            <details class="sg-det" id="pg-det" style="margin-top:16px" ${abierto ? 'open' : ''}><summary>Ver el detalle de lo consumido</summary><div>
                ${renglones || '<div class="sg-vacio">Todavía no hay consumos.</div>'}</div></details>`;
    }

    /* ---------------------------------------------------------------- pagar */
    function puedePagar(c) {
        return c.estado_cuenta !== 'Pagada' && SG.num(c.saldo) > 0 && !(c.pago_pendiente && c.pago_pendiente.metodo === 'MercadoPago')
            && P.gestor !== 'ocupado' && (!hayPlanAire(c) || P.editarPlan);
    }
    const grupalConDivision = (c) => esGrupal() && Object.keys(c.por_comensal || {}).length > 1;
    const modoPlan = (c) => (grupalConDivision(c) ? P.division : 'todo');

    function propinaElegida(base) {
        if (P.propina === 'otro') { const v = P.propinaTxt.trim() ? SG.parseMonto(P.propinaTxt) : '0'; return v == null ? null : SG.num(v); }
        return Math.round((base || 0) * P.propina) / 100;
    }

    /* Plan de pago según lo elegido: [{metodo, monto, propina}] en pesos con dos decimales. */
    function armarPlan() {
        const c = P.cuenta; const saldo = saldoDe();
        if (grupalConDivision(c) && !P.division) return { vacio: true };
        if (!P.metodo) return { vacio: true };
        const prop = propinaElegida(saldo);
        if (prop == null || prop < 0) return { error: 'La propina no es un número válido.' };
        const cs = centavos(saldo), cp = centavos(prop);
        if (P.metodo !== 'combinar') {
            return { partes: [{ metodo: P.metodo, monto: aPesos(cs), propina: aPesos(cp) }], total: saldo + prop, prop };
        }
        const elegidos = CLAVES.filter((k) => P.combo[k].on);
        if (!elegidos.length) return { error: 'Marcá al menos un medio de pago.' };
        let asignado = 0; const montos = {};
        for (const k of elegidos) {
            const v = P.combo[k].txt.trim() ? SG.parseMonto(P.combo[k].txt) : null;
            const m = v == null ? 0 : centavos(SG.num(v));
            if (m <= 0) return { error: `Indicá cuánto se paga con ${k === 'mercadopago' ? 'Mercado Pago' : METODOS[k].txt.toLowerCase()}.` };
            montos[k] = m; asignado += m;
        }
        if (asignado !== cs) {
            const dif = cs - asignado;
            return { error: dif > 0 ? `Falta asignar ${$$$(dif / 100)} de la cuenta.` : `Te pasaste ${$$$(-dif / 100)} del saldo.` };
        }
        // La propina se reparte en proporción a lo que se paga con cada medio; el último absorbe el redondeo.
        let resto = cp;
        const partes = elegidos.map((k, i) => {
            const p = i === elegidos.length - 1 ? resto : Math.round(cp * montos[k] / cs);
            resto -= p;
            return { metodo: k, monto: aPesos(montos[k]), propina: aPesos(p) };
        });
        return { partes, total: saldo + prop, prop };
    }

    function pintarPagar() {
        const box = $('#pg-pagar'); const c = P.cuenta;
        if (!puedePagar(c)) { box.hidden = true; box.innerHTML = ''; P.firma = ''; return; }
        box.hidden = false;
        const firma = `${c.estado_cuenta}|${c.saldo}|${P.editarPlan}|${c.pedidos_en_cocina}|${P.gestor}|${Object.keys(c.por_comensal || {}).join(',')}`;
        if (firma === P.firma && box.innerHTML) { resumen(); return; }
        if (editando(box)) { P.pendienteForm = true; return; }
        P.firma = firma; P.pendienteForm = false;
        armarPagar();
    }

    function cuantoLeToca(c) {
        const por = Object.entries(c.por_comensal || {});
        let filas;
        if (P.division === 'consumo') filas = por.map(([n, m]) => [n, SG.num(m)]);
        else {
            const cs = centavos(saldoDe()), n = por.length; const base = Math.floor(cs / n); const sobra = cs - base * n;
            filas = por.map(([nom], i) => [nom, (base + (i < sobra ? 1 : 0)) / 100]);
        }
        return `<div class="sg-kv" style="margin-top:12px">${filas.map(([n, m]) => `<div><span>${esc(n)}</span><b>${$$$(m)}</b></div>`).join('')}</div>
            <p class="sg-nota" style="margin:8px 0 0">Es una referencia para que se organicen. El pago se registra por medio de pago, no por persona.</p>`;
    }

    function armarPagar() {
        const box = $('#pg-pagar'); const c = P.cuenta;
        const pedirDivision = grupalConDivision(c);
        const listo = !pedirDivision || !!P.division;
        let html = `<div class="sg-box-cab"><h2>${P.editarPlan ? 'Cambiar cómo pagar' : 'Pagar la cuenta'}</h2></div>`;
        let n = 0;
        if (pedirDivision) {
            html += `<div class="pg-paso"><div class="sg-subtitulo">${++n}. ¿Cómo se paga la cuenta?</div>
                <div class="sg-segmentos"><button type="button" class="sg-chip ${P.division === 'consumo' ? 'activo' : ''}" data-div="consumo" aria-pressed="${P.division === 'consumo'}">Cada uno paga lo que consumió</button>
                <button type="button" class="sg-chip ${P.division === 'partes_iguales' ? 'activo' : ''}" data-div="partes_iguales" aria-pressed="${P.division === 'partes_iguales'}">Se divide en partes iguales</button></div>
                ${P.division ? cuantoLeToca(c) : ''}</div>`;
        }
        if (listo) {
            html += `<div class="pg-paso"><div class="sg-subtitulo">${++n}. Propina para el mozo (opcional)</div>
                <div class="sg-segmentos">${[[0, 'Sin propina'], [10, '10%'], [15, '15%'], ['otro', 'Otro monto']].map(([v, t]) => `<button type="button" class="sg-chip ${P.propina === v ? 'activo' : ''}" data-prop="${v}">${t}</button>`).join('')}</div>
                <input id="pg-prop" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="Monto de la propina en pesos" style="margin-top:8px" value="${esc(P.propinaTxt)}" ${P.propina === 'otro' ? '' : 'hidden'}></div>`;
            const cards = [...CLAVES, 'combinar'].map((k) => {
                const m = k === 'combinar' ? { txt: 'Combinar', sub: 'Parte con cada medio', ico: 'dividir' } : METODOS[k];
                return `<button type="button" class="pg-metodo ${P.metodo === k ? 'activo' : ''}" data-metodo="${k}" aria-pressed="${P.metodo === k}">${SG.ico(m.ico)}<span>${m.txt}</span><small>${m.sub}</small></button>`;
            }).join('');
            html += `<div class="pg-paso"><div class="sg-subtitulo">${++n}. ¿Con qué pagan?</div><div class="pg-metodos">${cards}</div>
                ${P.metodo === 'combinar' ? panelCombinar() : ''}
                ${P.metodo === 'efectivo' || P.metodo === 'tarjeta' ? `<p class="sg-nota" style="margin:12px 0 0">${P.metodo === 'efectivo'
                    ? 'Le avisamos al mozo y se acerca a tu mesa a cobrar en efectivo. Se puede pagar en pesos, dólares, reales o guaraníes.'
                    : 'Le avisamos al mozo y se acerca a tu mesa con el posnet para cobrar con tarjeta de crédito o débito.'}</p>` : ''}
                ${P.metodo === 'mercadopago' ? '<p class="sg-nota" style="margin:12px 0 0">Vas a pasar a la pantalla segura de Mercado Pago y después volvés acá automáticamente.</p>' : ''}</div>
                <div class="sg-vista" id="pg-resumen" aria-live="polite"></div>
                <button type="button" class="sg-btn principal" id="pg-confirmar" data-act="confirmar" style="width:100%;min-height:52px;font-size:15px;margin-top:14px" disabled><span id="pg-confirmar-txt">Elegí cómo pagar</span></button>
                <p class="sg-nota" style="margin:10px 0 0">El efectivo y la tarjeta siempre los cobra y controla el mozo. Al pagar con Mercado Pago, la mesa deja de recibir pedidos nuevos.</p>`;
        } else {
            html += '<p class="sg-nota" style="margin:14px 0 0">Elegí una opción para continuar.</p>';
        }
        box.innerHTML = html;
        resumen();
    }

    function panelCombinar() {
        const filas = CLAVES.map((k) => {
            const f = P.combo[k];
            return `<div class="pg-comb-fila">
                <label class="sg-check"><input type="checkbox" data-comb-on="${k}" ${f.on ? 'checked' : ''}><span>${METODOS[k].txt}</span></label>
                <input class="sg-input" data-comb-monto="${k}" inputmode="decimal" autocomplete="off" placeholder="Monto" aria-label="Monto con ${METODOS[k].txt}" value="${esc(f.txt)}" ${f.on ? '' : 'disabled'}>
                <button type="button" class="sg-btn chico" data-comb-resto="${k}" ${f.on ? '' : 'disabled'}>Lo que falta</button>
            </div>`;
        }).join('');
        return `<div class="pg-comb"><p class="sg-nota" style="margin:12px 0 8px">Marcá los medios que van a usar e indicá cuánto de la cuenta se paga con cada uno. La suma tiene que dar ${$$$(saldoDe())}.</p>${filas}</div>`;
    }

    function resumen() {
        const box = $('#pg-resumen'); if (!box) return;
        const btn = $('#pg-confirmar'), txt = $('#pg-confirmar-txt'); if (!btn || !txt) return;
        const estado = (ok, texto) => { btn.disabled = !ok; txt.textContent = texto; };
        const pl = armarPlan();
        if (pl.vacio) { box.innerHTML = ''; estado(false, 'Elegí cómo pagar'); return; }
        if (pl.error) { box.innerHTML = `<div><span>Revisá</span><b class="mal">${esc(pl.error)}</b></div>`; estado(false, 'Completá los datos'); return; }
        const filas = pl.partes.length > 1 ? pl.partes.map((p) => `<div><span>${METODOS[p.metodo].txt}</span><b>${$$$(SG.num(p.monto) + SG.num(p.propina))}</b></div>`).join('') : '';
        box.innerHTML = `<div><span>De la cuenta</span><b>${$$$(saldoDe())}</b></div>${pl.prop > 0 ? `<div><span>Propina</span><b>${$$$(pl.prop)}</b></div>` : ''}
            <div><span>Total a abonar</span><b style="color:var(--primary-orange)">${$$$(pl.total)}</b></div>${filas}`;
        const aire = pl.partes.some((p) => p.metodo !== 'mercadopago');
        const mp = pl.partes.some((p) => p.metodo === 'mercadopago');
        estado(true, aire ? (mp ? 'Avisar al mozo y pagar con Mercado Pago' : 'Avisar al mozo') : 'Pagar con Mercado Pago');
    }
    const NOMBRE_METODO_DE = { efectivo: 'Efectivo', tarjeta: 'Tarjeta', mercadopago: 'MercadoPago' };

    /* --------------------------------------------------------------- pagos */
    function pintarPagos() {
        const c = P.cuenta; const box = $('#pg-pagos');
        const lista = (c.pagos || []).filter((p) => ['Aprobado', 'Pendiente'].includes(p.estado));
        if (!lista.length) { box.hidden = true; box.innerHTML = ''; return; }
        box.hidden = false;
        box.innerHTML = `<div class="sg-box-cab"><h2>Pagos de la mesa</h2></div><div class="sg-lista">${lista.map((p) => `
            <div class="sg-item"><div class="izq"><span class="sg-icono-metodo">${SG.ico(ICO_METODO[p.metodo] || 'moneda')}</span>
                <div><strong>${esc(NOMBRE_METODO[p.metodo] || p.metodo)} <span class="sg-badge ${p.estado === 'Aprobado' ? 'ok' : 'aviso'}" style="margin-left:6px">${p.estado === 'Aprobado' ? 'Pagado' : 'Pendiente'}</span></strong>
                <small>${esc(SG.fechaHora(p.fecha_hora))}${SG.num(p.propina) > 0 ? ' · Propina ' + $$$(p.propina) : ''}</small></div></div>
                <span class="sg-monto">${$$$(p.monto)}</span></div>`).join('')}</div>`;
    }

    /* ------------------------------------------------- factura (después de pagar) */
    function pintarComprobante() {
        const c = P.cuenta; const box = $('#pg-comp'); const f = c.factura;
        if (c.estado_cuenta !== 'Pagada' || !f || f.estado === 'Anulada') { box.hidden = true; box.innerHTML = ''; return; }
        if (editando(box)) return;
        const ocupado = P.gestor === 'ocupado';
        box.hidden = false;
        box.innerHTML = `<div class="sg-box-cab"><h2>¿Necesitás factura?</h2></div>
            <p class="sg-nota">Si la necesitás, decinos a nombre de quién la emitimos. También podés descargar el comprobante en PDF con el detalle de la cuenta y los pagos.</p>
            ${ocupado ? aviso('aviso', 'candado', `${esc(P.gestorNombre)} está gestionando el pago de la mesa y es quien puede cargar la factura.`) : ''}
            <div class="sg-form">
                <label class="sg-check"><input type="checkbox" id="cp-qf" ${f.quiere_factura ? 'checked' : ''} ${ocupado ? 'disabled' : ''}><span>Necesito factura</span></label>
                <div class="sg-campo" id="cp-nom-w" ${f.quiere_factura ? '' : 'hidden'}><label for="cp-nom">Nombre o razón social</label>
                    <input id="cp-nom" class="sg-input" maxlength="100" placeholder="Tu nombre o la razón social de tu empresa" value="${esc(f.nombre_factura || '')}" ${ocupado ? 'disabled' : ''}></div>
                <div class="sg-botones"><button type="button" class="sg-btn" data-act="guardar-comp" ${ocupado ? 'disabled' : ''}>Guardar</button>
                    <button type="button" class="sg-btn principal" data-act="descargar" ${f.comprobante_disponible ? '' : 'disabled'}>${SG.ico('descargar')}<span>Descargar comprobante</span></button></div>
            </div>`;
        const qf = $('#cp-qf'); qf.addEventListener('change', () => { $('#cp-nom-w').hidden = !qf.checked; if (qf.checked) $('#cp-nom').focus(); });
    }

    /* -------------------------------------------------------------- acciones */
    function claveFija(body) {
        const h = JSON.stringify(body);
        if (!P.clave || P.clave.h !== h) P.clave = { h, v: SG.clave() };
        return P.clave.v;
    }

    async function confirmar(boton) {
        const pl = armarPlan();
        if (pl.vacio || pl.error) { SG.mal(pl.error || 'Elegí cómo pagar.'); return; }
        const c = P.cuenta; const saldo = saldoDe();
        const aire = pl.partes.filter((p) => p.metodo !== 'mercadopago');
        const mp = pl.partes.find((p) => p.metodo === 'mercadopago');
        const lineas = pl.partes.map((p) => `<div><span>${METODOS[p.metodo].txt}</span><b>${$$$(SG.num(p.monto) + SG.num(p.propina))}</b></div>`).join('');
        const ok = await SG.dialogo({
            titulo: mp && !aire.length ? 'Pagar con Mercado Pago' : 'Confirmar cómo pagan', icono: mp && !aire.length ? 'mercadopago' : 'campana',
            aceptar: mp ? 'Continuar' : 'Avisar al mozo',
            html: `<div class="sg-vista" style="margin-bottom:8px"><div><span>De la cuenta</span><b>${$$$(saldo)}</b></div>${pl.prop > 0 ? `<div><span>Propina</span><b>${$$$(pl.prop)}</b></div>` : ''}${lineas}<div><span>Total a abonar</span><b>${$$$(pl.total)}</b></div></div>
                <p>${aire.length ? 'Le avisamos al mozo para que se acerque a cobrar ' + esc(aire.map((p) => METODOS[p.metodo].txt.toLowerCase()).join(' y ')) + '. ' : ''}${mp ? 'Después pasás a Mercado Pago para completar ese pago. Al pagar, la mesa deja de recibir pedidos nuevos.' : ''}</p>`
        });
        if (!ok) return;
        const pestanaMp = mp ? abrirPestanaMp() : null;
        await SG.conEspera(boton, async () => {
            if (aire.length) {
                const r = await post('/solicitar-cuenta', {
                    metodo_pago: NOMBRE_METODO_DE[aire[0].metodo], nombre: nombreComensal(),
                    plan: { modo: modoPlan(c), partes: pl.partes }
                });
                if (!r.ok) { cerrarPestanaVacia(pestanaMp); if (!bloqueado(r)) SG.mal(r.error); return; }
                P.editarPlan = false; P.firma = '';
            }
            if (mp) {
                const body = {};
                if (centavos(SG.num(mp.monto)) !== centavos(saldo)) body.monto_cuenta = mp.monto;
                if (SG.num(mp.propina) > 0) body.propina = mp.propina;
                body.clave = claveFija({ ...body });
                const r = await post('/cuenta/pagar/mercadopago', body);
                if (!r.ok) {
                    cerrarPestanaVacia(pestanaMp);
                    if (!bloqueado(r)) SG.mal(r.error);
                    if (aire.length) await cargar();
                    return;
                }
                const pago = r.data.pago;
                if (!pago || !pago.url_pago) { cerrarPestanaVacia(pestanaMp); SG.mal('No se pudo abrir Mercado Pago. Probá de nuevo o pedile ayuda al mozo.'); if (aire.length) await cargar(); return; }
                guardar('savage-mp-pago', String(pago.id));
                irAMercadoPago(pago.url_pago, pestanaMp);
                if (P.mpPestana) await cargar();
                return;
            }
            SG.ok('Listo, avisamos al mozo.');
            await cargar();
        });
    }

    async function soltar(boton) {
        await SG.conEspera(boton, async () => {
            const r = await post('/cuenta/gestor/soltar');
            if (!r.ok) { SG.mal(r.error); return; }
            P.soltado = true; if (sondeo) sondeo.parar();
            location.href = 'catalogo.html';
        });
    }

    async function verificar(boton) {
        const pen = P.cuenta.pago_pendiente; if (!pen) return;
        await SG.conEspera(boton, async () => {
            const r = await post('/cuenta/pagar/estado', { pago: pen.id });
            if (!r.ok) { SG.mal(r.error); return; }
            P.cuenta = r.data.cuenta; P.firma = ''; pintar();
            if (r.data.aviso) SG.aviso('Mercado Pago no respondió en este momento. Probá de nuevo en unos segundos.', 'info');
            else if (P.cuenta.pago_pendiente) SG.aviso('El pago todavía no se acreditó. Si ya pagaste, esperá unos segundos.', 'info');
            else SG.ok('Pago confirmado.');
        });
    }
    async function cancelar(boton) {
        const pen = P.cuenta.pago_pendiente; if (!pen) return;
        const ok = await SG.dialogo({ titulo: 'Cancelar el pago pendiente', icono: 'alerta', peligro: true, aceptar: 'Cancelar el pago', cancelar: 'No, volver',
            texto: 'El link de Mercado Pago deja de servir y vas a poder elegir otra forma de pagar. Si ya pagaste, el sistema lo detecta y no lo cancela.' });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await post('/cuenta/pagar/cancelar', { pago: pen.id });
            if (!r.ok) { if (!bloqueado(r)) SG.mal(r.error); return; }
            P.cuenta = r.data.cuenta; P.firma = ''; P.retorno = null; P.mpPestana = false; limpiarRespaldoMp(); pintar(); SG.ok('Pago cancelado.');
        });
    }
    async function guardarComp(boton) {
        const qf = $('#cp-qf').checked, nombre = $('#cp-nom').value.trim();
        if (qf && !nombre) { SG.mal('Escribí el nombre o la razón social para la factura.'); $('#cp-nom').focus(); return; }
        await SG.conEspera(boton, async () => {
            const r = await post('/cuenta/factura', { quiere_factura: qf, nombre_factura: qf ? nombre : undefined });
            if (!r.ok) { if (!bloqueado(r)) SG.mal(r.error); return; }
            SG.ok(qf ? 'Guardamos tu pedido de factura.' : 'Quitamos el pedido de factura.');
            await cargar();
        });
    }
    async function descargar(boton) {
        await SG.conEspera(boton, async () => {
            let resp;
            try {
                resp = await fetch(SG.BASE + '/cuenta/comprobante', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ numero_mesa: numero, pin, descargar: true }) });
            } catch { SG.mal('No hay conexión con el sistema. Probá de nuevo.'); return; }
            if (!resp.ok) { let d = null; try { d = await resp.json(); } catch { /* sin cuerpo */ } SG.mal(SG.mensajeDe(d, resp.status)); return; }
            const blob = await resp.blob(); const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = `comprobante-mesa-${numero}.pdf`; document.body.appendChild(a); a.click(); a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 4000);
            SG.ok('Comprobante descargado.');
        });
    }

    /* --------------------------------------------------------------- eventos */
    const main = $('#pg-main');
    main.addEventListener('toggle', (e) => { if (e.target.id === 'pg-det') P.detAbierto = e.target.open; }, true);
    main.addEventListener('input', (e) => {
        if (e.target.id === 'pg-prop') { P.propinaTxt = e.target.value; resumen(); }
        if (e.target.dataset && e.target.dataset.combMonto) { P.combo[e.target.dataset.combMonto].txt = e.target.value; resumen(); }
        P.clave = null;
    });
    main.addEventListener('change', (e) => {
        const k = e.target.dataset && e.target.dataset.combOn;
        if (k) {
            P.combo[k].on = e.target.checked; P.clave = null;
            if (!e.target.checked) P.combo[k].txt = '';
            armarPagar();
            if (P.combo[k].on) { const i = $(`[data-comb-monto="${k}"]`); if (i) i.focus(); }
        }
    });
    main.addEventListener('focusout', () => {
        setTimeout(() => { if (P.pendienteForm && !editando($('#pg-pagar'))) { P.pendienteForm = false; pintarPagar(); } }, 60);
    });
    main.addEventListener('click', (e) => {
        const dv = e.target.closest('[data-div]');
        if (dv) { P.division = dv.dataset.div; P.clave = null; armarPagar(); return; }
        const m = e.target.closest('[data-metodo]');
        if (m) { P.metodo = m.dataset.metodo; P.clave = null; armarPagar(); return; }
        const pr = e.target.closest('[data-prop]');
        if (pr) { P.propina = pr.dataset.prop === 'otro' ? 'otro' : Number(pr.dataset.prop); P.clave = null; $$('[data-prop]').forEach((b) => b.classList.toggle('activo', b === pr)); $('#pg-prop').hidden = P.propina !== 'otro'; if (P.propina === 'otro') $('#pg-prop').focus(); resumen(); return; }
        const rest = e.target.closest('[data-comb-resto]');
        if (rest) {
            const k = rest.dataset.combResto; let otros = 0;
            CLAVES.forEach((x) => { if (x !== k && P.combo[x].on && P.combo[x].txt.trim()) { const v = SG.parseMonto(P.combo[x].txt); if (v != null) otros += centavos(SG.num(v)); } });
            const falta = Math.max(0, centavos(saldoDe()) - otros);
            P.combo[k].txt = SG.numero(falta / 100, 2); P.clave = null;
            const inp = $(`[data-comb-monto="${k}"]`); if (inp) inp.value = P.combo[k].txt; resumen(); return;
        }
        const b = e.target.closest('[data-act]'); if (!b) return;
        const a = b.dataset.act;
        if (a === 'confirmar') return confirmar(b);
        if (a === 'soltar') return soltar(b);
        if (a === 'verificar-mp') return verificar(b);
        if (a === 'cancelar-mp') return cancelar(b);
        if (a === 'continuar-mp') { const pen = P.cuenta.pago_pendiente; if (pen && pen.url_pago) irAMercadoPago(pen.url_pago, abrirPestanaMp()); else SG.mal('No se encontró el link de pago. Cancelá este pago y empezá de nuevo.'); return; }
        if (a === 'cambiar-plan') { P.editarPlan = true; P.firma = ''; pintar(); return; }
        if (a === 'guardar-comp') return guardarComp(b);
        if (a === 'descargar') return descargar(b);
    });

    /* Al salir de la pantalla se suelta el bloqueo (salvo que se vaya a Mercado Pago a pagar: ahí se conserva hasta volver). */
    window.addEventListener('pagehide', () => {
        if (P.saliendoMp || P.soltado || P.gestor !== 'mio') return;
        try {
            fetch(SG.BASE + '/cuenta/gestor/soltar', { method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ numero_mesa: numero, pin, dispositivo: DISP }) });
        } catch { /* nada */ }
    });

    /* --------------------------------------------------------------- arranque */
    cargarCot();
    const sondeo = SG.sondeo(async () => { await cargar(); if (P.cuenta && P.cuenta.estado_cuenta === 'Pagada') { P.mpPestana = false; limpiarRespaldoMp(); } if (P.retorno && P.cuenta && !P.cuenta.pago_pendiente && P.cuenta.estado_cuenta === 'Pagada') P.retorno = null; }, 5000);
    setInterval(() => { if (!document.hidden) cargarCot(); }, 120000);
})();
