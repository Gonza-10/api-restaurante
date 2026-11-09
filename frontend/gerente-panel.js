/* SAVAGE GRILL | Portal gerencial P32. Sólo frontend; requiere app.js. */
(() => {
  'use strict';
  const BASE = String(window.SAVAGE_CONFIG?.API_BASE_URL || 'http://localhost:8080/api/v1').replace(/\/+$/, '');
  const $ = id => document.getElementById(id);
  const S = { personal:[], roles:[], productos:[], sesiones:[], usuario:null, cargando:false, editando:null, reportesListos:false, paginasCompletas:true };
  const fmtPrecio = new Intl.NumberFormat('es-AR', { style:'currency', currency:'ARS', maximumFractionDigits:0 });
  const fmtNumero = new Intl.NumberFormat('es-AR', { maximumFractionDigits:0 });
  const fechaLocal = d => [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-');
  const parseFecha = valor => { const d = valor ? new Date(valor) : null; return d && !isNaN(d.getTime()) ? d : null; };
  function rolId(emp) { const r = emp?.rol; return Number(typeof r === 'object' ? r?.id : emp?.rol_id ?? r) || 0; }
  function rolNombre(emp) { const r = emp?.rol; if (typeof r === 'object' && r?.nombre) return r.nombre; if (typeof r === 'string' && !/^\d+$/.test(r)) return r; return S.roles.find(x => Number(x.id) === rolId(emp))?.nombre || (rolId(emp) ? `Rol #${rolId(emp)}` : 'Sin rol'); }
  function mostrar(id, texto, tipo='info') { const nodo = $(id); if (!nodo) return; nodo.textContent = texto || ''; nodo.hidden = !texto; nodo.className = `g-alert ${tipo}`; }
  /** Confirmación con foco, Escape y teclado, sin window.confirm ni valores HTML inyectados. */
  function confirmarSavage({ titulo, mensaje, boton='Confirmar', peligroso=false }={}) {
    return new Promise(resolve => {
      const capa=$('g-modal-confirmar');
      if(!capa || !capa.hidden) { resolve(false); return; }
      const anterior=document.activeElement;
      const overflowAnterior=document.body.style.overflow;
      const aceptar=$('g-confirmar-aceptar');
      const cancelar=$('g-confirmar-cancelar');
      $('g-confirmar-titulo').textContent=titulo||'Confirmar acción';
      $('g-confirmar-texto').textContent=mensaje||'¿Deseás continuar?';
      $('g-confirmar-icono').classList.toggle('danger',Boolean(peligroso));
      aceptar.textContent=boton;
      aceptar.className=`g-btn ${peligroso?'g-btn-danger-filled':'g-btn-primary'}`;
      capa.hidden=false;
      document.body.style.overflow='hidden';
      const control=new AbortController();
      function terminar(valor) {
        control.abort();
        capa.hidden=true;
        document.body.style.overflow=overflowAnterior;
        if(anterior?.isConnected && typeof anterior.focus==='function') anterior.focus();
        resolve(valor);
      }
      cancelar.addEventListener('click',()=>terminar(false),{signal:control.signal});
      aceptar.addEventListener('click',()=>terminar(true),{signal:control.signal});
      capa.addEventListener('pointerdown',e=>{if(e.target===capa)terminar(false);},{signal:control.signal});
      document.addEventListener('keydown',e=>{
        if(e.key==='Escape') {e.preventDefault();e.stopImmediatePropagation();terminar(false);return;}
        if(e.key==='Enter' && e.target===cancelar) return;
        if(e.key==='Tab') {
          const primero=cancelar, ultimo=aceptar;
          if(e.shiftKey && document.activeElement===primero){e.preventDefault();ultimo.focus();}
          else if(!e.shiftKey && document.activeElement===ultimo){e.preventDefault();primero.focus();}
        }
      },{signal:control.signal,capture:true});
      cancelar.focus();
    });
  }
  function crear(tag, clase, texto) { const n=document.createElement(tag); if(clase) n.className=clase; if(texto!=null) n.textContent=String(texto); return n; }
  function boton(texto, clase, accion, deshabilitado=false) { const b=crear('button',`g-btn g-btn-sm ${clase||''}`,texto); b.type='button'; b.disabled=deshabilitado; b.addEventListener('click', accion); return b; }
  function detalleError(obj, fallback) { if(!obj || typeof obj !== 'object') return fallback; const v = obj.error || obj.detail || obj.message; if(typeof v==='string') return v; const datos = Object.entries(obj).filter(([,v])=>v != null).slice(0,4).map(([k,v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join(' · '); return datos || fallback; }
  async function api(ruta, opciones={}) {
    const u = /^https?:\/\//.test(ruta) ? ruta : `${BASE}/${ruta.replace(/^\/+/, '')}`;
    const ctrl = new AbortController();
    const timer = setTimeout(()=>ctrl.abort(),16000);
    try {
      const resp = await apiFetch(u, { ...opciones, signal:ctrl.signal, cache: opciones.cache ?? 'no-store' });
      const texto = await resp.text();
      let datos; try { datos = texto ? JSON.parse(texto) : null; } catch { datos = null; }
      if(!resp.ok) throw new Error(detalleError(datos, `La API respondió con HTTP ${resp.status}.`));
      return datos;
    } catch (e) {
      if(e.name==='AbortError') throw new Error('La API tardó demasiado en responder.');
      throw e;
    } finally { clearTimeout(timer); }
  }
  function lista(datos) { if(Array.isArray(datos)) return datos; if(Array.isArray(datos?.results)) return datos.results; if(Array.isArray(datos?.items)) return datos.items; return null; }
  async function obtenerLista(ruta, maxPaginas=12) {
    let direccion=ruta, items=[], completos=true, paginas=0;
    while(direccion && paginas<maxPaginas) {
      const datos=await api(direccion); const filas=lista(datos);
      if(!filas) throw new Error('La API respondió con un formato de lista no reconocido.');
      items.push(...filas); paginas++;
      if(!datos?.next) break;
      const next=new URL(datos.next, `${BASE}/`);
      const base=new URL(`${BASE}/`);
      if(next.origin!==base.origin || !next.pathname.startsWith(base.pathname)) { completos=false; break; }
      direccion=next.href;
      if(paginas===maxPaginas) completos=false;
    }
    return {items, completos};
  }
  function refreshSelect(id, valores, placeholder, leerValor, leerTexto) {
    const sel=$(id), anterior=sel.value;
    sel.replaceChildren(new Option(placeholder, ''));
    valores.forEach(v=>sel.add(new Option(leerTexto(v), String(leerValor(v)))));
    if(Array.from(sel.options).some(op=>op.value===anterior)) sel.value=anterior;
    sel.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function cambiarVista(vista) {
    document.querySelectorAll('[data-vista]').forEach(b=> { const activa=b.dataset.vista===vista; b.classList.toggle('active',activa); if(activa)b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current'); });
    $('vista-personal').hidden=vista!=='personal'; $('vista-reportes').hidden=vista!=='reportes';
    sessionStorage.setItem('savage-gerencia-vista',vista);
    if(vista==='reportes' && !S.reportesListos) cargarDashboard();
  }
  function actualizarTema() { const claro=document.body.classList.contains('light-mode'); $('g-btn-tema').querySelector('span').textContent=claro?'Modo: Claro':'Modo: Oscuro'; }
  function inicializarTema() {
    if(localStorage.getItem('savage-tema')==='light') document.body.classList.add('light-mode');
    actualizarTema();
    $('g-btn-tema').addEventListener('click',()=>{ document.body.classList.toggle('light-mode');localStorage.setItem('savage-tema', document.body.classList.contains('light-mode')?'light':'dark');actualizarTema(); });
  }
  async function cargarPersonal() {
    mostrar('g-personal-alerta','');
    $('lista-empleados').replaceChildren(crear('div','g-empty','Consultando empleados...'));
    try {
      const [roles, empleados] = await Promise.all([obtenerLista('roles'),obtenerLista('empleados?incluir_inactivos=true')]);
      S.roles=roles.items; S.personal=empleados.items;
      refreshSelect('emp-rol',S.roles,'Seleccioná un rol...',r=>r.id,r=>r.nombre);
      refreshSelect('g-editar-rol',S.roles,'Seleccioná un rol...',r=>r.id,r=>r.nombre);
      refreshSelect('g-filtrar-rol',S.roles,'Todos los roles',r=>r.id,r=>r.nombre);
      renderPersonal();
      if(!empleados.completos) mostrar('g-personal-alerta','El servidor devolvió más páginas de empleados. La lista podría estar incompleta.','info');
    } catch(e) { S.personal=[]; $('lista-empleados').replaceChildren(crear('div','g-empty','No fue posible cargar la plantilla.')); mostrar('g-personal-alerta',`No se pudo consultar personal: ${e.message}`,'error'); }
  }
  function renderPersonal() {
    const q=$('g-buscar-empleado').value.trim().toLocaleLowerCase('es'); const est=$('g-filtrar-estado').value; const rol=$('g-filtrar-rol').value;
    const fil=S.personal.filter(emp=> {
      if(est==='activo' && !emp.activo || est==='inactivo' && !!emp.activo) return false;
      if(rol && String(rolId(emp))!==rol) return false;
      return !q || `${emp.nombre||''} ${emp.apellido||''} ${emp.usuario||''} ${rolNombre(emp)}`.toLocaleLowerCase('es').includes(q);
    });
    const activo=S.personal.filter(x=>x.activo).length;
    const resumen=$('g-resumen-personal'); resumen.replaceChildren();
    [['Total',S.personal.length],['Activos',activo],['Inactivos',S.personal.length-activo],['Visibles',fil.length]].forEach(([texto,n])=>{const chip=crear('span','g-chip');chip.append(crear('span','',`${texto}: `),crear('strong','',fmtNumero.format(n)));resumen.append(chip);});
    const cont=$('lista-empleados'); cont.replaceChildren();
    if(!fil.length) { cont.append(crear('div','g-empty','No hay empleados para estos filtros.')); return; }
    fil.forEach(emp=>{
      const card=crear('article',`g-employee ${emp.activo?'':'inactive'}`);
      const top=crear('div','g-employee-top'); const info=crear('div');info.append(crear('h4','',`${emp.nombre||''} ${emp.apellido||''}`.trim() || `Empleado #${emp.id}`),crear('div','g-username',`@${emp.usuario||'sin-usuario'}`));
      top.append(info,crear('span',`g-badge ${emp.activo?'':'off'}`,emp.activo?'Activo':'Inactivo'));card.append(top);
      const meta=crear('div','g-employee-meta');meta.append(crear('span','',rolNombre(emp))); if(emp.fecha_ingreso){ const fecha=parseFecha(emp.fecha_ingreso);if(fecha)meta.append(crear('span','',` · Ingreso ${fecha.toLocaleDateString('es-AR')}`));} card.append(meta);
      const acciones=crear('div','g-employee-actions');const esPropio=Number(S.usuario?.id)===Number(emp.id);
      acciones.append(boton('Editar datos','',()=>abrirEditor(emp)));
      acciones.append(boton(emp.activo?'Desactivar acceso':'Reactivar acceso',emp.activo?'g-btn-danger':'',()=>alternarEstado(emp),esPropio));
      if(esPropio) acciones.append(crear('span','g-muted','Cuenta actual'));card.append(acciones);cont.append(card);
    });
  }
  function abrirEditor(emp) {
    S.editando=emp; $('g-editar-id').value=String(emp.id);$('g-editar-nombre').value=emp.nombre||'';$('g-editar-apellido').value=emp.apellido||'';$('g-editar-usuario').value=emp.usuario||'';$('g-editar-rol').value=String(rolId(emp));$('g-editar-rol').dispatchEvent(new Event('change',{bubbles:true}));$('g-editar-pass').value=''; mostrar('g-edicion-alerta','');$('g-modal-editar').hidden=false;document.body.style.overflow='hidden';$('g-editar-nombre').focus();
  }
  function cerrarEditor() { $('g-modal-editar').hidden=true; document.body.style.overflow='';S.editando=null; }
  async function guardarEditor(ev) {
    ev.preventDefault();const emp=S.editando;if(!emp)return;
    const id=Number($('g-editar-id').value), rol=Number($('g-editar-rol').value), propio=Number(S.usuario?.id)===id;
    if(!rol)return mostrar('g-edicion-alerta','Seleccioná un rol válido.','error');
    if(propio && rol!==rolId(emp))return mostrar('g-edicion-alerta','No se permite cambiar tu propio rol.','error');
    const payload={nombre:$('g-editar-nombre').value.trim(),apellido:$('g-editar-apellido').value.trim(),usuario:$('g-editar-usuario').value.trim(),rol};
    const pass=$('g-editar-pass').value;if(pass){if(pass.length<8)return mostrar('g-edicion-alerta','La contraseña nueva debe tener al menos 8 caracteres.','error');payload.contrasena_hash=pass;}
    if(!payload.nombre||!payload.apellido||!payload.usuario)return mostrar('g-edicion-alerta','Completá los campos obligatorios.','error');
    if(!await confirmarSavage({
      titulo:'Guardar cambios del empleado',
      mensaje:`¿Confirmás los cambios de ${emp.nombre} ${emp.apellido}?${pass?' También se actualizará su contraseña.':''}`,
      boton:'Guardar cambios'
    }))return;
    const btn=$('g-guardar-edicion');btn.disabled=true;
    try { await api(`empleados/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});cerrarEditor();mostrar('g-personal-alerta','Datos del empleado actualizados correctamente.','success');await cargarPersonal();mostrar('g-personal-alerta','Datos del empleado actualizados correctamente.','success'); }
    catch(e){mostrar('g-edicion-alerta',`No se pudo guardar: ${e.message}`,'error');}finally{btn.disabled=false;}
  }
  async function alternarEstado(emp) {
    const propio=Number(S.usuario?.id)===Number(emp.id);
    if(propio) return mostrar('g-personal-alerta','No podés desactivar tu propia cuenta.','error');
    const activar=!emp.activo;
    if(!await confirmarSavage({
      titulo:activar?'Reactivar acceso':'Desactivar acceso',
      mensaje:`¿Confirmás que querés ${activar?'reactivar':'desactivar'} la cuenta de ${emp.nombre} ${emp.apellido}?`,
      boton:activar?'Reactivar acceso':'Desactivar acceso',
      peligroso:!activar
    }))return;
    try { await api(`empleados/${emp.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({activo:activar})});await cargarPersonal();mostrar('g-personal-alerta',`Acceso ${activar?'reactivado':'desactivado'} correctamente.`,'success'); }
    catch(e){ mostrar('g-personal-alerta',`No se pudo cambiar el estado: ${e.message}`,'error'); }
  }
  async function crearEmpleado(ev) {
    ev.preventDefault();const rol=Number($('emp-rol').value),pass=$('emp-pass').value;
    if(!rol) return mostrar('msj-empleado','Seleccioná un rol.','error');
    if(pass.length<8) return mostrar('msj-empleado','La contraseña debe tener al menos 8 caracteres.','error');
    const payload={nombre:$('emp-nombre').value.trim(),apellido:$('emp-apellido').value.trim(),usuario:$('emp-usuario').value.trim(),rol,contrasena_hash:pass,activo:true};
    if(!payload.nombre||!payload.apellido||!payload.usuario)return mostrar('msj-empleado','Completá todos los campos.','error');
    const btn=$('g-crear-empleado');btn.disabled=true;mostrar('msj-empleado','');
    try {await api('empleados',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('form-empleado').reset();mostrar('msj-empleado','Empleado creado correctamente en el servidor.','success');await cargarPersonal();}
    catch(e){mostrar('msj-empleado',`No se pudo registrar el empleado: ${e.message}`,'error');}finally{btn.disabled=false;}
  }
  const diaDesdeFecha = str => { const d=parseFecha(str);return d?fechaLocal(d):null; };
  function fechasDelPeriodo() {
    const hoy=new Date();hoy.setHours(12,0,0,0);
    const periodo=$('g-periodo').value;const n=periodo==='hoy'?1:periodo==='7'?7:30;
    return Array.from({length:n},(_,i)=>{ const d=new Date(hoy);d.setDate(d.getDate()-(n-1-i));return fechaLocal(d); });
  }
  function renderBarras(id,datos,sinDatos) {
    const cont=$(id);cont.replaceChildren();
    if(!datos.length || datos.every(x=>x.valor===0))return cont.append(crear('div','g-empty',sinDatos));
    const max=Math.max(...datos.map(x=>x.valor),1);
    datos.forEach(d=>{ const row=crear('div','g-bar-row');const titulo=crear('div','g-bar-label',d.etiqueta);titulo.title=d.etiqueta;const track=crear('div','g-track');const llenado=crear('div','g-fill');llenado.style.width=`${d.valor/max*100}%`;track.append(llenado);row.append(titulo,track,crear('strong','g-bar-number',fmtNumero.format(d.valor)));cont.append(row);});
  }
  async function cargarDashboard() {
    S.reportesListos=false; mostrar('g-reporte-alerta','Consultando sesiones reales...','info');
    ['g-kpi-sesiones','g-kpi-cerradas','g-kpi-consumo','g-kpi-abiertas'].forEach(id=>$(id).textContent='—');
    try {
      const [sesiones,productos]=await Promise.all([obtenerLista('sesiones-mesa',25),obtenerLista('productos?incluir_inactivos=true',25)]);
      S.sesiones=sesiones.items;S.productos=productos.items; S.paginasCompletas=sesiones.completos&&productos.completos;
      const dias=fechasDelPeriodo(), claves=new Set(dias);
      const nuevas=S.sesiones.filter(s=>claves.has(diaDesdeFecha(s.fecha_hora_apertura)));
      const cerradas=S.sesiones.filter(s=>claves.has(diaDesdeFecha(s.fecha_hora_cierre)));
      const abiertas=S.sesiones.filter(s=>String(s.estado||'').toLowerCase()==='abierto');
      const valores=nuevas.map(s=>{const detalles=Array.isArray(s.detalles)?s.detalles:null; if(detalles && detalles.length && detalles.every(d=>d.sub_total!==undefined && d.sub_total!==null))return detalles.reduce((t,d)=>t+(Number(d.sub_total)||0),0);return Number(s.total)||0;});
      const consumo=valores.reduce((a,b)=>a+b,0);
      $('g-kpi-sesiones').textContent=fmtNumero.format(nuevas.length);
      $('g-kpi-cerradas').textContent=fmtNumero.format(cerradas.length);
      $('g-kpi-consumo').textContent=fmtPrecio.format(consumo);
      $('g-kpi-abiertas').textContent=fmtNumero.format(abiertas.length);
      const productosMap=new Map(S.productos.map(p=>[Number(p.id),p.nombre]));
      const unidades=new Map();
      nuevas.forEach(s=>(Array.isArray(s.detalles)?s.detalles:[]).forEach(d=>{
        const id=Number(typeof d.producto==='object'?d.producto?.id:d.producto ?? d.producto_id);
        const cant=Number(d.cantidad)||0;
        if(id>0 && cant>0)unidades.set(id,(unidades.get(id)||0)+cant);
      }));
      const listaMasPedidos=[...unidades].sort((a,b)=>b[1]-a[1]).slice(0,8).map(([id,cant])=>({etiqueta:productosMap.get(id)||`Producto #${id}`,valor:cant}));
      renderBarras('g-grafico-productos',listaMasPedidos,'No hay unidades registradas en las sesiones del período.');
      const sumPorDia=new Map(dias.map(d=>[d,0]));
      nuevas.forEach(s=>{const d=diaDesdeFecha(s.fecha_hora_apertura);sumPorDia.set(d,(sumPorDia.get(d)||0)+1);});
      const entradas=[...sumPorDia];
      // Para 30 días, agrupar en bloques de hasta 5 sin omitir registros.
      const barras=entradas.length<=14
        ? entradas.map(([clave,valor])=>({etiqueta:clave.slice(8)+'/'+clave.slice(5,7),valor}))
        : Array.from({length:Math.ceil(entradas.length/5)},(_,i)=>{
            const bloque=entradas.slice(i*5,(i+1)*5);
            const primero=bloque[0][0],ultimo=bloque[bloque.length-1][0];
            return {etiqueta:`${primero.slice(8)}/${primero.slice(5,7)}–${ultimo.slice(8)}/${ultimo.slice(5,7)}`, valor:bloque.reduce((t,x)=>t+x[1],0)};
          });
      renderBarras('g-grafico-sesiones',barras,'No se registran aperturas de mesa en el período elegido.');
      $('g-fecha-reporte').textContent=`Actualizado ${new Date().toLocaleString('es-AR')}`;
      $('g-alcance-consulta').textContent= S.paginasCompletas ? `Base consultada: ${S.sesiones.length} sesiones históricas disponibles.` : `Consulta parcial: ${S.sesiones.length} sesiones recuperadas. Hay páginas pendientes; los indicadores pueden subestimar la actividad.`;
      mostrar('g-reporte-alerta',S.paginasCompletas?'':'La API tiene más páginas de registros que las consultadas. Los resultados podrían estar incompletos.','info');
      S.reportesListos=true;
    } catch(e) { mostrar('g-reporte-alerta',`No se pudieron calcular los indicadores: ${e.message}. No se mostrarán cifras estimadas sin respaldo.`,'error');S.reportesListos=false; }
  }
  function conectarEventos() {
    document.querySelectorAll('[data-vista]').forEach(b=>b.addEventListener('click',()=>cambiarVista(b.dataset.vista)));
    $('g-ir-admin').addEventListener('click',()=>{window.location.href='admin.html';});
    $('g-cerrar-sesion').addEventListener('click',()=>cerrarSesion());
    $('form-empleado').addEventListener('submit',crearEmpleado);
    ['g-buscar-empleado','g-filtrar-estado','g-filtrar-rol'].forEach(id=>$(id).addEventListener(id==='g-buscar-empleado'?'input':'change',renderPersonal));
    $('g-refrescar-personal').addEventListener('click',cargarPersonal);
    $('g-periodo').addEventListener('change',cargarDashboard);
    $('g-actualizar-dashboard').addEventListener('click',cargarDashboard);
    $('g-form-editar').addEventListener('submit',guardarEditor);
    ['g-cerrar-edicion','g-cancelar-edicion'].forEach(id=>$(id).addEventListener('click',cerrarEditor));
    $('g-modal-editar').addEventListener('click',e=>{if(e.target===$('g-modal-editar'))cerrarEditor();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape' && $('g-modal-confirmar').hidden && !$('g-modal-editar').hidden) cerrarEditor();});
  }
  async function iniciar() {
    const actual=typeof obtenerUsuarioActual==='function'?obtenerUsuarioActual():null;
    if(!actual || actual.rol!=='Gerente') {window.location.replace('login.html');return;}
    S.usuario=actual;$('info-usuario').textContent=`${actual.nombre||''} ${actual.apellido||''} (Gerente)`;
    inicializarTema();conectarEventos();
    try { const verificado=await api('me'); if(verificado?.rol!=='Gerente') throw new Error('El servidor no confirmó el rol Gerente.');S.usuario=verificado;$('info-usuario').textContent=`${verificado.nombre||''} ${verificado.apellido||''} (Gerente)`; }
    catch(e) {mostrar('g-personal-alerta',`No se pudo confirmar el permiso de Gerencia: ${e.message}`,'error');document.querySelectorAll('button,input,select').forEach(n=>n.disabled=true);return;}
    sgSelect.iniciar();
    const guardada=sessionStorage.getItem('savage-gerencia-vista');cambiarVista(guardada==='reportes'?'reportes':'personal');
    await cargarPersonal();
  }
    const sgSelect = (() => {
        const controles = new WeakMap();
        let actual = null;
        let menu = null;
        let opcionesAbiertas = [];
        let indiceResaltado = -1;
        let prefijoBusqueda = '';
        let relojBusqueda;

        function crearMenu() {
            if (menu) return menu;
            menu = document.createElement('div');
            menu.id = 'sg-select-listado';
            menu.className = 'sg-select-list';
            menu.setAttribute('role', 'listbox');
            menu.setAttribute('aria-label', 'Opciones de selección');
            menu.hidden = true;
            document.body.appendChild(menu);
            return menu;
        }

        function etiquetaDe(select) {
            const etiquetas = select.labels ? Array.from(select.labels) : [];
            const etiqueta = etiquetas[0];
            if (etiqueta) return (etiqueta.textContent || '').replace(/\*/g, '').trim();
            return select.getAttribute('aria-label') || 'Seleccionar una opción';
        }

        function actualizarBoton(select) {
            const ref = controles.get(select);
            if (!ref) return;
            const opcion = select.options[select.selectedIndex];
            ref.valor.textContent = opcion?.textContent || 'Seleccioná una opción';
            ref.boton.classList.toggle('sg-select-placeholder', !select.value);
            ref.boton.disabled = select.disabled;
            ref.boton.setAttribute('aria-label', `${etiquetaDe(select)}: ${ref.valor.textContent}`);
            if (actual?.select === select && !menu.hidden) {
                actual = ref;
                mostrarOpciones();
            }
        }

        function cerrar({ devolverFoco = false } = {}) {
            if (!actual) return;
            const ref = actual;
            actual = null;
            if (menu) {
                menu.hidden = true;
                menu.replaceChildren();
            }
            opcionesAbiertas = [];
            indiceResaltado = -1;
            ref.boton.setAttribute('aria-expanded', 'false');
            ref.boton.removeAttribute('aria-activedescendant');
            if (devolverFoco && ref.boton.isConnected) ref.boton.focus();
        }

        function ubicarMenu() {
            if (!actual || !menu || menu.hidden) return;
            const r = actual.boton.getBoundingClientRect();
            if (!r.width || !r.height) { cerrar(); return; }
            const margen = 8;
            const ancho = Math.max(160, Math.min(r.width, window.innerWidth - margen * 2));
            menu.style.width = `${ancho}px`;
            const izquierdo = Math.max(margen, Math.min(r.left, window.innerWidth - ancho - margen));
            menu.style.left = `${izquierdo}px`;
            menu.style.top = `${r.bottom + 6}px`;
            menu.style.maxHeight = `${Math.min(300, Math.max(100, window.innerHeight - 24))}px`;
            const alto = menu.getBoundingClientRect().height;
            const debajo = window.innerHeight - r.bottom - 8;
            const arriba = r.top - 8;
            if (debajo < Math.min(alto, 190) && arriba > debajo) {
                menu.style.top = `${Math.max(margen, r.top - alto - 6)}px`;
            } else if (debajo < alto) {
                menu.style.maxHeight = `${Math.max(90, debajo - 6)}px`;
            }
        }

        function resaltar(indice) {
            const habilitadas = opcionesAbiertas
                .map((registro, idx) => ({ registro, idx }))
                .filter(({ registro }) => !registro.option.disabled);
            if (!habilitadas.length) return;
            const encontrada = habilitadas.find(x => x.idx === indice);
            if (!encontrada) return;
            indiceResaltado = indice;
            opcionesAbiertas.forEach(({ nodo }, idx) => {
                nodo.classList.toggle('sg-select-highlight', idx === indice);
            });
            actual.boton.setAttribute('aria-activedescendant', encontrada.registro.nodo.id);
            encontrada.registro.nodo.scrollIntoView({ block: 'nearest' });
        }

        function mostrarOpciones() {
            if (!actual) return;
            const lista = crearMenu();
            lista.replaceChildren();
            opcionesAbiertas = [];
            const opciones = Array.from(actual.select.options);
            opciones.forEach((option, index) => {
                const fila = document.createElement('div');
                fila.className = 'sg-select-option';
                fila.id = `sg-select-opcion-${index}`;
                fila.setAttribute('role', 'option');
                fila.setAttribute('aria-selected', String(option.selected));
                fila.setAttribute('aria-disabled', String(option.disabled));
                fila.textContent = option.textContent;
                fila.addEventListener('pointerdown', e => e.preventDefault());
                fila.addEventListener('click', () => elegir(index));
                lista.appendChild(fila);
                opcionesAbiertas.push({ option, nodo: fila, index });
            });
            lista.hidden = false;
            ubicarMenu();
            const seleccionado = opciones.findIndex(o => o.selected && !o.disabled);
            const primeroHabilitado = opciones.findIndex(o => !o.disabled);
            resaltar(seleccionado >= 0 ? seleccionado : primeroHabilitado);
        }

        function abrir(ref) {
            if (ref.select.disabled) return;
            if (actual === ref) { cerrar({ devolverFoco: true }); return; }
            cerrar();
            actual = ref;
            ref.boton.setAttribute('aria-expanded', 'true');
            mostrarOpciones();
        }

        function elegir(indice) {
            if (!actual) return;
            const registro = opcionesAbiertas[indice];
            if (!registro || registro.option.disabled) return;
            const { select } = actual;
            const antes = select.value;
            select.selectedIndex = indice;
            actualizarBoton(select);
            cerrar({ devolverFoco: true });
            if (select.value !== antes) {
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function recorrer(direccion) {
            if (!actual) return;
            const habilitadas = opcionesAbiertas.map((x, i) => i).filter(i => !opcionesAbiertas[i].option.disabled);
            if (!habilitadas.length) return;
            let pos = habilitadas.indexOf(indiceResaltado);
            if (pos < 0) pos = 0;
            resaltar(habilitadas[(pos + direccion + habilitadas.length) % habilitadas.length]);
        }

        function manejarTeclado(evento, ref) {
            const abierto = actual === ref;
            if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                evento.preventDefault();
                if (!abierto) abrir(ref);
                else recorrer(evento.key === 'ArrowDown' ? 1 : -1);
                return;
            }
            if (evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                if (abierto && indiceResaltado >= 0) elegir(indiceResaltado);
                else abrir(ref);
                return;
            }
            if (evento.key === 'Escape' && abierto) {
                evento.preventDefault();
                cerrar({ devolverFoco: true });
                return;
            }
            if (evento.key === 'Tab' && abierto) { cerrar(); return; }
            if (!abierto) return;
            if (evento.key === 'Home' || evento.key === 'End') {
                evento.preventDefault();
                const lista = opcionesAbiertas.map((x, i) => i).filter(i => !opcionesAbiertas[i].option.disabled);
                resaltar(evento.key === 'Home' ? lista[0] : lista.at(-1));
                return;
            }
            if (evento.key.length === 1 && !evento.ctrlKey && !evento.altKey && !evento.metaKey) {
                clearTimeout(relojBusqueda);
                prefijoBusqueda += evento.key.toLocaleLowerCase('es');
                const posicion = opcionesAbiertas.findIndex(x => !x.option.disabled &&
                    (x.option.textContent || '').trim().toLocaleLowerCase('es').startsWith(prefijoBusqueda));
                if (posicion >= 0) resaltar(posicion);
                relojBusqueda = setTimeout(() => { prefijoBusqueda = ''; }, 700);
            }
        }

        function mejorar(select) {
            if (!select || controles.has(select) || select.multiple || select.size > 1) return;
            const padre = select.parentNode;
            if (!padre) return;
            const wrapper = document.createElement('span');
            wrapper.className = 'sg-select-shell';
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'sg-select-button';
            boton.setAttribute('aria-haspopup', 'listbox');
            boton.setAttribute('aria-controls', 'sg-select-listado');
            boton.setAttribute('aria-expanded', 'false');
            const valor = document.createElement('span');
            valor.className = 'sg-select-value';
            const flecha = document.createElement('span');
            flecha.className = 'sg-select-arrow';
            flecha.setAttribute('aria-hidden', 'true');
            boton.append(valor, flecha);
            padre.insertBefore(wrapper, select);
            wrapper.append(select, boton);
            select.classList.add('sg-select-native');
            select.tabIndex = -1;
            select.setAttribute('aria-hidden', 'true');
            const ref = { select, boton, valor };
            controles.set(select, ref);
            boton.addEventListener('click', () => abrir(ref));
            boton.addEventListener('keydown', evento => manejarTeclado(evento, ref));
            select.addEventListener('change', () => actualizarBoton(select));
            select.addEventListener('invalid', evento => {
                evento.preventDefault();
                boton.focus();
                boton.setAttribute('aria-invalid', 'true');
            });
            boton.addEventListener('focus', () => {
                boton.removeAttribute('aria-invalid');
                actualizarBoton(select);
            });
            const observarOpciones = new MutationObserver(() => actualizarBoton(select));
            observarOpciones.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected', 'label', 'value'] });
            actualizarBoton(select);
        }

        function mejorarTodos(raiz = document) {
            if (raiz instanceof HTMLSelectElement) mejorar(raiz);
            if (typeof raiz.querySelectorAll === 'function') {
                raiz.querySelectorAll('select').forEach(mejorar);
            }
        }

        function iniciar() {
            mejorarTodos();
            crearMenu();
            const observador = new MutationObserver(cambios => {
                for (const cambio of cambios) {
                    for (const nodo of cambio.addedNodes) {
                        if (nodo.nodeType === Node.ELEMENT_NODE) mejorarTodos(nodo);
                    }
                }
            });
            observador.observe(document.body, { childList: true, subtree: true });
            document.addEventListener('pointerdown', evento => {
                if (actual && !actual.boton.contains(evento.target) && !menu.contains(evento.target)) cerrar();
            }, true);
            document.addEventListener('click', evento => {
                const etiqueta = evento.target.closest?.('label[for]');
                if (!etiqueta) return;
                const select = document.getElementById(etiqueta.htmlFor);
                const ref = select ? controles.get(select) : null;
                if (!ref) return;
                evento.preventDefault();
                ref.boton.focus();
                abrir(ref);
            });
            document.addEventListener('reset', () => setTimeout(() => {
                document.querySelectorAll('select.sg-select-native').forEach(actualizarBoton);
            }, 0), true);
            window.addEventListener('resize', ubicarMenu);
            window.addEventListener('scroll', ubicarMenu, true);
            document.addEventListener('focusin', evento => {
                if (actual && !actual.boton.contains(evento.target) && !menu.contains(evento.target)) cerrar();
            });
        }

        return { iniciar, actualizar: () => document.querySelectorAll('select.sg-select-native').forEach(actualizarBoton) };
    })();
  document.addEventListener('DOMContentLoaded',iniciar);

})();
