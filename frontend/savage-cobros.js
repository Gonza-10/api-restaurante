/* Savage Grill — UI Cobros. Contrato: README hito cobros / Postman de David (09-11-2026).
   Nunca calcula saldos, conversiones ni vuelto: todos los valores llegan desde la API.
   Ningun PIN ni contrasena se guarda en URLs, logs o almacenamiento persistente. */
(() => {
  'use strict';
  const API = (window.SAVAGE_CONFIG?.API_BASE_URL || 'http://localhost:8080/api/v1').replace(/\/+$/, '');
  const $ = id => document.getElementById(id);
  const estadosFinales = new Set(['aprobado', 'rechazado', 'cancelado', 'expirado', 'anulado']);
  const cliente = { credenciales:null, cuenta:null, pago:null, temporizador:null, clavePendiente:null };
  const personal = { token:null, rol:null, sesion:null, factura:null,claveEfectivo:null,firmaEfectivo:null };
  const ver = (id, activo=true) => { if($(id)) $(id).hidden = !activo; };
  const obj = v => v && typeof v === 'object' && !Array.isArray(v) ? v : {};
  const lista = v => Array.isArray(v) ? v : [];
  const limpiar = el => { el.replaceChildren(); };
  const texto = (valor, alternativo='—') => valor === null || valor === undefined || valor === '' ? alternativo : String(valor);
  function crear(tag, contenido, clase) { const e=document.createElement(tag); if(clase)e.className=clase; e.textContent=texto(contenido); return e; }
  function mostrarMensaje(mensaje, correcto=false) {const el=$('mensaje-global');el.textContent=mensaje;el.className='alerta'+(correcto?' ok':'');ver('mensaje-global');el.scrollIntoView({behavior:'smooth',block:'nearest'});}
  function sinMensaje() { ver('mensaje-global',false); }
  function numeroEntrada(valor, obligatorio=false) {
    let v=String(valor ?? '').trim().replace(',','.');
    if (!v && !obligatorio) return null;
    if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(v)) throw new Error('Ingresá un importe positivo válido con hasta 2 decimales.');
    return v;
  }
  function moneda(valor, divisa='ARS') {
    if (valor == null || valor === '') return '—';
    // Presentación a 2 decimales de valores exactos de la API, sin usar float
    // ni modificar el monto que se envía al backend (cotizaciones hasta 8 decimales).
    const s=String(valor).trim().replace(',','.');
    const m=/^(-?)(\d+)(?:\.(\d+))?$/.exec(s);
    if(!m)return texto(valor);
    const frac=(m[3]||'').padEnd(3,'0');
    let enteroTexto=m[2].replace(/^0+(?=\d)/,'');
    let centimos=Number(frac.slice(0,2))+(frac.charCodeAt(2)>=53?1:0);
    if(centimos===100){
      centimos=0; const digitos=enteroTexto.split('');let lleva=true;
      for(let i=digitos.length-1;i>=0;i--){
        if(digitos[i]==='9')digitos[i]='0';
        else{digitos[i]=String(Number(digitos[i])+1);lleva=false;break;}
      }
      if(lleva)digitos.unshift('1');enteroTexto=digitos.join('');
    }
    const entero=enteroTexto.replace(/\B(?=(\d{3})+(?!\d))/g,'.');
    const decimal=String(centimos).padStart(2,'0');
    const signo=m[1] && (enteroTexto!=='0'||centimos!==0)?'-':'';
    return `${signo}${divisa==='ARS'?'$':divisa+' '}${entero},${decimal}`;
  }
  function linea(contenedor, izquierda, derecha) {
    const e=crear('div','','fila-dato'); e.append(crear('span',izquierda), crear('strong',derecha)); contenedor.append(e);
  }
  function pintarLista(id, elementos, convertir) {
    const el=$(id);limpiar(el);
    if(!elementos.length){el.append(crear('p','No hay registros disponibles.','suave'));return;}
    elementos.slice(0,100).forEach((x,i)=>{const [a,b]=convertir(x,i);linea(el,a,b);});
  }
  async function pedir(ruta, {method='GET', body, autenticado=false, pdf=false}={}) {
    const headers={'Accept':pdf?'application/pdf':'application/json'};
    if(body!==undefined) headers['Content-Type']='application/json';
    if(autenticado){if(!personal.token)throw new Error('Primero iniciá sesión como personal.');headers.Authorization=`Bearer ${personal.token}`;}
    let resp;
    try {
      resp=await fetch(API+ruta,{method,headers,body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
    }catch(e){throw new Error('No pudimos conectarnos. Revisá tu conexión e intentá nuevamente.');}
    if(!resp.ok){
      let msj=resp.status===401?'Volvé a iniciar sesión.':resp.status===403?'No tenés permiso para realizar esta operación.':resp.status===404?'No encontramos el registro solicitado.':resp.status===409?'La operación no puede realizarse en el estado actual.':'No pudimos completar la operación.';
      try {const d=await resp.json();msj += ': '+(typeof(d.error || d.detail || d.mensaje || d.message)==='string' ? (d.error || d.detail || d.mensaje || d.message) : Object.entries(d).map(([k,v])=>k+': '+(Array.isArray(v)?v.join(', '):String(v))).join('; ') || 'Operación no autorizada o inválida');}
      catch {msj += ': '+(resp.status===502?'Mercado Pago no está disponible por el momento.':'Revisá los datos e intentá de nuevo.');}
      throw new Error(msj);
    }
    if(pdf) return resp;
    const content=resp.headers.get('content-type') || '';
    if(!content.includes('json'))throw new Error('No pudimos completar la consulta en este momento. Intentá nuevamente.');
    return resp.json();
  }
  async function operar(fn) {sinMensaje();try {await fn();}catch(e){mostrarMensaje(e.message||'Error inesperado.');}}
  function credenciales() {
    const form=$('form-cliente'); const mesa=form.elements.numero_mesa.value.trim();const pin=form.elements.pin.value.trim();
    if(!/^\d+$/.test(mesa)||Number(mesa)<1)throw new Error('El número de mesa es obligatorio.');
    if(!/^\d{4}$/.test(pin))throw new Error('El PIN debe tener exactamente 4 dígitos.');
    return {numero_mesa:Number(mesa),pin};
  }
  function facturaDeCuenta(c){return obj(c.factura);}
  function saldoDeCuenta(c){return c.saldo ?? c.saldo_pendiente ?? c.total_pendiente;}
  function renderCuenta(datos){
    const c=obj(datos.cuenta && typeof datos.cuenta === 'object' ? datos.cuenta : datos);
    if(c.total === undefined && c.saldo === undefined && !c.renglones){throw new Error('No se pudo mostrar el detalle de tu cuenta. Consultá al mozo.');}
    cliente.cuenta=c;
    $('cliente-total').textContent=moneda(c.total);
    $('cliente-total2').textContent=moneda(c.total);
    $('cliente-saldo').textContent=moneda(saldoDeCuenta(c));
    $('cliente-estado').textContent=texto(c.estado ?? c.factura?.estado ?? 'En curso');
    pintarLista('cliente-renglones',lista(c.renglones),r=>[`${texto(r.cantidad,1)} × ${texto(r.nombre ?? r.producto?.nombre ?? r.producto ?? r.descripcion,'Producto')}`,moneda(r.subtotal ?? r.importe ?? r.total)]);
    const com=obj(c.por_comensal);
    const citems=Array.isArray(c.por_comensal)?c.por_comensal:Object.entries(com).map(([nombre,v])=>({nombre,importe:obj(v).total ?? obj(v).importe ?? v}));
    pintarLista('cliente-comensales',citems,x=>[texto(x.nombre ?? x.comensal),moneda(x.importe ?? x.total ?? x.consumo)]);
    pintarLista('cliente-pagos',lista(c.pagos),p=>[`${texto(p.metodo ?? p.medio ?? p.tipo,'Pago')} · ${texto(p.estado)}`,moneda(p.monto_cuenta ?? p.monto ?? p.importe)]);
    limpiar($('cliente-equivalentes'));
    Object.entries(obj(c.equivalentes)).forEach(([codigo,importe])=>$('cliente-equivalentes').append(crear('span',`${codigo}: ${moneda(importe,codigo)}`)));
    const f=facturaDeCuenta(c);
    if(c.pago_pendiente?.id){cliente.pago=c.pago_pendiente.id;cliente.clavePendiente=null;}
    const puede=c.puede_cobrarse !== false && c.caja_abierta !== false;
    $('cliente-pagar').disabled=!puede;
    const motivos=[];if(c.caja_abierta===false)motivos.push('Caja cerrada');if(c.puede_cobrarse===false)motivos.push('Hay comandas pendientes o en preparación');
    $('cliente-pagar').title=motivos.join(' · ');
    $('cliente-quiere-factura').checked=Boolean(f.quiere_factura);
    $('cliente-nombre-factura').value=texto(f.nombre_factura,'') === '—'?'':(f.nombre_factura || '');
    ver('fila-nombre-factura',$('cliente-quiere-factura').checked);
    ver('cliente-descargar',f.comprobante_disponible === true);
    if(c.pago_pendiente?.estado==='Pendiente') { $('cliente-pago-info').textContent=`Pago pendiente #${c.pago_pendiente.id}. Podés retomar o consultar su estado.`;ver('cliente-pago-info'); }
    if(c.pago_pendiente?.id)iniciarPolling();
    ver('resultado-cliente');ver('acciones-cliente');
  }
  async function consultarCuenta(){cliente.credenciales=credenciales();const datos=await pedir('/cuenta',{method:'POST',body:cliente.credenciales});renderCuenta(datos);mostrarMensaje('Cuenta actualizada.',true);}
  async function cotizaciones(){
    const d=await pedir('/cotizaciones'); const raw=Array.isArray(d)?d:Array.isArray(d.cotizaciones)?d.cotizaciones:d.cotizaciones || d;
    const items=Array.isArray(raw)?raw.map(x=>[x.moneda??x.codigo??'?',x.valor]):Object.entries(obj(raw)).filter(([k])=>['USD','BRL','PYG'].includes(k.toUpperCase())).map(([k,v])=>[k,obj(v).valor ?? v]);
    const el=$('cotizaciones-cliente');limpiar(el);
    if(!items.length) {el.append(crear('p','Las cotizaciones no están disponibles por el momento.','suave'));return;}
    items.forEach(([k,v])=>{el.append(crear('span',`${k}: ${moneda(v)} / unidad`));});
  }
  async function iniciarMercadoPago(){
    const cred=credenciales(),body={...cred,clave:cliente.clavePendiente || (cliente.clavePendiente=uuid())};
    const monto=numeroEntrada($('cliente-monto').value);if(monto!==null)body.monto_cuenta=monto;
    const propina=numeroEntrada($('cliente-propina').value);if(propina!==null)body.propina=propina;
    if($('cliente-quiere-factura').checked){
      const nombre=$('cliente-nombre-factura').value.trim();if(!nombre)throw new Error('Ingresá un nombre para el comprobante.');
      body.quiere_factura=true;body.nombre_factura=nombre;
    }
    const d=await pedir('/cuenta/pagar/mercadopago',{method:'POST',body});
    const p=obj(d.pago || d);cliente.pago=p.id ?? p.pago ?? d.pago_id ?? null;
    cliente.clavePendiente=null;
    const simulado=p.modo==='simulado' || /\/pago-simulado(?:\?|$)/.test(String(p.url_pago||''));
    const info=$('cliente-pago-info');info.replaceChildren();
    info.append(crear('strong',simulado?'Pago de demostración iniciado':'Tu pago está listo para continuar'));
    info.append(crear('p',simulado?
      'Esta versión es de prueba: no se cobra dinero real. El personal autorizado confirmará el resultado.':
      'Abrí Mercado Pago desde este celular para continuar. Volvé a esta pantalla para consultar el estado.'));
    ver('cliente-pago-info');
    if(p.url_pago && !simulado){
      try {const url=new URL(p.url_pago,location.href);
        if(url.protocol!=='https:')throw new Error('Enlace no seguro.');
        const a=crear('a','Abrir Mercado Pago','primario sg-link-pago');a.href=url.href;a.rel='noopener noreferrer';a.target='_blank';info.append(a);
      } catch { mostrarMensaje('No pudimos preparar el enlace de pago. Consultá al personal.'); }
    }
    iniciarPolling();
  }
  function uuid(){if(globalThis.crypto?.randomUUID)return crypto.randomUUID();return 'sg-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);}
  function idPago(){return cliente.pago ?? cliente.cuenta?.pago_pendiente?.id ?? null;}
  function detenerPolling(){if(cliente.temporizador){clearInterval(cliente.temporizador);cliente.temporizador=null;}}
  function iniciarPolling(){detenerPolling();cliente.temporizador=setInterval(()=>{if(!document.hidden)consultarEstadoPago(true).catch(()=>{});},4500);}
  async function consultarEstadoPago(silencioso=false){
    const pago=idPago();if(!pago){if(!silencioso)throw new Error('Todavía no hay un pago para consultar.');return;}
    const d=await pedir('/cuenta/pagar/estado',{method:'POST',body:{...credenciales(),pago}});
    const p=obj(d.pago || d);const estado=texto(p.estado);
    if(d.cuenta)renderCuenta(d.cuenta);
    $('cliente-pago-info').textContent=`Pago ${pago}: ${estado}.${d.aviso ? ' '+d.aviso : ''}`;ver('cliente-pago-info');
    if(estadosFinales.has(estado.toLowerCase())) {detenerPolling();cliente.clavePendiente=null;if(!silencioso)mostrarMensaje(`Estado del pago: ${estado}`,estado.toLowerCase()==='aprobado');}
    return d;
  }
  async function cancelarPago(){const pago=idPago();if(!pago)throw new Error('No hay pago pendiente para cancelar.');
    await pedir('/cuenta/pagar/cancelar',{method:'POST',body:{...credenciales(),pago}});detenerPolling();cliente.pago=null;cliente.clavePendiente=null;mostrarMensaje('Se solicitó cancelar el pago pendiente.',true);await consultarCuenta();}
  function nombreDescarga(h){
    const utf=/filename\*=UTF-8''([^;]+)/i.exec(h||'');const simple=/filename="?([^";]+)"?/i.exec(h||'');
    let n='Comprobante-Savage-Grill.pdf';try{if(utf)n=decodeURIComponent(utf[1]);else if(simple)n=simple[1];}catch{}
    return n.replace(/[\\/:*?"<>|\x00-\x1F]/g,'_').slice(0,140)||'Comprobante-Savage-Grill.pdf';
  }
  async function descargarComprobante(){
    const resp=await pedir('/cuenta/comprobante',{method:'POST',body:credenciales(),pdf:true});
    if(!(resp.headers.get('content-type')||'').includes('pdf'))throw new Error('El comprobante todavía no está disponible.');
    const blob=await resp.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=nombreDescarga(resp.headers.get('Content-Disposition'));document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
  }
  function pintarSesion(d){const c=obj(d.cuenta||d),f=obj(c.factura),el=$('mozo-cuenta');limpiar(el);personal.factura=null;personal.firmaEfectivo=null;personal.claveEfectivo=null;$('efectivo-factura').value='';$('mozo-factura').disabled=true;
    linea(el,'Mesa',texto(c.sesion?.numero_mesa));linea(el,'Estado',texto(c.estado_cuenta));
    linea(el,'Total de la cuenta',moneda(c.total));linea(el,'Saldo pendiente',moneda(saldoDeCuenta(c)));linea(el,'Caja',c.caja_abierta?'Abierta':'Cerrada');
    linea(el,'Disponible para cobrar',c.puede_cobrarse?'Sí':'No');linea(el,'Pedidos pendientes de Cocina',texto(c.pedidos_en_cocina?.length ?? c.pedidos_en_cocina));
    linea(el,'Factura',f.id ? `#${f.id} · ${texto(f.estado)}` : 'Sin emitir');
    if(f.id != null){personal.factura=f.id;$('efectivo-factura').value=f.id;linea(el,'Factura',f.id);}
    $('mozo-factura').disabled=c.caja_abierta===false || c.puede_cobrarse===false || f.id != null;
    $('mozo-cerrar').disabled=!(c.saldo==='0.00'||c.estado_cuenta==='Pagada');
    $('personal-comprobante').disabled=!f.comprobante_disponible;
  }
  function idSesion(){const id=+$('sesion-id').value;if(!Number.isInteger(id)||id<1)throw new Error('Ingresá un ID de sesión válido.');return id;}
  async function cuentaMozo(){const id=idSesion();personal.sesion=id;const d=await pedir(`/sesiones-mesa/${id}/cuenta`,{autenticado:true});pintarSesion(d);mostrarMensaje('Cuenta de mesa consultada.',true);}
  async function emitirFactura(){const id=idSesion();const d=await pedir(`/sesiones-mesa/${id}/factura`,{method:'POST',autenticado:true});
    const f=obj(d.factura);personal.factura=f.id ?? personal.factura;if(personal.factura)$('efectivo-factura').value=personal.factura;
    mostrarMensaje(`Factura interna emitida. ID: ${texto(personal.factura)}`,true);await cuentaMozo();}
  async function cobrarEfectivo(){const id=+$('efectivo-factura').value;if(!id)throw new Error('Ingresá el ID de factura.');
    const body={moneda:$('efectivo-moneda').value,recibido:numeroEntrada($('efectivo-recibido').value,true)};
    const prop=numeroEntrada($('efectivo-propina').value),par=numeroEntrada($('efectivo-parte').value);
    const firma=JSON.stringify([id,body.moneda,body.recibido,prop,par]);
    if(personal.firmaEfectivo!==firma){personal.firmaEfectivo=firma;personal.claveEfectivo=uuid();}
    body.clave=personal.claveEfectivo;
    if(prop!==null)body.propina=prop;if(par!==null)body.monto_cuenta=par;
    if($('efectivo-quiere-factura').checked){const nom=$('efectivo-nombre').value.trim();if(!nom)throw new Error('Escribí el nombre del comprobante.');body.quiere_factura=true;body.nombre_factura=nom;}
    const d=await pedir(`/facturas/${id}/pagos/efectivo`,{method:'POST',autenticado:true,body});
    personal.claveEfectivo=null;personal.firmaEfectivo=null;const pago=obj(d.pago || d);$('efectivo-resultado').textContent=`Pago registrado. ${pago.id?'ID '+pago.id+'. ':''}Vuelto en pesos: ${moneda(pago.vuelto)}. Saldo: ${moneda(d.cuenta?.saldo)}`;ver('efectivo-resultado');
    mostrarMensaje('Cobro en efectivo registrado.',true);if(personal.sesion)await cuentaMozo();
  }
  async function cerrarMesa(){const id=idSesion();if(!confirm('¿Cerrar esta mesa? Solo se permite si está cobrada y no hay pagos pendientes.'))return;
    const d=await pedir(`/sesiones-mesa/${id}/cerrar`,{method:'POST',autenticado:true});mostrarMensaje(`Mesa cerrada correctamente. ${texto(d.mensaje,'')}`,true);}
  function rolRespuesta(d,usuario){const x=d.rol?.nombre ?? d.rol ?? d.empleado?.rol?.nombre ?? d.empleado?.rol ?? d.usuario?.rol ?? d.user?.rol;
    if(x)return texto(x); // solo para renderizar controles; los permisos reales los decide Django.
    return 'Personal';
  }
  async function loginPersonal(){const usuario=$('personal-usuario').value.trim();const contrasena=$('personal-clave').value;
    const d=await pedir('/login',{method:'POST',body:{usuario,contrasena}});const tk=d.token ?? d.access ?? d.access_token ?? d.auth_token;
    if(typeof tk!=='string'||!tk)throw new Error('No pudimos iniciar sesión. Intentá nuevamente.');
    personal.token=tk;personal.rol=rolRespuesta(d,usuario);$('personal-clave').value=''; if(d.empleado){sessionStorage.setItem('savage_token',tk);sessionStorage.setItem('savage_usuario',JSON.stringify(d.empleado));}
    $('personal-identidad').textContent=`Sesión: ${usuario} · ${personal.rol}`;
    const esAdmin=/admin|gerente/i.test(personal.rol);
    ver('personal-acceso',false);ver('panel-personal');ver('panel-administracion',esAdmin);
    mostrarMensaje('Sesión iniciada.',true);
    window.dispatchEvent(new CustomEvent('sg-personal-listo',{detail:{rol:personal.rol}}));if(esAdmin)await consultarCaja();await cargarSesionesPersonal();
  }
  function logout(){personal.token=null;personal.rol=null;personal.sesion=null;personal.factura=null;sessionStorage.removeItem('savage_token');sessionStorage.removeItem('savage_usuario');ver('panel-personal',false);ver('personal-acceso');ver('panel-administracion',false);$('personal-usuario').value='';$('personal-clave').value='';mostrarMensaje('Sesión finalizada.',true);}
  async function consultarCaja(){
    const d=await pedir('/caja/actual',{autenticado:true}),el=$('caja-estado');limpiar(el);const c=obj(d.caja);
    linea(el,'Estado',d.abierta===true?'Abierta':'Cerrada');
    if(!c.id){$('form-abrir-caja').hidden=false;const cierre=$('form-cerrar-caja')?.closest('details');if(cierre)cierre.hidden=true;return;}
    linea(el,'Número de caja',texto(c.id));
    let fecha=texto(c.fecha_hora_apertura);
    try{const f=new Date(fecha);if(!Number.isNaN(f.getTime()))fecha=f.toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});}catch{}
    linea(el,'Abierta desde',fecha);
    $('form-abrir-caja').hidden=true;
    const cierre=$('form-cerrar-caja')?.closest('details');if(cierre)cierre.hidden=false;
    const arq=obj(c.arqueo),fisico=obj(arq.efectivo),digital=obj(arq.mercado_pago),t=obj(arq.total);
    const titulo=crear('h3','Arqueo actual','sg-arqueo-titulo-v8');el.append(titulo);
    const ayuda=crear('p','Dinero esperado: fondo inicial más ingresos, menos egresos y vueltos. Se compara con el dinero contado al cerrar la caja.','suave');el.append(ayuda);
    const grid=crear('div','','sg-caja-fondo-v8');
    for(const m of ['ARS','USD','BRL','PYG']){
      const fila=obj(fisico[m]),box=crear('div','');box.append(crear('span',`Efectivo ${m}`),crear('b',moneda(fila.esperado,m)));grid.append(box);
    }
    const mp=crear('div','');mp.append(crear('span','Mercado Pago acreditado'),crear('b',moneda(digital.esperado)));grid.append(mp);
    const total= obj(t.esperado_en_pesos);
    if(total.total!=null){const b=crear('div','');b.append(crear('span','Total equivalente en pesos'),crear('b',moneda(total.total)));grid.append(b);}
    el.append(grid);
  }
  async function abrirCaja(){const montos=montosFormulario('abrir');const d=await pedir('/caja/abrir',{method:'POST',body:{montos},autenticado:true});mostrarMensaje('Caja abierta correctamente.',true);await consultarCaja();}
  async function cerrarCaja(){if(!confirm('¿Confirmás el cierre y arqueo? Esta operación registra diferencias.'))return;
    const d=await pedir('/caja/cerrar',{method:'POST',body:{montos:montosFormulario('cerrar'),mercado_pago:numeroEntrada($('caja-mp').value,true)},autenticado:true});
    const advertencias=lista(d.advertencias);mostrarMensaje(`Caja cerrada. ${advertencias.length?'Advertencias: '+advertencias.join('; '):'Sin advertencias reportadas.'}`,true);await consultarCaja();}
  function montosFormulario(prefix){const m={};['ARS','USD','BRL','PYG'].forEach(c=>m[c]=numeroEntrada($(`${prefix}-${c}`).value,true));return m;}
  async function movimiento(){const body={tipo:$('mov-tipo').value,moneda:$('mov-moneda').value,monto:numeroEntrada($('mov-monto').value,true),descripcion:$('mov-descripcion').value.trim()};if(!body.descripcion)throw new Error('La descripción es obligatoria.');
    await pedir('/caja/movimientos',{method:'POST',body,autenticado:true});mostrarMensaje('Movimiento registrado.',true);await consultarCaja();}
  async function auditoria(){const params=new URLSearchParams();if($('audit-desde').value)params.set('desde',$('audit-desde').value);if($('audit-hasta').value)params.set('hasta',$('audit-hasta').value);if($('audit-tipo').value)params.set('tipo',$('audit-tipo').value);params.set('limite','30');
    const d=await pedir('/auditoria?'+params,{autenticado:true});const eventos=lista(d.eventos??d.resultados??d.results??d);
    pintarLista('audit-lista',eventos,e=>[`${texto(e.fecha_hora)} · ${texto(e.evento ?? e.tipo)}`,texto(e.descripcion)]);}
  async function propinas(){const d=await pedir('/propinas',{autenticado:true});pintarLista('propinas-resultado',lista(d.por_mozo),e=>[texto(e.mozo ?? e.nombre ?? e.empleado_nombre ?? e.empleado),moneda(e.propina_total)]);
    linea($('propinas-resultado'),'TOTAL',moneda(d.total));}
  async function simularMP(){const id=+$('simular-pago-id').value;const d=await pedir(`/pagos/${id}/simular`,{method:'POST',autenticado:true,body:{resultado:$('simular-resultado').value}});mostrarMensaje(`Simulación enviada: ${texto(d.estado ?? d.pago?.estado)}`,true);}
  async function actualizarBCRA(){await pedir('/cotizaciones/actualizar',{method:'POST',autenticado:true});await cotizaciones();mostrarMensaje('Consulta al BCRA solicitada.',true);}
  async function facturas(){const d=await pedir('/facturas',{autenticado:true});pintarLista('facturas-lista',lista(d.facturas??d.resultados??d.results??d),e=>[`Factura ${texto(e.id)} · ${texto(e.estado)}`,moneda(e.total)]);}
  function crearInputsCaja(){['abrir','cerrar'].forEach(tipo=>['ARS','USD','BRL','PYG'].forEach(m=>{const lab=crear('label',m);const inp=document.createElement('input');inp.id=`${tipo}-${m}`;inp.value='0.00';inp.inputMode='decimal';inp.required=true;lab.append(inp);$(`${tipo}-montos`).append(lab);}));}

  function rolDeEmpleado(e){return typeof e?.rol==='object' ? e.rol.nombre : e?.rol;}
  async function recuperarPersonal(){
    const tk=sessionStorage.getItem('savage_token');if(!tk)return;
    const user=JSON.parse(sessionStorage.getItem('savage_usuario')||'null');
    if(!user)return;
    personal.token=tk;personal.rol=texto(rolDeEmpleado(user),'Personal');
    try {await pedir('/me',{autenticado:true});}
    catch(err){personal.token=null;mostrarMensaje('La sesión del personal expiró. Volvé a iniciar sesión.');return;}
    ver('personal-acceso',false);ver('panel-personal');
    $('personal-identidad').textContent=`${[user.nombre,user.apellido].filter(Boolean).join(' ')} · ${personal.rol}`;
    ver('panel-administracion',/admin|gerente/i.test(personal.rol));
    window.dispatchEvent(new CustomEvent('sg-personal-listo',{detail:{rol:personal.rol}}));if(/admin|gerente/i.test(personal.rol))await consultarCaja();
    await cargarSesionesPersonal();
  }
  async function cargarSesionesPersonal(){
    const d=await pedir('/sesiones-mesa?estado=Abierto',{autenticado:true});
    const el=$('personal-mesas');limpiar(el);
    const items=lista(d.results ?? d);
    if(!items.length){el.append(crear('p','No hay mesas abiertas asignadas a este usuario.','suave'));return;}
    for(const s of items.slice(0,80)){
       const btn=crear('button',`Mesa ${texto(s.numero_mesa)} · Sesión #${s.id}${s.cuenta_solicitada?' · PIDE CUENTA':''}`,'mini');
       btn.type='button';btn.addEventListener('click',()=>{ $('sesion-id').value=s.id; operar(cuentaMozo); });el.append(btn);
    }
  }
  async function descargarFacturaPersonal(){
    const id=Number($('efectivo-factura').value || personal.factura);
    if(!Number.isSafeInteger(id)||id<1)throw new Error('Primero seleccioná una factura emitida.');
    const resp=await pedir(`/facturas/${id}/comprobante?descargar=1`,{pdf:true,autenticado:true});
    if(!(resp.headers.get('content-type')||'').includes('pdf'))throw new Error('El comprobante todavía no está disponible.');
    const blob=await resp.blob(),url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=nombreDescarga(resp.headers.get('Content-Disposition'));a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
  }
  async function sincronizarPagoPersonal(){
    const id=Number($('personal-pago-id').value);
    if(!Number.isSafeInteger(id)||id<1)throw new Error('Ingresá un ID de pago válido.');
    const d=await pedir(`/pagos/${id}/sincronizar`,{method:'POST',autenticado:true});
    $('personal-pago-estado').textContent=`Pago #${id}: ${texto(d.pago?.estado ?? d.estado)}`;
    mostrarMensaje('Estado actualizado.',true);
    if(personal.sesion)await cuentaMozo();
  }
  async function anularOperación(){
    const tipo=$('anular-tipo').value,id=Number($('anular-id').value),motivo=$('anular-motivo').value.trim();
    if(!Number.isSafeInteger(id)||id<1)throw new Error('Ingresá un ID válido.');
    if(!motivo)throw new Error('Ingresá un motivo para la auditoría.');
    if(!confirm('¿Confirmás la anulación? Se registrará en el backend.'))return;
    const ruta=tipo==='factura'?`/facturas/${id}/anular`:tipo==='mp'?`/pagos/${id}/cancelar`:`/pagos/${id}/anular`;
    await pedir(ruta,{method:'POST',body:{motivo},autenticado:true});
    mostrarMensaje('Solicitud registrada.',true);
    if(personal.sesion)await cuentaMozo();
  }
  async function consultarJornada(){
     try {const d=await pedir('/jornada/actual');const n=$('sg-jornada-estado');
       n.textContent=d.abierta ? `Jornada abierta · ${texto(d.jornada?.id)}` : 'Jornada cerrada · pueden quedar mesas de días anteriores';
       ver('sg-jornada-referencia');
     }catch{} // Esto no bloquea el cobro; la caja tiene reglas independientes.
  }
  function precargarCliente(){
     const m=sessionStorage.getItem('savage-mesa-numero'),p=sessionStorage.getItem('savage-mesa-pin');
     if(m && /^\d+$/.test(m))$('form-cliente').elements.numero_mesa.value=m;
     if(p && /^\d{4}$/.test(p))$('form-cliente').elements.pin.value=p;
     if(m && p && /^\d{4}$/.test(p))consultarCuenta().catch(e=>mostrarMensaje(e.message));
  }

  // Regularización excepcional: solo Admin/Gerente. Nunca escribe SQL directamente.
  const sgRegularizacion = {sesion:null, cuenta:null, mesa:null};
  function sgRenglones() { return $('sg-regularizar-detalle'); }
  async function sgConsultarMesaAntigua(){
    if(!/admin|gerente/i.test(personal.rol || '')) throw new Error('Esta operación es exclusiva de Administración y Gerencia.');
    const numero = Number($('sg-regularizar-numero')?.value);
    if(!Number.isSafeInteger(numero) || numero < 1)throw new Error('Ingresá un número de mesa válido.');
    sgRegularizacion.sesion=null;sgRegularizacion.cuenta=null;sgRegularizacion.mesa=numero;
    ver('sg-regularizar-form',false);
    const d=await pedir('/sesiones-mesa?estado=Abierto&mesa='+encodeURIComponent(numero),{autenticado:true});
    const sesiones=lista(d.results ?? d).filter(s=>Number(s.numero_mesa)===numero && String(s.estado).toLowerCase()==='abierto');
    const el=sgRenglones();limpiar(el);
    if(sesiones.length===0){el.append(crear('p','No hay una sesión abierta para esa mesa. Si sigue apareciendo ocupada, necesitamos revisar la diferencia entre la mesa y el historial de sesiones. No intentes liberarla por SQL.','suave'));return;}
    if(sesiones.length>1){el.append(crear('p','Hay más de una sesión abierta: no se puede resolver desde esta pantalla. Avisá a Administración para revisar los registros.','suave'));return;}
    const sesion=sesiones[0];
    const cuenta=await pedir('/sesiones-mesa/'+sesion.id+'/cuenta',{autenticado:true});
    sgRegularizacion.sesion=sesion;sgRegularizacion.cuenta=cuenta;
    const pagos=lista(cuenta.pagos);
    const pendientes=pagos.filter(p=>String(p.estado).toLowerCase()==='pendiente');
    const pedidos=Number(cuenta.pedidos_en_cocina || 0);
    linea(el,'Mesa y sesión','Mesa '+numero+' · Sesión #'+sesion.id);
    linea(el,'Estado de la sesión',texto(cuenta.sesion?.estado ?? sesion.estado));
    linea(el,'Total de consumo',moneda(cuenta.total));
    linea(el,'Saldo pendiente',moneda(saldoDeCuenta(cuenta)));
    linea(el,'Estado de factura',texto(cuenta.factura?.estado ?? 'Sin emitir'));
    linea(el,'Pagos digitales pendientes',String(pendientes.length));
    linea(el,'Pedidos todavía en Cocina',String(pedidos));
    if(pendientes.length){el.append(crear('p','Hay un pago pendiente: primero debe aprobarse, rechazarse o cancelarse de manera válida. No se puede cerrar la mesa.','suave'));return;}
    if(pedidos>0){el.append(crear('p','Todavía existen pedidos en Cocina. Resolvelos antes de cerrar excepcionalmente esta mesa.','suave'));return;}
    const pagada=String(cuenta.factura?.estado ?? '').toLowerCase()==='pagada';
    if(pagada){el.append(crear('p','La factura está pagada. Podés cerrar esta mesa normalmente desde Mesas y cobros.','suave'));return;}
    el.append(crear('p','Esta sesión tiene una cuenta sin acreditar completamente. Un cierre excepcional NO equivale a cobrarla.','suave'));
    $('sg-regularizar-confirmar').placeholder='CERRAR MESA '+numero;
    $('sg-regularizar-confirmar').value='';
    $('sg-regularizar-motivo').value='';
    ver('sg-regularizar-form',true);
  }
  async function sgCerrarMesaAntigua(){
    if(!/admin|gerente/i.test(personal.rol || ''))throw new Error('No tenés autorización para cerrar excepcionalmente una mesa.');
    const {sesion,cuenta,mesa}=sgRegularizacion;
    if(!sesion || !cuenta || mesa!==Number($('sg-regularizar-numero').value)) throw new Error('Consultá de nuevo el estado de la mesa antes de continuar.');
    const motivo=$('sg-regularizar-motivo').value.trim();
    if(motivo.length<12)throw new Error('Explicá el motivo del cierre excepcional (al menos 12 caracteres).');
    if($('sg-regularizar-confirmar').value.trim()!=='CERRAR MESA '+mesa) throw new Error('La confirmación debe decir: CERRAR MESA '+mesa);
    if(lista(cuenta.pagos).some(p=>String(p.estado).toLowerCase()==='pendiente'))throw new Error('Primero hay que resolver los pagos pendientes.');
    if(Number(cuenta.pedidos_en_cocina||0)>0)throw new Error('Primero hay que resolver los pedidos de Cocina.');
    const aviso='Vas a cerrar excepcionalmente la mesa '+mesa+'. Esto NO acredita pagos ni borra deudas. ¿Confirmás?';
    if(!confirm(aviso))return;
    await pedir('/sesiones-mesa/'+sesion.id+'/cerrar',{method:'POST',body:{forzar:true,motivo},autenticado:true});
    mostrarMensaje('La sesión anterior se cerró y quedó registrado el motivo. Revisá el historial y el estado de la mesa.',true);
    sgRegularizacion.sesion=null;sgRegularizacion.cuenta=null;ver('sg-regularizar-form',false);
    await sgConsultarMesaAntigua();
    await cargarSesionesPersonal();
  }

  function eventos(){
    const pendientes=new WeakSet();
    function on(id,evt,fn){const el=$(id);if(!el)return;
      el.addEventListener(evt,async e=>{if(evt==='submit')e.preventDefault();if(pendientes.has(el))return;pendientes.add(el);try{await operar(fn);}finally{pendientes.delete(el);}});}
    if(document.body.dataset.sgPortal==='cliente'){
      on('form-cliente','submit',consultarCuenta);
      on('refrescar-cotizaciones','click',async()=>{await cotizaciones();mostrarMensaje('Cotizaciones actualizadas.',true);});
      on('cliente-pagar','click',iniciarMercadoPago);
      on('cliente-estado-pago','click',async()=>consultarEstadoPago());
      on('cliente-cancelar','click',cancelarPago);
      on('cliente-descargar','click',descargarComprobante);
      $('cliente-quiere-factura')?.addEventListener('change',e=>ver('fila-nombre-factura',e.target.checked));
      precargarCliente();
      cotizaciones().catch(()=>{$('cotizaciones-cliente').textContent='Cotizaciones no disponibles por el momento.';});
      return;
    }
    if(document.body.dataset.sgPortal!=='personal')return;
    on('form-personal','submit',loginPersonal);on('personal-salir','click',async()=>logout());
    on('form-mesa','submit',cuentaMozo);on('mozo-factura','click',emitirFactura);on('mozo-cerrar','click',cerrarMesa);
    $('efectivo-quiere-factura')?.addEventListener('change',e=>ver('efectivo-nombre-fila',e.target.checked));
    on('form-efectivo','submit',cobrarEfectivo);on('propinas-consultar','click',propinas);on('form-mp-simular','submit',simularMP);
    on('caja-consultar','click',async()=>{await consultarCaja();mostrarMensaje('Caja actualizada.',true);});
    on('form-abrir-caja','submit',abrirCaja);on('form-cerrar-caja','submit',cerrarCaja);
    on('form-movimiento','submit',movimiento);on('form-auditoria','submit',auditoria);
    on('cotizacion-actualizar','click',actualizarBCRA);on('facturas-consultar','click',facturas);
    on('sg-regularizar-consultar','click',sgConsultarMesaAntigua);on('sg-regularizar-form','submit',sgCerrarMesaAntigua);
    on('personal-mesas-actualizar','click',cargarSesionesPersonal);on('personal-comprobante','click',descargarFacturaPersonal);
    on('personal-sincronizar','click',sincronizarPagoPersonal);on('form-anular','submit',anularOperación);
    crearInputsCaja();
    const deepId=new URLSearchParams(location.search).get('sesion');
    if(deepId&&/^\d+$/.test(deepId))$('sesion-id').value=deepId;
    recuperarPersonal().then(()=>{if(deepId && personal.token)operar(cuentaMozo);}).catch(e=>mostrarMensaje(e.message));
  }
  eventos();
  window.addEventListener('beforeunload',detenerPolling);
})();
