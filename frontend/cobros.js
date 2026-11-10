/* =========================================================================
   Savage Grill · Cobros del salón — Mesas y cobros + Propinas
   (la caja, las cotizaciones, la auditoría y las anulaciones están en cobros-caja.js)
   ========================================================================= */
(() => {
    'use strict';
    if (!window.SG || !SG.exigirRol(['Mozo', 'Admin', 'Gerente'])) return;
    SG.iniciarCabecera();

    const { $, $$, esc } = SG;
    const D = SG.dinero;
    const AG = SG.esAdminGerente();
    const COB = (window.COB = {});
    const S = (COB.S = {
        tab: 'mesas', sesiones: [], sel: null, cuenta: null, cot: null, caja: null,
        buscar: '', metodo: null, piden: null, clave: null, detAbierto: false, pendienteForm: false
    });

    /* ------------------------------------------------------------ utilidades */
    const METODOS = {
        Efectivo: { txt: 'Efectivo', ico: 'efectivo' },
        Tarjeta: { txt: 'Tarjeta', ico: 'tarjeta' },
        MercadoPago: { txt: 'Mercado Pago', ico: 'mercadopago' }
    };
    const SOLICITADO = { efectivo: 'Efectivo', tarjeta: 'Tarjeta', mercadopago: 'MercadoPago' };
    COB.METODOS = METODOS;
    const ESTADO_PAGO = {
        Aprobado: ['ok', 'Cobrado'], Pendiente: ['aviso', 'Pendiente'], Anulado: ['mal', 'Anulado'],
        Cancelado: ['neutro', 'Cancelado'], Expirado: ['neutro', 'Vencido'], Rechazado: ['mal', 'Rechazado']
    };
    const aviso = (tipo, icono, html, extra = '') =>
        `<div class="sg-notice ${tipo}">${SG.ico(icono)}<div>${html}${extra}</div></div>`;
    COB.aviso = aviso;
    const cent = (v) => Math.round(SG.num(v) * 100);
    const deCent = (c) => c / 100;
    const moneda$ = (v) => D(v, 'ARS');

    COB.cotDe = (m) => {
        if (m === 'ARS') return 1;
        const c = ((S.cot && S.cot.cotizaciones) || []).find((x) => x.moneda === m);
        const v = c ? SG.num(c.valor) : 0;
        return v > 0 ? v : null;
    };
    const cotDe = COB.cotDe;

    /* --------------------------------------------------------------- pestañas */
    const TABS = [
        { id: 'mesas', txt: 'Mesas y cobros' },
        { id: 'propinas', txt: 'Propinas' },
        { id: 'caja', txt: 'Caja y registros', ag: true },
        { id: 'anular', txt: 'Anulaciones', ag: true }
    ].filter((t) => !t.ag || AG);

    function armarPestanas() {
        const nav = $('#tabs');
        nav.innerHTML = TABS.map((t) => `<button type="button" class="sg-tab" role="tab" data-tab="${t.id}" id="tab-${t.id}" aria-controls="p-${t.id}">${esc(t.txt)}</button>`).join('');
        nav.addEventListener('click', (e) => { const b = e.target.closest('[data-tab]'); if (b) irA(b.dataset.tab); });
        nav.addEventListener('keydown', (e) => {
            if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
            const i = TABS.findIndex((t) => t.id === S.tab);
            const n = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length];
            irA(n.id); $('#tab-' + n.id).focus();
        });
    }
    function irA(id) {
        if (!TABS.some((t) => t.id === id)) id = 'mesas';
        S.tab = id;
        TABS.forEach((t) => { $('#p-' + t.id).hidden = t.id !== id; });
        $$('.sg-tab', $('#tabs')).forEach((b) => {
            const on = b.dataset.tab === id;
            b.classList.toggle('activa', on); b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1;
        });
        try { history.replaceState(null, '', '#' + id); } catch { /* nada */ }
        if (id === 'propinas') cargarPropinas();
        if (id === 'caja' && COB.cargarCaja) COB.cargarCaja();
        if (id === 'anular' && COB.cargarAnulaciones) COB.cargarAnulaciones();
    }
    COB.irA = irA;

    /* ------------------------------------------------------------ cotizaciones */
    COB.cargarCotizaciones = async () => {
        const r = await SG.api('/cotizaciones');
        if (r.ok) { S.cot = r.data; if (COB.pintarCot) COB.pintarCot(); if (S.cuenta) { pintarResumen(S.cuenta); recalcularEfectivo(); } }
        return r;
    };

    /* -------------------------------------------------------------- caja (estado) */
    async function cargarEstadoCaja() {
        const r = await SG.api('/caja/actual');
        if (r.ok) S.caja = r.data;
    }
    COB.cargarEstadoCaja = cargarEstadoCaja;

    /* ----------------------------------------------------------- lista de mesas */
    async function cargarSesiones() {
        const r = await SG.api('/sesiones-mesa?estado=abierto');
        if (!r.ok) {
            if (!S.sesiones.length) $('#m-lista').innerHTML = aviso('mal', 'alerta', esc(r.error || 'No se pudieron cargar las mesas.'));
            return;
        }
        const lista = Array.isArray(r.data) ? r.data : (r.data && r.data.results) || [];
        avisarNuevas(lista);
        S.sesiones = lista;
        pintarLista();
        if (S.sel && !lista.some((s) => s.id === S.sel)) {
            S.sel = null; S.cuenta = null;
            pintarVacio('La mesa que estabas mirando ya se cerró. Elegí otra de la lista.');
        }
    }
    function avisarNuevas(lista) {
        const ahora = new Set(lista.filter((s) => s.solicita_cuenta).map((s) => s.id));
        if (S.piden) {
            lista.filter((s) => ahora.has(s.id) && !S.piden.has(s.id)).forEach((s) => {
                const m = SOLICITADO[s.metodo_pago_solicitado];
                SG.aviso(`La mesa ${s.numero_mesa} pidió la cuenta${m ? ` y quiere pagar con ${METODOS[m].txt.toLowerCase()}` : ''}.`, 'info', 9000);
            });
        }
        S.piden = ahora;
    }
    function pintarLista() {
        const q = S.buscar.trim().toLowerCase();
        let items = S.sesiones.slice().sort((a, b) => (Number(b.solicita_cuenta) - Number(a.solicita_cuenta)) || (a.numero_mesa - b.numero_mesa));
        if (q) items = items.filter((s) => String(s.numero_mesa) === q || String(s.id).includes(q) || (s.mozo_nombre || '').toLowerCase().includes(q));
        $('#m-cont').textContent = String(S.sesiones.length);
        const cont = $('#m-lista');
        const foco = document.activeElement && cont.contains(document.activeElement) ? document.activeElement.dataset.id : null;
        if (!items.length) {
            cont.innerHTML = `<div class="sg-vacio">${S.sesiones.length ? 'No hay mesas que coincidan con la búsqueda.' : 'No hay mesas abiertas en este momento.'}</div>`;
            return;
        }
        cont.innerHTML = items.map((s) => {
            const m = SOLICITADO[s.metodo_pago_solicitado];
            const pide = s.solicita_cuenta
                ? `<span class="sg-badge aviso">${SG.ico('campana').replace('<svg', '<svg width="12" height="12"')}Pide la cuenta${m ? ` · ${esc(METODOS[m].txt)}` : ''}</span>` : '';
            return `<button type="button" class="sg-mesa ${s.id === S.sel ? 'elegida' : ''} ${s.solicita_cuenta ? 'pide' : ''}" data-id="${s.id}" aria-pressed="${s.id === S.sel}">
                <div class="sg-mesa-cab"><span class="sg-mesa-num">Mesa ${esc(s.numero_mesa)}</span>${pide}</div>
                <small>Sesión n.° ${s.id} · ${esc(s.mozo_nombre || '')}</small>
                <small>Consumo ${moneda$(s.total)} · abierta ${esc(SG.hace(s.fecha_hora_apertura) || 'recién')}</small>
            </button>`;
        }).join('');
        if (foco) { const b = cont.querySelector(`[data-id="${foco}"]`); if (b) b.focus(); }
    }

    /* -------------------------------------------------------------- detalle */
    function pintarVacio(texto) {
        $('#m-detalle').innerHTML = `<div class="sg-box"><div class="sg-vacio">${SG.ico('mesa').replace('<svg', '<svg width="34" height="34" style="opacity:.5;display:block;margin:0 auto 10px"')}${esc(texto || 'Elegí una mesa de la lista para ver su cuenta y registrar cobros.')}</div></div>`;
    }
    function armarDetalle() {
        $('#m-detalle').innerHTML = `
            <div class="sg-box" id="d-cab"></div>
            <div class="sg-apilado" id="d-avisos"></div>
            <div class="sg-box" id="d-cuenta"></div>
            <div class="sg-box" id="d-cobro" hidden></div>
            <div class="sg-box" id="d-pagos"></div>
            <details class="sg-det" id="d-extra"><summary>Comprobante y pagos digitales <span class="sg-badge neutro">Opciones avanzadas</span></summary><div id="d-extra-c"></div></details>`;
    }
    async function seleccionar(id) {
        S.sel = id; S.cuenta = null; S.clave = null; S.metodo = null;
        pintarLista();
        armarDetalle();
        $('#d-cab').innerHTML = '<div class="sg-vacio"><span class="sg-giro"></span> Cargando la cuenta…</div>';
        await cargarCuenta();
    }
    async function cargarCuenta() {
        const id = S.sel; if (!id) return;
        const r = await SG.api(`/sesiones-mesa/${id}/cuenta`);
        if (S.sel !== id) return;
        if (!r.ok) {
            if (r.status === 404) { S.sel = null; S.cuenta = null; pintarVacio('No se encontró la cuenta de esa mesa.'); pintarLista(); return; }
            if (!S.cuenta) $('#d-cab').innerHTML = aviso('mal', 'alerta', esc(r.error));
            return;
        }
        S.cuenta = r.data;
        pintarCuenta();
    }
    COB.recargarCuenta = cargarCuenta;
    const mesaActual = () => S.sesiones.find((s) => s.id === S.sel) || null;
    const enFoco = (el) => !!(el && document.activeElement && el.contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));

    function pintarCuenta() {
        const c = S.cuenta; if (!c || !$('#d-cab')) return;
        pintarCab(c); pintarAvisos(c); pintarResumen(c); pintarPagos(c); pintarExtra(c); decidirCobro(c);
    }

    const puedeCobrar = (c) => c.estado_cuenta === 'Emitida' && c.puede_cobrarse && c.caja_abierta;

    function pintarCab(c) {
        const ses = mesaActual() || {};
        const total = SG.num(c.total), saldo = SG.num(c.saldo);
        const estado = c.estado_cuenta;
        let badge = ['neutro', 'Cuenta sin preparar'];
        if (estado === 'Emitida') badge = saldo < total ? ['aviso', 'Cobro parcial'] : ['aviso', 'Pendiente de cobro'];
        if (estado === 'Pagada') badge = ['ok', 'Cuenta pagada'];
        if (estado === 'Anulada') badge = ['mal', 'Cuenta anulada'];
        const sinPreparar = estado === 'Sin emitir' || estado === 'Anulada';
        const puedeCerrar = estado === 'Pagada' || total <= 0;
        const ayuda = sinPreparar
            ? (total > 0 ? 'Cuando el cliente pida pagar, tocá «Preparar la cuenta»: se fija el consumo y la mesa deja de recibir pedidos nuevos.' : 'Esta mesa todavía no tiene consumo.')
            : estado === 'Emitida' ? 'La cuenta está preparada. Elegí cómo paga el cliente y registrá el cobro; si paga por partes, se puede cobrar de a una.'
                : 'La cuenta está paga. Cerrá la mesa para liberarla cuando los clientes se retiren.';
        $('#d-cab').innerHTML = `
            <div class="sg-box-cab">
                <div><h2 style="font-size:22px">Mesa ${esc(c.sesion.numero_mesa)}</h2>
                    <div class="sg-nota" style="margin:4px 0 0">Sesión n.° ${c.sesion.id}${c.sesion.mozo ? ' · Mozo: ' + esc(c.sesion.mozo) : ''}</div></div>
                <span class="sg-badge ${badge[0]}">${badge[1]}</span>
            </div>
            <div class="sg-botones">
                <button type="button" class="sg-btn principal" data-act="preparar" ${sinPreparar && total > 0 ? '' : 'disabled'}>${SG.ico('recibo')}<span>Preparar la cuenta</span></button>
                <button type="button" class="sg-btn" data-act="cerrar-mesa" ${puedeCerrar ? '' : 'disabled'}>${SG.ico('candado')}<span>Cerrar mesa</span></button>
            </div>
            <p class="sg-nota" style="margin:12px 0 0">${esc(ayuda)}</p>`;
        void ses;
    }

    function pintarAvisos(c) {
        const ses = mesaActual() || {};
        const a = [];
        if (c.estado_cuenta !== 'Pagada' && !c.caja_abierta) {
            a.push(aviso('aviso', 'alerta', '<b>La caja está cerrada.</b> No se puede cobrar hasta que un administrador o gerente la abra.',
                AG ? '<div class="sg-botones"><button type="button" class="sg-btn chico" data-act="ir-caja">Ir a Caja y registros</button></div>' : ''));
        }
        if (c.estado_cuenta !== 'Pagada' && c.pedidos_en_cocina > 0) {
            a.push(aviso('aviso', 'reloj', `<b>Hay ${c.pedidos_en_cocina} ${c.pedidos_en_cocina === 1 ? 'pedido' : 'pedidos'} en preparación.</b> Se puede cobrar cuando estén listos.`));
        }
        if (ses.solicita_cuenta && c.estado_cuenta !== 'Pagada') {
            const m = SOLICITADO[ses.metodo_pago_solicitado];
            a.push(aviso('info', 'campana', `<b>El cliente pidió la cuenta</b> ${esc(SG.hace(ses.fecha_hora_solicita_cuenta))}.${m ? ` Quiere pagar con <b>${esc(METODOS[m].txt.toLowerCase())}</b>.` : ''}`));
        }
        const plan = c.plan_pago;
        if (plan && c.estado_cuenta !== 'Pagada' && (plan.partes || []).length) {
            const MODO = { todo: 'toda la cuenta junta', consumo: 'cada uno lo que consumió', partes_iguales: 'en partes iguales' };
            const filas = plan.partes.map((p) => `${esc(p.metodo === 'MercadoPago' ? 'Mercado Pago' : p.metodo)} <b>${moneda$(p.monto)}</b>${SG.num(p.propina) > 0 ? ` (propina ${moneda$(p.propina)})` : ''}${p.metodo === 'MercadoPago' ? ' · se cobra solo' : ' · lo cobrás vos'}`);
            a.push(aviso('info', 'dividir', `<b>Plan de pago de la mesa</b>${plan.por ? ` (armado por ${esc(plan.por)})` : ''}: ${esc(MODO[plan.modo] || plan.modo)}.<br>${filas.join('<br>')}`));
        }
        if (c.gestor_pago && c.estado_cuenta !== 'Pagada') {
            a.push(aviso('aviso', 'candado', `<b>${esc(c.gestor_pago.nombre)} está gestionando el pago desde su celular.</b> Los demás comensales no pueden pagar hasta que termine. Si no responde, podés liberarlo.`,
                '<div class="sg-botones"><button type="button" class="sg-btn chico" data-act="liberar-pago">Liberar el pago</button></div>'));
        }
        if (c.pago_pendiente) {
            a.push(aviso('info', 'mercadopago', `<b>Hay un pago con Mercado Pago esperando confirmación</b> por ${moneda$(c.pago_pendiente.monto)}. Se acredita solo cuando el cliente termina de pagar desde su celular.`));
        }
        if (c.en_sobremesa) {
            a.push(aviso('ok', 'check', '<b>La cuenta está paga.</b> Los clientes pueden seguir en la mesa; cerrala cuando se retiren.'));
        }
        $('#d-avisos').innerHTML = a.join('');
    }

    function motivoNoCobrar(c) {
        if (c.estado_cuenta === 'Pagada') return 'La cuenta ya está paga.';
        if (c.estado_cuenta !== 'Emitida') return 'Primero hay que preparar la cuenta.';
        if (!c.caja_abierta) return 'La caja está cerrada.';
        if (c.pedidos_en_cocina > 0) return 'Hay pedidos todavía en preparación.';
        if (SG.num(c.saldo) <= 0) return 'No queda saldo pendiente.';
        return '';
    }

    function pintarResumen(c) {
        if (!$('#d-cuenta')) return;
        const abierto = $('#d-det') ? $('#d-det').open : S.detAbierto;
        const total = SG.num(c.total), saldo = SG.num(c.saldo), pagado = Math.max(0, total - saldo);
        let estadoPago = 'Sin preparar';
        if (c.estado_cuenta === 'Pagada') estadoPago = 'Pagada completa';
        else if (c.estado_cuenta === 'Emitida') estadoPago = pagado > 0 ? 'Pago parcial' : 'Sin pagos todavía';
        const cobrable = puedeCobrar(c);
        const eq = ['USD', 'BRL', 'PYG'].map((m) => {
            const cot = cotDe(m);
            let valor = cot ? saldo / cot : (c.equivalentes && c.equivalentes[m] != null ? SG.num(c.equivalentes[m]) : null);
            if (valor == null) return '';
            const ref = m === 'PYG' ? `1.000 Gs. = ${moneda$(cot ? cot * 1000 : 0)}` : `1 ${m} = ${moneda$(cot || 0)}`;
            return `<div class="sg-moneda mc-${m}"><div class="cod">${m} · ${SG.MONEDAS[m].corto}</div><div class="val">${D(valor, m)}</div>${cot ? `<div class="sub">${esc(ref)}</div>` : ''}</div>`;
        }).join('');
        const renglones = (c.renglones || []).map((r) => `
            <div class="sg-renglon"><span class="cant">${esc(r.cantidad)}×</span><span>${esc(r.descripcion)}${r.comensal ? `<small>${esc(r.comensal)}</small>` : ''}</span><span class="imp">${moneda$(r.sub_total)}</span></div>`).join('');
        const porCom = Object.entries(c.por_comensal || {});
        $('#d-cuenta').innerHTML = `
            <div class="sg-box-cab"><h2>Cuenta</h2></div>
            <div class="sg-total-card"><div><small>Saldo pendiente</small><strong>${moneda$(saldo)}</strong></div>
                <div style="text-align:right"><small>Total de la cuenta</small><div style="font-weight:850;font-size:17px">${moneda$(total)}</div></div></div>
            <div class="sg-kv" style="margin-top:12px">
                <div><span>Ya cobrado</span><b>${moneda$(pagado)}</b></div>
                <div><span>Estado del pago</span><b>${esc(estadoPago)}</b></div>
                <div><span>¿Se puede cobrar ahora?</span><b style="color:${cobrable ? 'var(--sg-ok)' : 'var(--text-muted)'}">${cobrable ? 'Sí' : 'No' + (motivoNoCobrar(c) ? ' · ' + esc(motivoNoCobrar(c)) : '')}</b></div>
            </div>
            ${saldo > 0 && eq ? `<div class="sg-subtitulo">Saldo en otras monedas</div>
                <p class="sg-nota" style="margin-bottom:10px">Con la cotización de hoy del BCRA. Sirve para saber cuánto pedirle al cliente si paga en efectivo en otra moneda.</p>
                <div class="sg-monedas tres">${eq}</div>` : ''}
            <details class="sg-det" id="d-det" style="margin-top:16px" ${abierto ? 'open' : ''}><summary>Detalle del consumo</summary><div>
                ${renglones || '<div class="sg-vacio">Todavía no hay consumo en esta mesa.</div>'}
                ${porCom.length ? `<div class="sg-subtitulo">Lo que consumió cada comensal</div>
                    <p class="sg-nota" style="margin-bottom:8px">Es informativo. Los platos compartidos se reparten en partes iguales entre quienes los comparten.</p>
                    <div class="sg-kv">${porCom.map(([n, m]) => `<div><span>${esc(n)}</span><b>${moneda$(m)}</b></div>`).join('')}</div>` : ''}
            </div></details>`;
    }

    /* ---------------------------------------------------------------- pagos */
    function detallePago(p) {
        const partes = [];
        if (p.metodo === 'Efectivo') {
            partes.push(`Recibido ${D(p.monto_recibido, p.moneda)}${p.moneda !== 'ARS' && p.cotizacion ? ` (cotización ${moneda$(p.cotizacion)})` : ''}`);
            if (SG.num(p.vuelto) > 0) partes.push(`Vuelto ${moneda$(p.vuelto)}`);
        } else if (p.metodo === 'Tarjeta') partes.push('Confirmado por el personal');
        else if (p.metodo === 'MercadoPago' && p.estado === 'Pendiente') partes.push('Esperando que el cliente termine de pagar');
        if (SG.num(p.propina) > 0) partes.push(`Propina ${moneda$(p.propina)}`);
        return partes.join(' · ');
    }
    COB.filaPago = (p, { acciones = false } = {}) => {
        const m = METODOS[p.metodo] || { txt: p.metodo, ico: 'moneda' };
        const [cls, txt] = ESTADO_PAGO[p.estado] || ['neutro', p.estado];
        const pie = [SG.hora(p.fecha_hora), p.registrado_por].filter(Boolean).join(' · ');
        const botones = [];
        if (acciones && p.estado === 'Pendiente' && p.metodo === 'MercadoPago') {
            botones.push(`<button type="button" class="sg-btn chico" data-act="sync" data-pago="${p.id}">${SG.ico('refrescar')}<span>Verificar pago</span></button>`);
            if (AG) botones.push(`<button type="button" class="sg-btn chico peligro" data-act="cancelar-mp" data-pago="${p.id}">Cancelar pago</button>`);
        }
        if (acciones === 'todo' && AG && p.estado === 'Aprobado' && (p.metodo === 'Efectivo' || p.metodo === 'Tarjeta')) {
            botones.push(`<button type="button" class="sg-btn chico peligro" data-act="anular-pago" data-pago="${p.id}">Anular cobro</button>`);
        }
        return `<div class="sg-item lleno">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
                <div class="izq"><span class="sg-icono-metodo">${SG.ico(m.ico)}</span>
                    <div><strong>${esc(m.txt)} <span class="sg-badge ${cls}" style="margin-left:6px">${esc(txt)}</span></strong>
                    <small>${esc(detallePago(p))}</small><small>${esc(pie)}</small>
                    ${p.motivo_anulacion ? `<small>Motivo de la anulación: ${esc(p.motivo_anulacion)}</small>` : ''}</div></div>
                <div class="der"><span class="sg-monto">${moneda$(p.monto)}</span><small>a la cuenta</small></div>
            </div>
            ${botones.length ? `<div class="sg-botones">${botones.join('')}</div>` : ''}
        </div>`;
    };
    function pintarPagos(c) {
        const pagos = c.pagos || [];
        const cont = pagos.filter((p) => p.estado === 'Aprobado');
        const propina = cont.reduce((a, p) => a + SG.num(p.propina), 0);
        $('#d-pagos').innerHTML = `
            <div class="sg-box-cab"><h2>Cobros registrados</h2>${propina > 0 ? `<span class="sg-badge naranja">Propinas ${moneda$(propina)}</span>` : ''}</div>
            ${pagos.length ? `<div class="sg-lista">${pagos.map((p) => COB.filaPago(p, { acciones: true })).join('')}</div>`
        : '<div class="sg-vacio">Todavía no hay cobros en esta cuenta.</div>'}`;
    }

    /* ------------------------------------------------- comprobante y digitales */
    function pintarExtra(c) {
        const cont = $('#d-extra-c'); if (!cont || enFoco(cont)) return;
        const f = c.factura;
        const mp = (c.pagos || []).filter((p) => p.metodo === 'MercadoPago');
        const comp = f ? `
            <div class="sg-subtitulo" style="margin-top:4px">Comprobante en PDF</div>
            <p class="sg-nota">Si el cliente lo pide, se genera un PDF con el detalle de la cuenta y los pagos para entregárselo. El restaurante conserva siempre el registro del cobro, lo pida o no el cliente.</p>
            <div class="sg-form">
                <label class="sg-check"><input type="checkbox" id="x-qf" ${f.quiere_factura ? 'checked' : ''}><span>El cliente quiere el comprobante en PDF</span></label>
                <div class="sg-campo" id="x-nom-w" ${f.quiere_factura ? '' : 'hidden'}><label for="x-nom">Nombre que va en el comprobante</label>
                    <input id="x-nom" class="sg-input" maxlength="100" placeholder="Nombre o razón social" value="${esc(f.nombre_factura || '')}"></div>
                <div class="sg-botones">
                    <button type="button" class="sg-btn" data-act="guardar-comp">Guardar pedido</button>
                    <button type="button" class="sg-btn" data-act="comprobante" ${f.comprobante_disponible ? '' : 'disabled'}>${SG.ico('descargar')}<span>Descargar comprobante</span></button>
                </div>
                ${f.comprobante_disponible ? '' : `<p class="sg-nota" style="margin:0">${f.estado === 'Pagada' ? 'Marcá la casilla y guardá para poder descargarlo.' : 'Se podrá descargar cuando la cuenta esté paga.'}</p>`}
            </div>` : '<p class="sg-nota" style="margin:0">El comprobante se puede pedir una vez que la cuenta esté preparada.</p>';
        const dig = `
            <div class="sg-subtitulo">Pagos con Mercado Pago</div>
            <p class="sg-nota">El importe neto es lo que Mercado Pago acredita al restaurante, ya descontadas sus comisiones. El estado se actualiza solo; «Verificar pago» lo consulta en el momento.</p>
            ${mp.length ? `<div class="sg-lista">${mp.map((p) => `<div class="sg-item lleno"><div class="sg-kv">
                <div><span>Estado</span><b>${esc((ESTADO_PAGO[p.estado] || [0, p.estado])[1])}</b></div>
                <div><span>Importe a la cuenta</span><b>${moneda$(p.monto)}</b></div>
                ${p.mp_pago_id ? `<div><span>N.° de operación</span><b>${esc(p.mp_pago_id)}</b></div>` : ''}
                ${p.mp_monto_neto != null ? `<div><span>Importe neto acreditado</span><b>${moneda$(p.mp_monto_neto)}</b></div>` : ''}
                <div><span>Fecha</span><b>${esc(SG.fechaHora(p.fecha_hora))}</b></div></div></div>`).join('')}</div>`
                : '<div class="sg-vacio" style="padding:8px 0">Esta cuenta no tiene pagos con Mercado Pago.</div>'}`;
        cont.innerHTML = comp + '<hr class="sg-sep">' + dig;
        const qf = $('#x-qf');
        if (qf) qf.addEventListener('change', () => { $('#x-nom-w').hidden = !qf.checked; if (qf.checked) $('#x-nom').focus(); });
    }

    /* ======================================================================
       FORMULARIO DE COBRO
       ====================================================================== */
    function decidirCobro(c) {
        const box = $('#d-cobro'); if (!box) return;
        if (!puedeCobrar(c)) { box.hidden = true; box.innerHTML = ''; S.firma = ''; return; }
        const saldoC = cent(c.saldo);
        const firma = `${c.sesion.id}|${c.factura && c.factura.id}|${saldoC}`;
        box.hidden = false;
        if (firma === S.firma && box.innerHTML) return;
        if (enFoco(box)) { S.pendienteForm = true; return; }   // no pisar lo que se está tipeando
        S.firma = firma; S.pendienteForm = false; S.clave = null;
        if (!S.metodo) { const m = SOLICITADO[(mesaActual() || {}).metodo_pago_solicitado]; S.metodo = m || 'Efectivo'; }
        armarCobro(c);
    }

    function bloqueComprobante(p, f) {
        return `
            <label class="sg-check"><input type="checkbox" id="${p}-qf" ${f && f.quiere_factura ? 'checked' : ''}><span>El cliente quiere el comprobante en PDF
                <small>Se genera un PDF con el detalle de la cuenta para entregárselo. El restaurante conserva igual el registro del cobro.</small></span></label>
            <div class="sg-campo" id="${p}-nom-w" ${f && f.quiere_factura ? '' : 'hidden'}><label for="${p}-nom">Nombre que va en el comprobante</label>
                <input id="${p}-nom" class="sg-input" maxlength="100" placeholder="Nombre o razón social" value="${esc((f && f.nombre_factura) || '')}"></div>`;
    }
    function bloqueParcial(p) {
        return `
            <label class="sg-check"><input type="checkbox" id="${p}-par"><span>El cliente paga solo una parte de la cuenta
                <small>Usalo cuando un comensal paga lo suyo y el resto de la mesa paga después. Lo que no se cobre queda como saldo pendiente.</small></span></label>
            <div class="sg-parcial" id="${p}-par-w" hidden>
                <div class="sg-campo"><label for="${p}-parm">Cuánto de la cuenta se cobra ahora (en pesos)</label>
                    <input id="${p}-parm" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="Ej.: 12.500,00"></div>
                <div class="sg-botones"><button type="button" class="sg-btn chico" data-act="${p}-mitad">La mitad del saldo</button><button type="button" class="sg-btn chico" data-act="${p}-todo">Todo el saldo</button></div>
            </div>`;
    }

    function armarCobro(c) {
        const f = c.factura;
        const caso = S.metodo;
        const chips = Object.keys(METODOS).map((k) => `<button type="button" class="sg-chip ${k === caso ? 'activo' : ''}" data-metodo="${k}" aria-pressed="${k === caso}">${SG.ico(METODOS[k].ico)}<span>${METODOS[k].txt}</span></button>`).join('');
        let cuerpo = '';
        if (caso === 'Efectivo') {
            cuerpo = `
            <div class="sg-form">
                <div class="sg-fila">
                    <div class="sg-campo"><label for="ef-mon">Moneda con la que paga el cliente</label>
                        <select id="ef-mon" data-sg-select>${SG.CODIGOS.map((m) => `<option value="${m}">${SG.MONEDAS[m].nombre} (${m})</option>`).join('')}</select></div>
                    <div class="sg-campo"><label for="ef-rec">Dinero que entrega el cliente</label>
                        <input id="ef-rec" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="Ej.: 20.000,00"></div>
                </div>
                <div id="ef-equiv" class="sg-nota" style="margin:-6px 0 0"></div>
                <div class="sg-fila">
                    <div class="sg-campo"><label for="ef-prop">Propina (en pesos, opcional)</label>
                        <input id="ef-prop" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="0,00"></div>
                    <div class="sg-campo"><label class="sg-label-vacio">&nbsp;</label><button type="button" class="sg-btn" data-act="ef-justo">Completar con el saldo justo</button></div>
                </div>
                ${bloqueParcial('ef')}
                ${bloqueComprobante('ef', f)}
                <div class="sg-vista" id="ef-resumen" aria-live="polite"></div>
                <button type="button" class="sg-btn principal ancha" data-act="cobrar-efectivo" style="width:100%">${SG.ico('efectivo')}<span>Registrar cobro en efectivo</span></button>
            </div>`;
        } else if (caso === 'Tarjeta') {
            const parteTj = ((c.plan_pago || {}).partes || []).find((p) => p.metodo === 'Tarjeta');
            const propTj = parteTj && SG.num(parteTj.propina) > 0 ? SG.numero(parteTj.propina, 2) : '';
            cuerpo = `
            <div class="sg-form">
                <p class="sg-nota" style="margin:0">El cliente paga con tarjeta de crédito o débito en el posnet. Cobrá la cuenta junto con la propina (si deja) y, cuando el pago ya se acreditó, confirmalo acá. No se maneja efectivo ni vuelto en este cobro.</p>
                ${bloqueParcial('tj')}
                <div class="sg-campo"><label for="tj-prop">Propina para el mozo (en pesos, opcional)</label>
                    <input id="tj-prop" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="0,00" value="${esc(propTj)}"></div>
                ${bloqueComprobante('tj', f)}
                <div class="sg-vista" id="tj-resumen" aria-live="polite"></div>
                <button type="button" class="sg-btn principal" data-act="cobrar-tarjeta" style="width:100%">${SG.ico('tarjeta')}<span>Confirmar cobro con tarjeta</span></button>
            </div>`;
        } else {
            const pen = c.pago_pendiente;
            cuerpo = `
            <div class="sg-apilado">
                ${aviso('info', 'mercadopago', '<b>El pago con Mercado Pago lo inicia el cliente desde su celular.</b> Tiene que entrar a la pantalla «Pagar» de su mesa y elegir Mercado Pago; puede pagar toda la cuenta o solo su parte.',
                    '<p class="sg-nota" style="margin:8px 0 0">Cuando termina de pagar, el cobro aparece solo en esta pantalla. Si querés cobrar otra parte en efectivo o con tarjeta, usá las otras opciones.</p>')}
                ${pen ? aviso('aviso', 'reloj', `<b>Pago pendiente por ${moneda$(pen.monto)}.</b> Si el cliente ya pagó y no se refleja, tocá «Verificar pago» en la lista de cobros de más abajo.`) : ''}
            </div>`;
        }
        $('#d-cobro').innerHTML = `
            <div class="sg-box-cab"><h2>Registrar un cobro</h2></div>
            <div class="sg-etiqueta" style="margin-bottom:8px">¿Cómo paga el cliente?</div>
            <div class="sg-segmentos" style="margin-bottom:18px">${chips}</div>
            ${cuerpo}`;
        SG.selectsEn($('#d-cobro'));
        enlazarCobro();
        recalcularEfectivo(); recalcularTarjeta();
    }

    function enlazarCobro() {
        const box = $('#d-cobro');
        ['ef', 'tj'].forEach((p) => {
            const par = $(`#${p}-par`, box);
            if (par) par.addEventListener('change', () => { $(`#${p}-par-w`, box).hidden = !par.checked; if (par.checked) $(`#${p}-parm`, box).focus(); recalcularEfectivo(); recalcularTarjeta(); });
            const qf = $(`#${p}-qf`, box);
            if (qf) qf.addEventListener('change', () => { $(`#${p}-nom-w`, box).hidden = !qf.checked; if (qf.checked) $(`#${p}-nom`, box).focus(); });
        });
        $$('input, select', box).forEach((i) => i.addEventListener('input', () => { S.clave = null; recalcularEfectivo(); recalcularTarjeta(); }));
        const mon = $('#ef-mon', box); if (mon) mon.addEventListener('change', () => { S.clave = null; recalcularEfectivo(); });
        box.addEventListener('focusout', () => {
            setTimeout(() => { if (S.pendienteForm && !enFoco(box)) { S.pendienteForm = false; if (S.cuenta) decidirCobro(S.cuenta); } }, 50);
        });
    }

    /* mismas reglas que el servidor (solo para mostrar; el servidor decide) */
    function calcular({ recibidoArs, saldo, propina, montoCuenta }) {
        const rec = cent(recibidoArs), sal = cent(saldo), pro = cent(propina);
        if (rec <= 0) return { error: 'Ingresá el dinero que entrega el cliente.' };
        let aplicado;
        if (montoCuenta == null) {
            const disp = rec - pro;
            if (disp < 0) return { error: 'La propina es mayor que el dinero recibido.' };
            aplicado = Math.min(sal, disp);
        } else {
            aplicado = cent(montoCuenta);
            if (aplicado > sal) return { error: `El monto a cobrar supera el saldo (${moneda$(deCent(sal))}).` };
        }
        if (aplicado + pro <= 0) return { error: 'No hay nada para cobrar: ni cuenta ni propina.' };
        const vuelto = rec - aplicado - pro;
        if (vuelto < 0) return { error: `Lo recibido no alcanza: faltan ${moneda$(deCent(-vuelto))}.` };
        return { aplicado: deCent(aplicado), propina: deCent(pro), vuelto: deCent(vuelto) };
    }
    function leerParcial(p) {
        const par = $(`#${p}-par`);
        if (!par || !par.checked) return { activo: false, valor: null };
        const v = SG.parseMonto($(`#${p}-parm`).value);
        return { activo: true, valor: v };
    }
    function leerEfectivo() {
        const c = S.cuenta; const moneda = $('#ef-mon').value;
        const cot = cotDe(moneda);
        const recTxt = SG.parseMonto($('#ef-rec').value);
        const propTxt = $('#ef-prop').value.trim() ? SG.parseMonto($('#ef-prop').value) : '0';
        const par = leerParcial('ef');
        if (!cot) return { error: `Todavía no hay cotización de ${moneda}. Probá con pesos o pedí que se actualicen las cotizaciones.` };
        if (recTxt == null) return { error: 'Ingresá el dinero que entrega el cliente.' };
        if (propTxt == null) return { error: 'La propina no es un número válido.' };
        if (par.activo && par.valor == null) return { error: 'Ingresá cuánto de la cuenta se cobra ahora.' };
        const recibidoArs = Math.round(SG.num(recTxt) * cot * 100) / 100;
        const calc = calcular({ recibidoArs, saldo: c.saldo, propina: propTxt, montoCuenta: par.activo ? par.valor : null });
        return { ...calc, moneda, cot, recibido: recTxt, recibidoArs, propinaTxt: propTxt, parcial: par.activo ? par.valor : null };
    }
    function recalcularEfectivo() {
        const box = $('#ef-resumen'); if (!box || !S.cuenta) return;
        const moneda = $('#ef-mon').value, cot = cotDe(moneda), saldo = SG.num(S.cuenta.saldo);
        const eq = $('#ef-equiv');
        if (moneda === 'ARS') eq.textContent = `Saldo a cobrar: ${moneda$(saldo)}.`;
        else if (cot) {
            const rec = SG.parseMonto($('#ef-rec').value);
            eq.textContent = `Saldo en ${SG.MONEDAS[moneda].corto.toLowerCase()}: ${D(saldo / cot, moneda)} · cotización ${moneda === 'PYG' ? '1.000 Gs. = ' + moneda$(cot * 1000) : '1 ' + moneda + ' = ' + moneda$(cot)}` +
                (rec ? ` · lo que entrega equivale a ${moneda$(SG.num(rec) * cot)}` : '');
        } else eq.textContent = `Todavía no hay cotización de ${moneda}.`;
        const r = leerEfectivo();
        if (r.error) { box.innerHTML = `<div><span>Resumen del cobro</span><b class="mal">${esc(r.error)}</b></div>`; return; }
        box.innerHTML = `
            <div><span>Se cobra de la cuenta</span><b>${moneda$(r.aplicado)}</b></div>
            ${r.propina > 0 ? `<div><span>Propina para el mozo</span><b>${moneda$(r.propina)}</b></div>` : ''}
            <div><span>Vuelto a devolver (siempre en pesos)</span><b>${moneda$(r.vuelto)}</b></div>
            <div><span>Saldo que queda en la cuenta</span><b>${moneda$(SG.num(S.cuenta.saldo) - r.aplicado)}</b></div>`;
    }
    /* Propina del cobro con tarjeta en pesos: 0 si está vacía, null si no es un número válido o es negativa. */
    function leerPropinaTarjeta() {
        const caja = $('#tj-prop'); if (!caja || !caja.value.trim()) return 0;
        const v = SG.parseMonto(caja.value);
        const n = v == null ? null : SG.num(v);
        return n == null || !(n >= 0) ? null : n;
    }
    function recalcularTarjeta() {
        const box = $('#tj-resumen'); if (!box || !S.cuenta) return;
        const par = leerParcial('tj'); const saldo = SG.num(S.cuenta.saldo);
        if (par.activo && par.valor == null) { box.innerHTML = '<div><span>Resumen del cobro</span><b class="mal">Ingresá cuánto se cobra ahora.</b></div>'; return; }
        const monto = par.activo ? SG.num(par.valor) : saldo;
        if (monto > saldo + 0.001) { box.innerHTML = `<div><span>Resumen del cobro</span><b class="mal">El monto supera el saldo (${moneda$(saldo)}).</b></div>`; return; }
        if (monto <= 0) { box.innerHTML = '<div><span>Resumen del cobro</span><b class="mal">El monto tiene que ser mayor a cero.</b></div>'; return; }
        const prop = leerPropinaTarjeta();
        if (prop == null) { box.innerHTML = '<div><span>Resumen del cobro</span><b class="mal">La propina no es un número válido.</b></div>'; return; }
        box.innerHTML = `<div><span>De la cuenta</span><b>${moneda$(monto)}</b></div>${prop > 0 ? `<div><span>Propina para el mozo</span><b>${moneda$(prop)}</b></div><div><span>Total a pasar por el posnet</span><b>${moneda$(monto + prop)}</b></div>` : ''}<div><span>Saldo que queda en la cuenta</span><b>${moneda$(saldo - monto)}</b></div>`;
    }

    function pedidoComprobante(p) {
        const qf = $(`#${p}-qf`); if (!qf) return {};
        const nombre = $(`#${p}-nom`).value.trim();
        return { quiere_factura: qf.checked, nombre_factura: qf.checked ? nombre : undefined };
    }
    function claveFija(body) {
        const huella = JSON.stringify(body);
        if (!S.clave || S.clave.huella !== huella) S.clave = { huella, valor: SG.clave() };
        return S.clave.valor;
    }
    async function despuesDeCobro(r, boton, mensaje) {
        if (!r.ok) { SG.mal(r.error); return; }
        S.cuenta = r.data.cuenta; S.clave = null; S.firma = '';
        SG.ok(mensaje);
        pintarCuenta();
        cargarSesiones();
        if (S.cuenta.estado_cuenta === 'Pagada') SG.ok('La cuenta quedó paga. Ya podés cerrar la mesa.');
        void boton;
    }

    async function cobrarEfectivo(boton) {
        const c = S.cuenta;
        const r = leerEfectivo();
        if (r.error) { SG.mal(r.error); return; }
        const qf = pedidoComprobante('ef');
        if (qf.quiere_factura && !qf.nombre_factura) { SG.mal('Escribí el nombre que va en el comprobante.'); $('#ef-nom').focus(); return; }
        const body = { moneda: r.moneda, recibido: r.recibido, ...qf };
        if (SG.num(r.propinaTxt) > 0) body.propina = r.propinaTxt;
        if (r.parcial != null) body.monto_cuenta = r.parcial;
        const ok = await SG.dialogo({
            titulo: 'Registrar cobro en efectivo', icono: 'efectivo', aceptar: 'Registrar cobro',
            html: `<div class="sg-vista" style="margin-bottom:6px">
                <div><span>Recibido</span><b>${D(r.recibido, r.moneda)}</b></div>
                <div><span>Se cobra de la cuenta</span><b>${moneda$(r.aplicado)}</b></div>
                ${r.propina > 0 ? `<div><span>Propina</span><b>${moneda$(r.propina)}</b></div>` : ''}
                <div><span>Vuelto a devolver en pesos</span><b>${moneda$(r.vuelto)}</b></div></div>`
        });
        if (!ok) return;
        body.clave = claveFija({ ...body });
        await SG.conEspera(boton, async () => {
            const resp = await SG.api(`/facturas/${c.factura.id}/pagos/efectivo`, { method: 'POST', body });
            await despuesDeCobro(resp, boton, SG.num(r.vuelto) > 0 ? `Cobro registrado. Devolvé ${moneda$(r.vuelto)} de vuelto.` : 'Cobro registrado.');
        });
    }
    async function cobrarTarjeta(boton) {
        const c = S.cuenta;
        const par = leerParcial('tj'); const saldo = SG.num(c.saldo);
        if (par.activo && par.valor == null) { SG.mal('Ingresá cuánto de la cuenta se cobra ahora.'); return; }
        const monto = par.activo ? SG.num(par.valor) : saldo;
        if (monto <= 0 || monto > saldo + 0.001) { SG.mal('El monto tiene que ser mayor a cero y no superar el saldo.'); return; }
        const prop = leerPropinaTarjeta();
        if (prop == null) { SG.mal('La propina no es un número válido.'); $('#tj-prop').focus(); return; }
        const qf = pedidoComprobante('tj');
        if (qf.quiere_factura && !qf.nombre_factura) { SG.mal('Escribí el nombre que va en el comprobante.'); $('#tj-nom').focus(); return; }
        const ok = await SG.dialogo({
            titulo: 'Confirmar cobro con tarjeta', icono: 'tarjeta', aceptar: 'Sí, ya se acreditó',
            texto: `Confirmá solo si el posnet ya aprobó el pago de ${moneda$(monto + prop)}${prop > 0 ? ` (cuenta ${moneda$(monto)} + propina ${moneda$(prop)})` : ''}. Este registro no mueve efectivo de la caja.`
        });
        if (!ok) return;
        const body = { ...qf }; if (par.activo) body.monto_cuenta = par.valor;
        if (prop > 0) body.propina = SG.parseMonto($('#tj-prop').value);
        body.clave = claveFija({ ...body });
        await SG.conEspera(boton, async () => {
            const resp = await SG.api(`/facturas/${c.factura.id}/pagos/tarjeta`, { method: 'POST', body });
            await despuesDeCobro(resp, boton, 'Cobro con tarjeta registrado.');
        });
    }

    /* --------------------------------------------------------------- acciones */
    async function liberarPago(boton) {
        const c = S.cuenta; if (!c) return;
        const ok = await SG.dialogo({
            titulo: 'Liberar el pago de la mesa', icono: 'candado', aceptar: 'Liberar',
            texto: `${c.gestor_pago ? c.gestor_pago.nombre : 'Un comensal'} deja de gestionar el pago y cualquier celular de la mesa puede tomarlo. ¿Seguimos?`
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/sesiones-mesa/${c.sesion.id}/pago/liberar`, { method: 'POST', body: {} });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok('Pago liberado.');
            S.firma = ''; await cargarCuenta();
        });
    }

    async function prepararCuenta(boton) {
        const c = S.cuenta;
        const ok = await SG.dialogo({
            titulo: 'Preparar la cuenta', icono: 'recibo', aceptar: 'Preparar la cuenta',
            texto: `Se fija el consumo de la mesa ${c.sesion.numero_mesa} en ${moneda$(c.total)} y la mesa deja de poder hacer pedidos nuevos. ¿Seguimos?`
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/sesiones-mesa/${c.sesion.id}/factura`, { method: 'POST', body: {} });
            if (!r.ok) { SG.mal(r.error); return; }
            S.cuenta = r.data; S.firma = '';
            SG.ok('Cuenta preparada. Ya se puede cobrar.');
            pintarCuenta();
        });
    }
    async function cerrarMesa(boton) {
        const c = S.cuenta;
        const ok = await SG.dialogo({
            titulo: `Cerrar la mesa ${c.sesion.numero_mesa}`, icono: 'candado', aceptar: 'Cerrar mesa',
            texto: 'La mesa queda libre y los clientes ya no pueden usar su código. Esta acción no se puede deshacer.'
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/sesiones-mesa/${c.sesion.id}/cerrar`, { method: 'POST', body: {} });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok(`Mesa ${c.sesion.numero_mesa} cerrada.`);
            S.sel = null; S.cuenta = null;
            pintarVacio('Mesa cerrada. Elegí otra de la lista.');
            await cargarSesiones();
        });
    }
    async function guardarComprobante(boton) {
        const c = S.cuenta; if (!c.factura) return;
        const qf = $('#x-qf').checked; const nombre = $('#x-nom').value.trim();
        if (qf && !nombre) { SG.mal('Escribí el nombre que va en el comprobante.'); $('#x-nom').focus(); return; }
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/facturas/${c.factura.id}/comprobante`, { method: 'PATCH', body: { quiere_factura: qf, nombre_factura: qf ? nombre : undefined } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok(qf ? 'Pedido de comprobante guardado.' : 'Se quitó el pedido de comprobante.');
            await cargarCuenta();
        });
    }
    async function descargarComprobante(boton) {
        const c = S.cuenta; if (!c.factura) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.archivo(`/facturas/${c.factura.id}/comprobante?descargar=1`, `comprobante-mesa-${c.sesion.numero_mesa}.pdf`);
            if (!r.ok) SG.mal(r.error); else SG.ok('Comprobante descargado.');
        });
    }
    COB.descargarComprobanteDe = async (facturaId, mesa, boton) => {
        await SG.conEspera(boton, async () => {
            const r = await SG.archivo(`/facturas/${facturaId}/comprobante?descargar=1`, `comprobante-mesa-${mesa}.pdf`);
            if (!r.ok) SG.mal(r.error); else SG.ok('Comprobante descargado.');
        });
    };
    async function verificarPago(id, boton) {
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/pagos/${id}/sincronizar`, { method: 'POST', body: {} });
            if (!r.ok) { SG.mal(r.error); return; }
            await cargarCuenta();
            const p = ((S.cuenta && S.cuenta.pagos) || []).find((x) => x.id === id);
            if (p && p.estado === 'Aprobado') SG.ok('El pago ya está acreditado.');
            else SG.aviso('El pago todavía no se acreditó. Probá de nuevo en unos segundos.', 'info');
        });
    }
    async function cancelarPagoMp(id, boton) {
        const ok = await SG.dialogo({
            titulo: 'Cancelar el pago pendiente', icono: 'alerta', peligro: true, aceptar: 'Cancelar el pago',
            texto: 'El link de pago deja de servir. Si el cliente ya pagó, el sistema lo detecta y no permite cancelarlo.',
            motivo: { etiqueta: 'Motivo', placeholder: 'Ej.: el cliente prefirió pagar en efectivo' }
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/pagos/${id}/cancelar`, { method: 'POST', body: { motivo: ok.motivo } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok('Pago cancelado.');
            await cargarCuenta();
            if (COB.refrescarAnulaciones) COB.refrescarAnulaciones();
        });
    }
    COB.verificarPago = verificarPago;
    COB.cancelarPagoMp = cancelarPagoMp;

    /* --------------------------------------------------------- eventos (mesas) */
    $('#m-buscar').addEventListener('input', () => { S.buscar = $('#m-buscar').value; pintarLista(); });
    $('#m-lista').addEventListener('click', (e) => { const b = e.target.closest('[data-id]'); if (b) seleccionar(Number(b.dataset.id)); });
    $('#m-detalle').addEventListener('toggle', (e) => { if (e.target.id === 'd-det') S.detAbierto = e.target.open; }, true);
    $('#m-detalle').addEventListener('click', async (e) => {
        const chip = e.target.closest('[data-metodo]');
        if (chip) { S.metodo = chip.dataset.metodo; S.clave = null; if (S.cuenta) armarCobro(S.cuenta); return; }
        const b = e.target.closest('[data-act]'); if (!b) return;
        const a = b.dataset.act;
        if (a === 'preparar') return prepararCuenta(b);
        if (a === 'cerrar-mesa') return cerrarMesa(b);
        if (a === 'ir-caja') return irA('caja');
        if (a === 'liberar-pago') return liberarPago(b);
        if (a === 'cobrar-efectivo') return cobrarEfectivo(b);
        if (a === 'cobrar-tarjeta') return cobrarTarjeta(b);
        if (a === 'guardar-comp') return guardarComprobante(b);
        if (a === 'comprobante') return descargarComprobante(b);
        if (a === 'sync') return verificarPago(Number(b.dataset.pago), b);
        if (a === 'cancelar-mp') return cancelarPagoMp(Number(b.dataset.pago), b);
        const saldo = SG.num(S.cuenta && S.cuenta.saldo);
        const poner = (p, v) => { $(`#${p}-parm`).value = SG.numero(v, 2); S.clave = null; recalcularEfectivo(); recalcularTarjeta(); };
        if (a === 'ef-mitad') return poner('ef', Math.floor(saldo * 50) / 100);
        if (a === 'ef-todo') return poner('ef', saldo);
        if (a === 'tj-mitad') return poner('tj', Math.floor(saldo * 50) / 100);
        if (a === 'tj-todo') return poner('tj', saldo);
        if (a === 'ef-justo') {
            const m = $('#ef-mon').value, cot = cotDe(m);
            if (!cot) { SG.mal(`Todavía no hay cotización de ${m}.`); return; }
            const par = leerParcial('ef');
            const base = par.activo && par.valor != null ? SG.num(par.valor) : saldo;
            const prop = SG.num(SG.parseMonto($('#ef-prop').value) || 0);
            const v = Math.ceil(((base + prop) / cot) * 100 - 1e-9) / 100;
            $('#ef-rec').value = SG.numero(v, SG.MONEDAS[m].dec); S.clave = null; recalcularEfectivo();
        }
    });

    /* ------------------------------------------------------------- propinas */
    const RANGOS = [
        ['hoy', 'Hoy'], ['ayer', 'Ayer'], ['semana', 'Últimos 7 días'], ['mes', 'Este mes']
    ];
    function fechaRel(dias) { const d = new Date(); d.setDate(d.getDate() + dias); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
    function rangoPropinas(k) {
        const hoy = SG.hoy();
        if (k === 'hoy') return [hoy, hoy];
        if (k === 'ayer') return [fechaRel(-1), fechaRel(-1)];
        if (k === 'semana') return [fechaRel(-6), hoy];
        return [hoy.slice(0, 8) + '01', hoy];
    }
    async function cargarPropinas() {
        const desde = $('#pr-desde').value, hasta = $('#pr-hasta').value;
        if (desde && hasta && desde > hasta) { SG.mal('La fecha «Desde» no puede ser posterior a «Hasta».'); return; }
        const q = new URLSearchParams(); if (desde) q.set('desde', desde); if (hasta) q.set('hasta', hasta);
        const r = await SG.api('/propinas' + (q.toString() ? '?' + q : ''));
        if (!r.ok) { $('#pr-lista').innerHTML = aviso('mal', 'alerta', esc(r.error)); return; }
        const filas = r.data.por_mozo || [];
        $('#pr-total').innerHTML = `<div class="sg-total-card"><div><small>${AG ? 'Total de propinas del período' : 'Tus propinas del período'}</small><strong>${moneda$(r.data.total)}</strong></div>
            <div style="text-align:right"><small>Cobros con propina</small><div style="font-weight:850;font-size:17px">${filas.reduce((a, f) => a + f.pagos, 0)}</div></div></div>`;
        $('#pr-lista').innerHTML = filas.length ? filas.map((f) => `
            <div class="sg-item"><div class="izq"><span class="sg-icono-metodo">${SG.ico('usuario')}</span><div><strong>${esc(f.empleado)}</strong><small>${f.pagos} ${f.pagos === 1 ? 'cobro con propina' : 'cobros con propina'}</small></div></div>
                <span class="sg-monto">${moneda$(f.propina_total)}</span></div>`).join('')
            : '<div class="sg-vacio">No hay propinas registradas en ese período.</div>';
    }
    function iniciarPropinas() {
        $('#pr-nota').textContent = AG
            ? 'Son las propinas de cobros ya aprobados, en pesos. Cada propina corresponde al mozo que atendió la mesa.'
            : 'Son tus propinas de cobros ya aprobados, en pesos. Solo ves las de las mesas que atendiste.';
        $('#pr-rapido').innerHTML = RANGOS.map(([k, t]) => `<button type="button" class="sg-chip" data-rango="${k}">${t}</button>`).join('');
        const [d, h] = rangoPropinas('hoy'); $('#pr-desde').value = d; $('#pr-hasta').value = h;
        $('#pr-rapido').addEventListener('click', (e) => {
            const b = e.target.closest('[data-rango]'); if (!b) return;
            const [a, z] = rangoPropinas(b.dataset.rango); $('#pr-desde').value = a; $('#pr-hasta').value = z;
            $$('.sg-chip', $('#pr-rapido')).forEach((x) => x.classList.toggle('activo', x === b));
            cargarPropinas();
        });
        $('#pr-buscar').addEventListener('click', cargarPropinas);
        ['pr-desde', 'pr-hasta'].forEach((id) => $('#' + id).addEventListener('change', () => $$('.sg-chip', $('#pr-rapido')).forEach((x) => x.classList.remove('activo'))));
        $$('.sg-chip', $('#pr-rapido'))[0].classList.add('activo');
    }

    /* ------------------------------------------------------------- arranque */
    COB.sesiones = () => S.sesiones;
    COB.cargarSesiones = cargarSesiones;
    COB.moneda$ = moneda$;
    COB.ESTADO_PAGO = ESTADO_PAGO;

    armarPestanas();
    iniciarPropinas();
    pintarVacio();
    const inicial = (location.hash || '').replace('#', '');
    irA(TABS.some((t) => t.id === inicial) ? inicial : 'mesas');
    COB.cargarCotizaciones();
    cargarEstadoCaja();
    // Enlace directo desde el panel del mozo: cobros.html?sesion=ID abre esa mesa.
    let porAbrir = Number(new URLSearchParams(location.search).get('sesion')) || null;
    SG.sondeo(async () => {
        await cargarSesiones();
        if (porAbrir) {
            const id = porAbrir; porAbrir = null;
            if (S.sesiones.some((x) => x.id === id)) await seleccionar(id);
        }
        if (S.sel) await cargarCuenta();
    }, 7000);
    setInterval(() => { if (!document.hidden) { COB.cargarCotizaciones(); cargarEstadoCaja(); } }, 60000);
})();
