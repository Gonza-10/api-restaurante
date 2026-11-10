/* =========================================================================
   Savage Grill · Cobros del salón — Caja y registros + Anulaciones
   (solo Administración y Gerencia; el mozo no carga esta parte)
   ========================================================================= */
(() => {
    'use strict';
    if (!window.COB || !SG.esAdminGerente()) return;
    const { $, $$, esc } = SG;
    const D = SG.dinero;
    const { S, aviso, moneda$ } = COB;

    const K = { movs: [], soloManuales: false, listo: false, antListo: false, anulListo: false, aud: { desplaz: 0, filtros: '' } };
    const opts = (arr) => arr.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
    const signo = (v, m) => { const n = SG.num(v); return `${n > 0 ? '+' : n < 0 ? '−' : ''}${D(Math.abs(n), m)}`; };
    const CONCEPTO = { Manual: 'Manual', Venta: 'Cobro de mesa', Propina: 'Propina', Vuelto: 'Vuelto', Anulacion: 'Anulación' };

    /* ======================================================================
       ARQUEO (tarjetas por moneda + total en pesos) — se usa al mirar la caja
       abierta, al cerrar y en el historial.
       ====================================================================== */
    function htmlArqueo(a, cerrada) {
        if (!a || !a.efectivo) return '<div class="sg-vacio">Sin datos de arqueo.</div>';
        const tarjetas = SG.CODIGOS.map((m) => {
            const x = a.efectivo[m] || {};
            const dif = SG.num(x.diferencia);
            return `<div class="sg-moneda mc-${m}"><div class="cod">${m} · ${SG.MONEDAS[m].corto}</div>
                <div class="val">${D(x.esperado, m)}</div><div class="sub">Esperado en el cajón</div>
                <div class="sg-mini">
                    <div><span>Fondo inicial</span><b>${D(x.apertura, m)}</b></div>
                    <div><span>Ingresos</span><b>${D(x.ingresos, m)}</b></div>
                    <div><span>Egresos</span><b>${D(x.egresos, m)}</b></div>
                    ${cerrada ? `<div><span>Contado</span><b>${D(x.declarado, m)}</b></div>
                    <div><span>Diferencia</span><b class="sg-dif ${dif === 0 ? 'ok' : 'mal'}">${dif === 0 ? 'Sin diferencia' : signo(dif, m)}</b></div>` : ''}
                </div></div>`;
        }).join('');
        const mp = a.mercado_pago;
        const hayMp = mp && (SG.num(mp.ingresos) !== 0 || SG.num(mp.egresos) !== 0 || (cerrada && SG.num(mp.declarado) !== 0));
        const difMp = mp ? SG.num(mp.diferencia) : 0;
        const tarjetaMp = hayMp ? `<div class="sg-moneda mc-MP"><div class="cod">MERCADO PAGO · Pesos</div>
            <div class="val">${moneda$(mp.esperado)}</div><div class="sub">Esperado en tu cuenta de Mercado Pago</div>
            <div class="sg-mini"><div><span>Cobros</span><b>${moneda$(mp.ingresos)}</b></div><div><span>Devoluciones</span><b>${moneda$(mp.egresos)}</b></div>
            ${cerrada ? `<div><span>Acreditado</span><b>${moneda$(mp.declarado)}</b></div>
            <div><span>Diferencia</span><b class="sg-dif ${difMp === 0 ? 'ok' : 'mal'}">${difMp === 0 ? 'Sin diferencia' : signo(difMp, 'ARS')}</b></div>` : ''}</div></div>` : '';
        const t = a.total || {};
        const esp = t.esperado_en_pesos, dec = t.declarado_en_pesos;
        const total = esp ? `<div class="sg-kv" style="margin-top:14px">
            <div><span>Efectivo esperado (en pesos)</span><b>${moneda$(esp.efectivo)}</b></div>
            ${hayMp ? `<div><span>Mercado Pago esperado</span><b>${moneda$(esp.mercado_pago)}</b></div>` : ''}
            <div class="total"><span>Total esperado en pesos</span><b>${moneda$(esp.total)}</b></div>
            ${cerrada && dec ? `<div><span>Total contado en pesos</span><b>${moneda$(dec.total)}</b></div>
            <div><span>Diferencia total</span><b class="sg-dif ${SG.num(dec.total) - SG.num(esp.total) === 0 ? 'ok' : 'mal'}">${SG.num(dec.total) - SG.num(esp.total) === 0 ? 'Sin diferencia' : signo(SG.num(dec.total) - SG.num(esp.total), 'ARS')}</b></div>` : ''}
        </div>` : '';
        return `<div class="sg-monedas dos">${tarjetas}${tarjetaMp}</div>${total}`;
    }

    function camposMonedas(prefijo, rotulo) {
        return `<div class="sg-monedas dos">${SG.CODIGOS.map((m) => `
            <div class="sg-moneda mc-${m}"><label class="cod" for="${prefijo}-${m}" style="display:block">${m} · ${SG.MONEDAS[m].corto}</label>
                <input id="${prefijo}-${m}" class="sg-input" style="margin-top:8px" inputmode="decimal" autocomplete="off" placeholder="0,00" aria-label="${esc(rotulo)} en ${SG.MONEDAS[m].nombre}"></div>`).join('')}</div>`;
    }
    function leerMonedas(prefijo, { obligatorio }) {
        const montos = {};
        for (const m of SG.CODIGOS) {
            const txt = $(`#${prefijo}-${m}`).value.trim();
            if (!txt) { if (obligatorio) return { error: `Completá el monto de ${SG.MONEDAS[m].corto.toLowerCase()} (poné 0 si no hay).`, foco: `#${prefijo}-${m}` }; montos[m] = '0'; continue; }
            const v = SG.parseMonto(txt);
            if (v == null) return { error: `El monto de ${SG.MONEDAS[m].corto.toLowerCase()} no es un número válido.`, foco: `#${prefijo}-${m}` };
            montos[m] = v;
        }
        return { montos };
    }

    /* ======================================================================
       CAJA ACTUAL
       ====================================================================== */
    async function cargarEstado() {
        const r = await SG.api('/caja/actual');
        if (!r.ok) { $('#c-actual').innerHTML = aviso('mal', 'alerta', esc(r.error)); return; }
        S.caja = r.data;
        pintarCajaActual();
    }
    function pintarCajaActual() {
        const box = $('#c-actual');
        const abierta = S.caja && S.caja.abierta, caja = S.caja && S.caja.caja;
        if (!abierta || !caja) {
            box.innerHTML = `
                <div class="sg-box-cab"><h2>Caja actual</h2><span class="sg-badge neutro">Cerrada</span></div>
                ${aviso('aviso', 'candado', '<b>No hay una caja abierta.</b> Mientras esté cerrada no se puede cobrar en el salón.')}
                <div class="sg-subtitulo">Abrir la caja</div>
                <p class="sg-nota"><b>Fondo inicial:</b> es el efectivo con el que arranca el turno, por ejemplo el cambio para dar vuelto. No es una venta ni se suma a lo cobrado. Dejá en blanco las monedas con las que no arrancás.</p>
                <div class="sg-form">${camposMonedas('ab', 'Fondo inicial')}
                    <button type="button" class="sg-btn principal" data-act="abrir-caja" style="width:100%">${SG.ico('caja')}<span>Abrir caja</span></button></div>`;
            $('#c-mov').innerHTML = `<div class="sg-box-cab"><h2>Ingresos y egresos de efectivo</h2></div><div class="sg-vacio">Abrí la caja para poder registrar movimientos.</div>`;
            return;
        }
        const arq = caja.arqueo || {};
        const hayMp = arq.mercado_pago && (SG.num(arq.mercado_pago.ingresos) !== 0 || SG.num(arq.mercado_pago.egresos) !== 0);
        box.innerHTML = `
            <div class="sg-box-cab"><h2>Caja actual</h2><span class="sg-badge ok">Abierta</span></div>
            <div class="sg-kv">
                <div><span>Caja n.°</span><b>${caja.id}</b></div>
                <div><span>Abierta el</span><b>${esc(SG.fechaHora(caja.fecha_hora_apertura))}</b></div>
                <div><span>Abierta por</span><b>${esc(caja.abierta_por || '—')}</b></div>
            </div>
            <div class="sg-subtitulo">Lo que el sistema espera encontrar</div>
            <p class="sg-nota">Se calcula con el fondo inicial, los cobros y los movimientos. Al cerrar la caja contás lo que hay y se compara con esto: esa comparación es el <b>arqueo</b>.</p>
            ${htmlArqueo(arq, false)}
            <details class="sg-det" id="cj-cierre" style="margin-top:18px"><summary>Cerrar la caja y hacer el arqueo</summary><div>
                <p class="sg-nota">Contá el efectivo que hay en el cajón, moneda por moneda, y anotalo acá (0 si no hay). Si no coincide con lo esperado, la diferencia queda registrada, pero igual se puede cerrar.</p>
                <div class="sg-form">${camposMonedas('ce', 'Efectivo contado')}
                    ${hayMp ? `<div class="sg-campo"><label for="ce-mp">Acreditado en Mercado Pago por los cobros de esta caja (en pesos)</label>
                        <input id="ce-mp" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="0,00">
                        <small class="sg-nota" style="margin:0">Miralo en tu cuenta de Mercado Pago. Hubo cobros digitales en esta caja, así que hay que anotarlo.</small></div>` : ''}
                    <button type="button" class="sg-btn peligro" data-act="cerrar-caja" style="width:100%">${SG.ico('candado')}<span>Cerrar caja</span></button>
                </div></div></details>`;
        pintarMov();
    }

    async function abrirCaja(boton) {
        const r = leerMonedas('ab', { obligatorio: false });
        if (r.error) { SG.mal(r.error); $(r.foco).focus(); return; }
        const resumen = SG.CODIGOS.filter((m) => SG.num(r.montos[m]) > 0).map((m) => D(r.montos[m], m)).join(' · ') || 'sin efectivo inicial';
        const ok = await SG.dialogo({ titulo: 'Abrir la caja', icono: 'caja', aceptar: 'Abrir caja', texto: `Fondo inicial: ${resumen}. Desde ese momento se puede cobrar en el salón.` });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const resp = await SG.api('/caja/abrir', { method: 'POST', body: { montos: r.montos } });
            if (!resp.ok) { SG.mal(resp.error); return; }
            SG.ok('Caja abierta. Ya se puede cobrar.');
            await refrescarCaja();
        });
    }
    async function cerrarCaja(boton) {
        const r = leerMonedas('ce', { obligatorio: true });
        if (r.error) { SG.mal(r.error); $(r.foco).focus(); return; }
        const body = { montos: r.montos };
        const mp = $('#ce-mp');
        if (mp) {
            const v = SG.parseMonto(mp.value);
            if (v == null) { SG.mal('Anotá lo acreditado en Mercado Pago (poné 0 si no se acreditó nada).'); mp.focus(); return; }
            body.mercado_pago = v;
        }
        const ok = await SG.dialogo({
            titulo: 'Cerrar la caja', icono: 'candado', peligro: true, aceptar: 'Cerrar caja',
            texto: 'Al cerrar no se pueden registrar más cobros hasta abrir otra caja. Se compara lo que contaste con lo esperado y el resultado queda guardado. Esta acción no se puede deshacer.'
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const resp = await SG.api('/caja/cerrar', { method: 'POST', body });
            if (!resp.ok) { SG.mal(resp.error); return; }
            const c = resp.data;
            const dif = !!c.hay_diferencias;
            const cont = document.createElement('div');
            cont.innerHTML = `<div class="sg-modal-icono ${dif ? 'peligro' : ''}">${SG.ico(dif ? 'alerta' : 'check')}</div>
                <h3>Caja cerrada${dif ? ' con diferencias' : ''}</h3>
                <p>${dif ? 'Lo contado no coincide con lo esperado. Las diferencias quedaron registradas.' : 'Lo contado coincide con lo esperado. No hay diferencias.'}</p>
                ${(c.advertencias || []).length ? `<div class="sg-apilado" style="margin-bottom:14px">${c.advertencias.map((t) => aviso('aviso', 'alerta', esc(t))).join('')}</div>` : ''}
                ${htmlArqueo(c.arqueo, true)}
                <div class="sg-botones"><button type="button" class="sg-btn principal" data-r="x">Entendido</button></div>`;
            const v = SG.ventana(cont, { ancha: true, etiqueta: 'Resultado del arqueo' });
            $('[data-r="x"]', cont).addEventListener('click', () => v.cerrar());
            setTimeout(() => $('[data-r="x"]', cont).focus(), 30);
            await refrescarCaja();
        });
    }

    /* ======================================================================
       MOVIMIENTOS
       ====================================================================== */
    async function cargarMovs() {
        if (!(S.caja && S.caja.abierta)) { K.movs = []; return; }
        const r = await SG.api('/caja/movimientos');
        if (r.ok) { K.movs = Array.isArray(r.data) ? r.data : []; pintarListaMov(); }
    }
    let movArmado = false;
    function pintarMov() {
        const box = $('#c-mov');
        if (!(S.caja && S.caja.abierta)) { movArmado = false; return; }
        if (!movArmado || !$('#mv-form')) {
            box.innerHTML = `
                <div class="sg-box-cab"><h2>Ingresos y egresos de efectivo</h2></div>
                <p class="sg-nota">Registrá acá el efectivo que entra o sale de la caja y no es el cobro de una mesa: por ejemplo, cambio que se agrega, el pago a un proveedor o un retiro. Siempre hay que escribir el motivo, para que quede en la auditoría.</p>
                <div class="sg-form" id="mv-form">
                    <div class="sg-campo"><span class="sg-etiqueta">Tipo de movimiento</span>
                        <div class="sg-segmentos" id="mv-tipo"><button type="button" class="sg-chip activo" data-tipo="Ingreso" aria-pressed="true">Ingreso</button><button type="button" class="sg-chip" data-tipo="Egreso" aria-pressed="false">Egreso</button></div></div>
                    <div class="sg-fila">
                        <div class="sg-campo"><label for="mv-mon">Moneda</label><select id="mv-mon" data-sg-select>${SG.CODIGOS.map((m) => `<option value="${m}">${SG.MONEDAS[m].nombre} (${m})</option>`).join('')}</select></div>
                        <div class="sg-campo"><label for="mv-monto">Monto</label><input id="mv-monto" class="sg-input" inputmode="decimal" autocomplete="off" placeholder="0,00"></div>
                    </div>
                    <div class="sg-campo"><label for="mv-desc">Descripción</label><input id="mv-desc" class="sg-input" maxlength="200" placeholder="Ej.: cambio para el cajón, pago al proveedor de hielo"></div>
                    <button type="button" class="sg-btn principal" data-act="registrar-mov" style="width:100%;min-height:52px;font-size:15px">${SG.ico('mas')}<span>Registrar movimiento</span></button>
                </div>
                <div class="sg-subtitulo">Movimientos de esta caja</div>
                <div class="sg-segmentos" id="mv-filtro" style="margin-bottom:12px"><button type="button" class="sg-chip activo" data-f="todos">Todos</button><button type="button" class="sg-chip" data-f="manuales">Solo los cargados a mano</button></div>
                <div id="mv-lista" class="sg-lista"></div>`;
            SG.selectsEn(box);
            movArmado = true;
        }
        pintarListaMov();
    }
    function pintarListaMov() {
        const cont = $('#mv-lista'); if (!cont) return;
        let items = K.movs;
        if (K.soloManuales) items = items.filter((m) => m.concepto === 'Manual');
        cont.innerHTML = items.length ? items.slice(0, 60).map((m) => `
            <div class="sg-item"><div class="izq"><span class="sg-badge ${m.tipo === 'Ingreso' ? 'ok' : 'mal'}">${esc(m.tipo)}</span>
                <div><strong>${esc(CONCEPTO[m.concepto] || m.concepto)}${m.medio === 'MercadoPago' ? ' · Mercado Pago' : ''}</strong>
                <small>${esc(m.descripcion || '')}</small><small>${esc(SG.hora(m.fecha_hora))}${m.empleado_nombre ? ' · ' + esc(m.empleado_nombre) : ''}</small></div></div>
                <div class="der"><span class="sg-monto">${D(m.monto, m.moneda)}</span>${m.moneda !== 'ARS' ? `<small>${moneda$(m.monto_ars)}</small>` : ''}</div></div>`).join('')
            + (items.length > 60 ? `<div class="sg-nota" style="text-align:center">Se muestran los 60 más recientes.</div>` : '')
            : `<div class="sg-vacio">${K.soloManuales ? 'Todavía no se cargó ningún movimiento a mano.' : 'Todavía no hay movimientos en esta caja.'}</div>`;
    }
    async function registrarMov(boton) {
        const tipo = $('#mv-tipo .activo').dataset.tipo, moneda = $('#mv-mon').value;
        const monto = SG.parseMonto($('#mv-monto').value), desc = $('#mv-desc').value.trim();
        if (monto == null || SG.num(monto) <= 0) { SG.mal('Ingresá un monto mayor a cero.'); $('#mv-monto').focus(); return; }
        if (!desc) { SG.mal('Escribí una descripción: queda registrada en la auditoría.'); $('#mv-desc').focus(); return; }
        const ok = await SG.dialogo({
            titulo: `Registrar ${tipo.toLowerCase()}`, icono: 'caja', aceptar: 'Registrar',
            texto: `${tipo} de ${D(monto, moneda)} en efectivo. Motivo: «${desc}».`
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api('/caja/movimientos', { method: 'POST', body: { tipo, moneda, monto, descripcion: desc } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok(`${tipo} registrado.`);
            $('#mv-monto').value = ''; $('#mv-desc').value = '';
            await refrescarCaja();
        });
    }

    async function refrescarCaja() {
        await cargarEstado();
        await cargarMovs();
        COB.cargarEstadoCaja();
        cargarAnteriores();
    }

    /* ======================================================================
       COTIZACIONES
       ====================================================================== */
    COB.pintarCot = () => {
        const box = $('#c-cot'); if (!box) return;
        const d = S.cot;
        const filas = (d && d.cotizaciones) || [];
        const cuerpo = SG.CODIGOS.filter((m) => m !== 'ARS').map((m) => {
            const c = filas.find((x) => x.moneda === m);
            if (!c) return `<div class="sg-moneda mc-${m}"><div class="cod">${m} · ${SG.MONEDAS[m].corto}</div><div class="val">—</div><div class="sub">Sin cotización</div></div>`;
            const v = SG.num(c.valor);
            return `<div class="sg-moneda mc-${m}"><div class="cod">${m} · ${SG.MONEDAS[m].corto}</div>
                <div class="val">${m === 'PYG' ? moneda$(v * 1000) : moneda$(v)}</div>
                <div class="sub">${m === 'PYG' ? 'por cada 1.000 Gs.' : 'por cada 1 ' + m}</div>
                <div class="sub">Del ${esc(SG.fecha(c.fecha))}</div></div>`;
        }).join('');
        box.innerHTML = `
            <div class="sg-box-cab"><h2>Cotizaciones del día</h2>${d && d.desactualizada ? '<span class="sg-badge aviso">Desactualizadas</span>' : '<span class="sg-badge ok">Al día</span>'}</div>
            <p class="sg-nota">Vienen del Banco Central (BCRA) y se actualizan solas. Se usan para convertir lo que el cliente entrega en otra moneda. No se pueden cargar a mano.</p>
            <div class="sg-monedas dos">
                <div class="sg-moneda mc-ARS"><div class="cod">ARS · Pesos</div><div class="val">${moneda$(1)}</div><div class="sub">Moneda base</div></div>${cuerpo}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-top:14px">
                <span class="sg-nota" style="margin:0">${d && d.ultima_consulta ? 'Última consulta: ' + esc(SG.fechaHora(d.ultima_consulta)) : 'Todavía no se consultó al BCRA.'}</span>
                <button type="button" class="sg-btn" data-act="act-cot">${SG.ico('refrescar')}<span>Actualizar cotizaciones</span></button>
            </div>`;
    };
    async function actualizarCot(boton) {
        await SG.conEspera(boton, async () => {
            const r = await SG.api('/cotizaciones/actualizar', { method: 'POST', body: {} });
            if (!r.ok) { SG.mal(r.status === 502 ? 'No se pudo consultar al BCRA en este momento. Se siguen usando las últimas cotizaciones guardadas.' : r.error); return; }
            SG.ok('Cotizaciones actualizadas.');
            await COB.cargarCotizaciones();
        });
    }

    /* ======================================================================
       CAJAS ANTERIORES
       ====================================================================== */
    function armarAnteriores() {
        $('#c-ant').innerHTML = `
            <div class="sg-box-cab"><h2>Cajas anteriores</h2></div>
            <p class="sg-nota">Historial de cajas cerradas, con su arqueo y sus movimientos.</p>
            <div class="sg-filtros"><div class="sg-campo"><label for="an-fecha">Fecha de apertura (opcional)</label><input id="an-fecha" type="date" class="sg-input"></div>
                <button type="button" class="sg-btn" data-act="an-buscar">Buscar</button></div>
            <div id="an-lista" class="sg-lista"></div>`;
    }
    async function cargarAnteriores() {
        const f = $('#an-fecha') ? $('#an-fecha').value : '';
        const r = await SG.api('/cajas?estado=Cerrada' + (f ? '&fecha=' + f : ''));
        const cont = $('#an-lista'); if (!cont) return;
        if (!r.ok) { cont.innerHTML = aviso('mal', 'alerta', esc(r.error)); return; }
        const lista = (Array.isArray(r.data) ? r.data : []).slice(0, 12);
        cont.innerHTML = lista.length ? lista.map((c) => `
            <div class="sg-item"><div><strong>Caja n.° ${c.id}</strong><small>Abrió ${esc(SG.fechaHora(c.fecha_hora_apertura))} · ${esc(c.abierta_por || '')}</small><small>Cerró ${esc(SG.fechaHora(c.fecha_hora_cierre))} · ${esc(c.cerrada_por || '')}</small></div>
                <button type="button" class="sg-btn chico" data-act="ver-caja" data-id="${c.id}">Ver arqueo</button></div>`).join('')
            : '<div class="sg-vacio">No hay cajas cerradas para mostrar.</div>';
    }
    async function verCaja(id, boton) {
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/cajas/${id}`);
            if (!r.ok) { SG.mal(r.error); return; }
            const c = r.data;
            const movs = (c.movimientos || []).map((m) => `
                <div class="sg-item"><div class="izq"><span class="sg-badge ${m.tipo === 'Ingreso' ? 'ok' : 'mal'}">${esc(m.tipo)}</span><div><strong>${esc(CONCEPTO[m.concepto] || m.concepto)}</strong><small>${esc(m.descripcion || '')}</small><small>${esc(SG.hora(m.fecha_hora))}${m.empleado_nombre ? ' · ' + esc(m.empleado_nombre) : ''}</small></div></div><span class="sg-monto">${D(m.monto, m.moneda)}</span></div>`).join('');
            const cont = document.createElement('div');
            cont.innerHTML = `<h3>Caja n.° ${c.id}</h3>
                <p>Abrió ${esc(SG.fechaHora(c.fecha_hora_apertura))} (${esc(c.abierta_por || '—')}) · Cerró ${esc(SG.fechaHora(c.fecha_hora_cierre))} (${esc(c.cerrada_por || '—')})</p>
                ${c.hay_diferencias ? aviso('aviso', 'alerta', '<b>Esta caja se cerró con diferencias.</b>') : aviso('ok', 'check', '<b>Se cerró sin diferencias.</b>')}
                <div style="margin-top:14px">${htmlArqueo(c.arqueo, true)}</div>
                <div class="sg-subtitulo">Movimientos</div><div class="sg-lista">${movs || '<div class="sg-vacio">No hubo movimientos.</div>'}</div>
                <div class="sg-botones"><button type="button" class="sg-btn principal" data-r="x">Cerrar</button></div>`;
            const v = SG.ventana(cont, { ancha: true, etiqueta: `Caja ${c.id}` });
            $('[data-r="x"]', cont).addEventListener('click', () => v.cerrar());
        });
    }

    /* ======================================================================
       FACTURAS
       ====================================================================== */
    function armarFacturas() {
        $('#c-fact').innerHTML = `
            <div class="sg-box-cab"><h2>Facturas</h2></div>
            <p class="sg-nota">Cuentas emitidas en la fecha elegida, con su estado. Tocá «Ver detalle» para ver el consumo y los cobros. Se muestran hasta 200.</p>
            <div class="sg-filtros">
                <div class="sg-campo"><label for="f-fecha">Fecha</label><input id="f-fecha" type="date" class="sg-input" value="${SG.hoy()}"></div>
                <div class="sg-campo"><label for="f-estado">Estado</label><select id="f-estado" data-sg-select>${opts([['', 'Todas'], ['Emitida', 'Pendientes de cobro'], ['Pagada', 'Pagadas'], ['Anulada', 'Anuladas']])}</select></div>
                <button type="button" class="sg-btn principal" data-act="f-buscar">Buscar</button>
            </div>
            <div id="f-lista" class="sg-lista"></div>`;
        SG.selectsEn($('#c-fact'));
    }
    const ESTADO_FACT = { Emitida: ['aviso', 'Pendiente de cobro'], Pagada: ['ok', 'Pagada'], Anulada: ['mal', 'Anulada'] };
    COB.htmlFacturaItem = (f, accion) => {
        const [cls, txt] = ESTADO_FACT[f.estado] || ['neutro', f.estado];
        return `<div class="sg-item" data-fid="${f.id}"><div><strong>Factura n.° ${f.id} · Mesa ${esc(f.numero_mesa)}</strong>
            <small>Emitida ${esc(SG.fechaHora(f.fecha_hora_emision))}${f.emitida_por ? ' por ' + esc(f.emitida_por) : ''}</small>
            <span class="sg-badge ${cls}" style="margin-top:6px">${txt}</span></div>
            <div class="der"><span class="sg-monto">${moneda$(f.total)}</span><div style="margin-top:8px">${accion}</div></div></div>`;
    };
    async function cargarFacturas() {
        const q = new URLSearchParams();
        const fecha = $('#f-fecha').value, estado = $('#f-estado').value;
        if (fecha) q.set('fecha', fecha); if (estado) q.set('estado', estado);
        const r = await SG.api('/facturas' + (q.toString() ? '?' + q : ''));
        const cont = $('#f-lista');
        if (!r.ok) { cont.innerHTML = aviso('mal', 'alerta', esc(r.error)); return; }
        const lista = Array.isArray(r.data) ? r.data : [];
        cont.innerHTML = lista.length
            ? lista.map((f) => COB.htmlFacturaItem(f, `<button type="button" class="sg-btn chico" data-act="ver-fact" data-id="${f.id}">Ver detalle</button>`)).join('')
            : '<div class="sg-vacio">No hay facturas para esos filtros.</div>';
    }
    async function verFactura(id, boton) {
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/facturas/${id}`);
            if (!r.ok) { SG.mal(r.error); return; }
            const c = r.data, f = c.factura;
            const renglones = (c.renglones || []).map((x) => `<div class="sg-renglon"><span class="cant">${esc(x.cantidad)}×</span><span>${esc(x.descripcion)}${x.comensal ? `<small>${esc(x.comensal)}</small>` : ''}</span><span class="imp">${moneda$(x.sub_total)}</span></div>`).join('');
            const cont = document.createElement('div');
            cont.innerHTML = `<h3>Mesa ${esc(c.sesion.numero_mesa)} · Factura n.° ${f ? f.id : ''}</h3>
                <p>${f ? 'Emitida ' + esc(SG.fechaHora(f.fecha_hora_emision)) : ''}${c.sesion.mozo ? ' · Mozo: ' + esc(c.sesion.mozo) : ''}</p>
                <div class="sg-kv"><div class="total"><span>Total</span><b>${moneda$(c.total)}</b></div><div><span>Saldo pendiente</span><b>${moneda$(c.saldo)}</b></div>
                    <div><span>Estado</span><b>${esc((ESTADO_FACT[c.estado_cuenta] || [0, c.estado_cuenta])[1])}</b></div></div>
                <div class="sg-subtitulo">Consumo</div>${renglones || '<div class="sg-vacio">Sin renglones.</div>'}
                <div class="sg-subtitulo">Cobros</div><div class="sg-lista">${(c.pagos || []).length ? c.pagos.map((p) => COB.filaPago(p)).join('') : '<div class="sg-vacio">Sin cobros registrados.</div>'}</div>
                <div class="sg-botones fin">${f && f.comprobante_disponible ? `<button type="button" class="sg-btn" data-r="pdf">${SG.ico('descargar')}<span>Descargar comprobante</span></button>` : ''}<button type="button" class="sg-btn principal" data-r="x">Cerrar</button></div>`;
            const v = SG.ventana(cont, { ancha: true, etiqueta: 'Detalle de la factura' });
            $('[data-r="x"]', cont).addEventListener('click', () => v.cerrar());
            const pdf = $('[data-r="pdf"]', cont); if (pdf) pdf.addEventListener('click', () => COB.descargarComprobanteDe(f.id, c.sesion.numero_mesa, pdf));
        });
    }

    /* ======================================================================
       AUDITORÍA
       ====================================================================== */
    const TIPO_AUD = { pago: ['naranja', 'Cobro'], movimiento: ['neutro', 'Movimiento'], caja: ['aviso', 'Caja'], factura: ['naranja', 'Factura'], mesa: ['neutro', 'Mesa'] };
    function armarAuditoria() {
        $('#c-aud').innerHTML = `
            <div class="sg-box-cab"><h2>Auditoría</h2></div>
            <p class="sg-nota">Registro de todo lo que pasó con cobros, facturas, caja y mesas: qué se hizo, cuándo y quién. De lo más nuevo a lo más viejo.</p>
            <div class="sg-filtros">
                <div class="sg-campo"><label for="au-tipo">Qué mostrar</label><select id="au-tipo" data-sg-select>${opts([['', 'Todo'], ['pago', 'Cobros'], ['movimiento', 'Movimientos de caja'], ['caja', 'Aperturas y cierres de caja'], ['factura', 'Facturas'], ['mesa', 'Mesas']])}</select></div>
                <div class="sg-campo"><label for="au-desde">Desde</label><input id="au-desde" type="date" class="sg-input" value="${SG.hoy()}"></div>
                <div class="sg-campo"><label for="au-hasta">Hasta</label><input id="au-hasta" type="date" class="sg-input" value="${SG.hoy()}"></div>
                <div class="sg-campo"><label for="au-mesa">N.° de mesa</label><input id="au-mesa" class="sg-input" inputmode="numeric" placeholder="Todas"></div>
                <button type="button" class="sg-btn principal" data-act="au-buscar">Buscar</button>
            </div>
            <div id="au-lista" class="sg-lista"></div>
            <div id="au-mas" style="margin-top:14px;text-align:center" hidden><button type="button" class="sg-btn" data-act="au-mas">Ver más</button></div>`;
        SG.selectsEn($('#c-aud'));
    }
    async function buscarAuditoria(mas) {
        const LIM = 50;
        const q = new URLSearchParams();
        const tipo = $('#au-tipo').value, d = $('#au-desde').value, h = $('#au-hasta').value, mesa = $('#au-mesa').value.trim();
        if (tipo) q.set('tipo', tipo); if (d) q.set('desde', d); if (h) q.set('hasta', h); if (mesa) q.set('mesa', mesa);
        q.set('limite', LIM);
        if (!mas) K.aud.desplaz = 0;
        q.set('desplazamiento', K.aud.desplaz);
        const r = await SG.api('/auditoria?' + q);
        const cont = $('#au-lista');
        if (!r.ok) { if (!mas) cont.innerHTML = aviso('mal', 'alerta', esc(r.error)); else SG.mal(r.error); return; }
        const ev = r.data.eventos || [];
        const html = ev.map((e) => {
            const [cls, txt] = TIPO_AUD[e.tipo] || ['neutro', e.tipo];
            const meta = [SG.fechaHora(e.fecha_hora), e.empleado && e.empleado.nombre, e.mesa != null ? 'Mesa ' + e.mesa : null].filter(Boolean).join(' · ');
            return `<div class="sg-item"><div class="izq" style="align-items:flex-start"><span class="sg-badge ${cls}">${esc(txt)}</span>
                <div><strong>${esc(e.evento || '')}</strong>${e.descripcion ? `<small>${esc(e.descripcion)}</small>` : ''}<small>${esc(meta)}</small></div></div>
                ${e.monto != null ? `<span class="sg-monto">${D(e.monto, e.moneda || 'ARS')}</span>` : ''}</div>`;
        }).join('');
        if (mas) cont.insertAdjacentHTML('beforeend', html);
        else cont.innerHTML = html || '<div class="sg-vacio">No hay registros para esos filtros.</div>';
        K.aud.desplaz += ev.length;
        $('#au-mas').hidden = !r.data.hay_mas;
    }

    /* ======================================================================
       ANULACIONES
       ====================================================================== */
    const AN = { abiertas: {} };
    function armarAnulaciones() {
        $('#a-cobros').innerHTML = `
            <div class="sg-box-cab"><h2>Anular un cobro o una cuenta</h2></div>
            <p class="sg-nota">Sirve para corregir un error de cobro. Anular un cobro en efectivo devuelve ese dinero a la caja abierta y vuelve a dejar el saldo pendiente; con tarjeta la caja no se mueve. Siempre hay que escribir el motivo y queda en la auditoría.</p>
            <div class="sg-filtros">
                <div class="sg-campo"><label for="an2-fecha">Fecha de emisión</label><input id="an2-fecha" type="date" class="sg-input" value="${SG.hoy()}"></div>
                <div class="sg-campo"><label for="an2-estado">Estado</label><select id="an2-estado" data-sg-select>${opts([['', 'Todas'], ['Emitida', 'Pendientes de cobro'], ['Pagada', 'Pagadas'], ['Anulada', 'Anuladas']])}</select></div>
                <button type="button" class="sg-btn principal" data-act="an2-buscar">Buscar</button>
            </div>
            <div id="an2-lista" class="sg-lista"></div>`;
        $('#a-mesa').innerHTML = `
            <div class="sg-box-cab"><h2>Regularización excepcional de una mesa</h2></div>
            ${aviso('aviso', 'alerta', '<b>Usalo solo en casos excepcionales</b>, por ejemplo si el cliente se fue sin pagar o la cuenta se resolvió por fuera del sistema. Cierra la mesa sin cobrar: <b>no registra ningún pago ni borra la deuda</b>. Solo libera la mesa y deja constancia del motivo.')}
            <div class="sg-form" style="margin-top:16px">
                <div class="sg-campo"><label for="rg-mesa">Mesa a regularizar</label><select id="rg-mesa" data-sg-select data-placeholder="Elegí una mesa abierta"></select></div>
                <button type="button" class="sg-btn peligro" data-act="regularizar" style="width:100%">${SG.ico('candado')}<span>Cerrar mesa sin cobro</span></button>
            </div>`;
        SG.selectsEn($('#a-cobros')); SG.selectsEn($('#a-mesa'));
    }
    async function cargarMesasRegularizar() {
        const r = await SG.api('/sesiones-mesa?estado=abierto');
        const sel = $('#rg-mesa'); if (!sel || !r.ok) return;
        const lista = (Array.isArray(r.data) ? r.data : []).sort((a, b) => a.numero_mesa - b.numero_mesa);
        SG.llenarSelect(sel, lista.map((s) => ({ valor: s.id, texto: `Mesa ${s.numero_mesa} · Sesión n.° ${s.id} · consumo ${moneda$(s.total)}` })), { vacio: lista.length ? 'Elegí una mesa abierta' : 'No hay mesas abiertas', valor: '' });
    }
    async function cargarAnulFacturas() {
        const q = new URLSearchParams();
        const fecha = $('#an2-fecha').value, estado = $('#an2-estado').value;
        if (fecha) q.set('fecha', fecha); if (estado) q.set('estado', estado);
        const r = await SG.api('/facturas' + (q.toString() ? '?' + q : ''));
        const cont = $('#an2-lista');
        if (!r.ok) { cont.innerHTML = aviso('mal', 'alerta', esc(r.error)); return; }
        const lista = Array.isArray(r.data) ? r.data : [];
        AN.abiertas = {};
        cont.innerHTML = lista.length ? lista.map((f) => `<div data-wrap="${f.id}">${COB.htmlFacturaItem(f, `<button type="button" class="sg-btn chico" data-act="an2-ver" data-id="${f.id}">Ver cobros</button>`)}<div class="sg-lista" id="an2-exp-${f.id}" style="margin-top:8px" hidden></div></div>`).join('')
            : '<div class="sg-vacio">No hay facturas para esos filtros.</div>';
    }
    function pintarExpansion(id, c) {
        const box = $(`#an2-exp-${id}`); if (!box) return;
        const f = c.factura;
        const hayVivos = (c.pagos || []).some((p) => ['Aprobado', 'Pendiente'].includes(p.estado));
        box.hidden = false;
        box.innerHTML = `${(c.pagos || []).length ? c.pagos.map((p) => COB.filaPago(p, { acciones: 'todo' })).join('') : '<div class="sg-vacio" style="padding:8px">Esta cuenta no tiene cobros.</div>'}
            ${f && f.estado !== 'Anulada' ? `<div class="sg-botones"><button type="button" class="sg-btn peligro chico" data-act="anular-fact" data-id="${f.id}" ${hayVivos ? 'disabled' : ''}>Anular la cuenta completa</button></div>
                <p class="sg-nota" style="margin:0">${hayVivos ? 'Para anular la cuenta primero hay que anular o cancelar sus cobros.' : 'Al anular la cuenta, la mesa vuelve a poder pedir y se puede preparar una cuenta nueva.'}</p>` : ''}`;
        AN.abiertas[id] = true;
    }
    async function verCobros(id, boton) {
        const box = $(`#an2-exp-${id}`);
        if (AN.abiertas[id]) { box.hidden = true; AN.abiertas[id] = false; boton.textContent = 'Ver cobros'; return; }
        let abrio = false;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/facturas/${id}`);
            if (!r.ok) { SG.mal(r.error); return; }
            pintarExpansion(id, r.data); abrio = true;
        });
        boton.textContent = abrio ? 'Ocultar' : 'Ver cobros';
    }
    async function refrescarExpansion(id) {
        const r = await SG.api(`/facturas/${id}`);
        if (r.ok) pintarExpansion(id, r.data);
    }
    function facturaDe(el) { const w = el.closest('[data-wrap]'); return w ? Number(w.dataset.wrap) : null; }

    async function anularPago(id, boton) {
        const fid = facturaDe(boton);
        const ok = await SG.dialogo({
            titulo: 'Anular el cobro', icono: 'alerta', peligro: true, aceptar: 'Anular cobro',
            texto: 'El cobro deja de contar, el saldo de la cuenta vuelve a quedar pendiente y, si fue en efectivo, el dinero se devuelve en la caja abierta. Esta acción no se puede deshacer.',
            motivo: { etiqueta: 'Motivo de la anulación', placeholder: 'Ej.: se cobró dos veces por error' }
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/pagos/${id}/anular`, { method: 'POST', body: { motivo: ok.motivo } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok('Cobro anulado.');
            if (fid) await refrescarExpansion(fid);
            COB.cargarEstadoCaja(); COB.cargarSesiones();
            if (S.sel) COB.recargarCuenta();
        });
    }
    async function anularFactura(id, boton) {
        const ok = await SG.dialogo({
            titulo: 'Anular la cuenta', icono: 'alerta', peligro: true, aceptar: 'Anular cuenta',
            texto: 'La cuenta queda anulada. La mesa vuelve a poder pedir y se puede preparar una cuenta nueva. Esta acción no se puede deshacer.',
            motivo: { etiqueta: 'Motivo de la anulación', placeholder: 'Ej.: la cuenta se preparó con un error' }
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/facturas/${id}/anular`, { method: 'POST', body: { motivo: ok.motivo } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok('Cuenta anulada.');
            await cargarAnulFacturas();
            COB.cargarSesiones();
            if (S.sel) COB.recargarCuenta();
        });
    }
    async function regularizar(boton) {
        const sel = $('#rg-mesa'); const id = Number(sel.value);
        if (!id) { SG.mal('Elegí la mesa que querés regularizar.'); sel._sg && sel._sg.boton.focus(); return; }
        const texto = sel.options[sel.selectedIndex].textContent;
        const ok = await SG.dialogo({
            titulo: 'Cerrar la mesa sin cobro', icono: 'alerta', peligro: true, aceptar: 'Cerrar sin cobrar',
            texto: `${texto}. Se cierra la mesa sin registrar ningún pago y sin borrar la deuda. Solo hacelo si ya está resuelto por fuera del sistema.`,
            motivo: { etiqueta: 'Motivo (obligatorio)', placeholder: 'Ej.: el cliente se retiró sin pagar, lo resuelve la gerencia' }
        });
        if (!ok) return;
        await SG.conEspera(boton, async () => {
            const r = await SG.api(`/sesiones-mesa/${id}/cerrar`, { method: 'POST', body: { forzar: true, motivo: ok.motivo } });
            if (!r.ok) { SG.mal(r.error); return; }
            SG.ok('Mesa cerrada sin cobro. Quedó registrado el motivo.');
            await cargarMesasRegularizar();
            COB.cargarSesiones();
        });
    }
    COB.refrescarAnulaciones = () => { if (K.anulListo) cargarAnulFacturas(); };

    /* ======================================================================
       ENTRADA DE LAS PESTAÑAS
       ====================================================================== */
    COB.cargarCaja = async () => {
        if (!K.listo) {
            armarFacturas(); armarAuditoria(); armarAnteriores();
            K.listo = true;
            buscarAuditoria(false);
        }
        await Promise.all([refrescarCaja(), COB.cargarCotizaciones(), cargarFacturas()]);
        if (S.cot) COB.pintarCot();
    };
    COB.cargarAnulaciones = async () => {
        if (!K.anulListo) { armarAnulaciones(); K.anulListo = true; cargarAnulFacturas(); }
        cargarMesasRegularizar();
    };

    /* ======================================================================
       EVENTOS
       ====================================================================== */
    document.addEventListener('click', (e) => {
        const b = e.target.closest('[data-act]'); if (!b) return;
        const panel = b.closest('#p-caja, #p-anular'); if (!panel) return;
        const a = b.dataset.act;
        if (a === 'abrir-caja') return abrirCaja(b);
        if (a === 'cerrar-caja') return cerrarCaja(b);
        if (a === 'registrar-mov') return registrarMov(b);
        if (a === 'act-cot') return actualizarCot(b);
        if (a === 'an-buscar') return cargarAnteriores();
        if (a === 'ver-caja') return verCaja(b.dataset.id, b);
        if (a === 'f-buscar') return cargarFacturas();
        if (a === 'ver-fact') return verFactura(b.dataset.id, b);
        if (a === 'au-buscar') return buscarAuditoria(false);
        if (a === 'au-mas') return buscarAuditoria(true);
        if (a === 'an2-buscar') return cargarAnulFacturas();
        if (a === 'an2-ver') return verCobros(Number(b.dataset.id), b);
        if (a === 'anular-pago') return anularPago(Number(b.dataset.pago), b);
        if (a === 'anular-fact') return anularFactura(Number(b.dataset.id), b);
        if (a === 'cancelar-mp') {
            const fid = facturaDe(b);
            return COB.cancelarPagoMp(Number(b.dataset.pago), b).then(() => { if (fid) refrescarExpansion(fid); });
        }
        if (a === 'sync') {
            const fid = facturaDe(b);
            return COB.verificarPago(Number(b.dataset.pago), b).then(() => { if (fid) refrescarExpansion(fid); });
        }
        if (a === 'regularizar') return regularizar(b);
    });
    document.addEventListener('click', (e) => {
        const t = e.target.closest('#mv-tipo [data-tipo]');
        if (t) { $$('#mv-tipo .sg-chip').forEach((x) => { const on = x === t; x.classList.toggle('activo', on); x.setAttribute('aria-pressed', String(on)); }); return; }
        const f = e.target.closest('#mv-filtro [data-f]');
        if (f) { K.soloManuales = f.dataset.f === 'manuales'; $$('#mv-filtro .sg-chip').forEach((x) => x.classList.toggle('activo', x === f)); pintarListaMov(); }
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || e.target.tagName !== 'INPUT') return;
        const id = e.target.id;
        if (['f-fecha'].includes(id)) cargarFacturas();
        if (['au-desde', 'au-hasta', 'au-mesa'].includes(id)) buscarAuditoria(false);
        if (id === 'an-fecha') cargarAnteriores();
        if (id === 'an2-fecha') cargarAnulFacturas();
    });
    document.addEventListener('change', (e) => {
        if (e.target.id === 'f-estado') cargarFacturas();
        if (e.target.id === 'an2-estado') cargarAnulFacturas();
        if (e.target.id === 'au-tipo') buscarAuditoria(false);
    });
})();
