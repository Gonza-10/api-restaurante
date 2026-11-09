/* Savage Grill — calendario para campos de fecha del sistema.
   Mantiene intactos los input[type=date] y sus valores ISO YYYY-MM-DD,
   ocultando SOLO su aspecto nativo; así funcionan consultas, formularios,
   validaciones y los bloques que se crean dinámicamente. */
(() => {
  'use strict';
  if (window.SavageCalendario) return;
  const controles = new WeakMap();
  let abierto = null;
  let popup = null;
  let mes = null;
  const formatoISO = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const parseISO = s => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
    if (!m) return null;
    const d = new Date(+m[1], +m[2]-1, +m[3]);
    return d.getFullYear()===+m[1] && d.getMonth()===+m[2]-1 && d.getDate()===+m[3] ? d : null;
  };
  const etiqueta = d => d.toLocaleDateString('es-AR', {day:'numeric',month:'long',year:'numeric'});
  const hoy = () => new Date();
  function limite(ref, fecha) {
    const min = parseISO(ref.input.min);
    const max = parseISO(ref.input.max);
    const d = formatoISO(fecha);
    return (!min || d>=formatoISO(min)) && (!max || d<=formatoISO(max));
  }
  function sincronizar(ref) {
    const d = parseISO(ref.input.value);
    ref.label.textContent = d ? etiqueta(d) : 'Seleccioná una fecha';
    ref.boton.classList.toggle('sg-cal-vacio', !d);
    ref.boton.disabled = ref.input.disabled;
    ref.boton.setAttribute('aria-label', d ? `Fecha: ${etiqueta(d)}. Cambiar` : 'Elegir fecha');
  }
  function actualizar() {
    document.querySelectorAll('input.sg-cal-native').forEach(input => {
      const ref = controles.get(input);
      if (ref) sincronizar(ref);
    });
  }
  function cerrar(devolverFoco=false) {
    if (!abierto) return;
    const ref = abierto;
    abierto = null;
    popup.hidden = true;
    ref.boton.setAttribute('aria-expanded', 'false');
    if (devolverFoco && document.contains(ref.boton)) ref.boton.focus();
  }
  function posicionar() {
    if (!abierto || popup.hidden || !document.contains(abierto.boton)) {cerrar();return;}
    const rect=abierto.boton.getBoundingClientRect();
    const width=Math.min(356,window.innerWidth-24);
    popup.style.width=width+'px';
    let left=Math.min(Math.max(12,rect.left),window.innerWidth-width-12);
    const alto=Math.min(popup.offsetHeight,window.innerHeight-24);
    const bottom=window.innerHeight-rect.bottom;
    let top=bottom>=alto+10 || rect.top<alto+10 ? rect.bottom+8 : rect.top-alto-8;
    top=Math.max(12,Math.min(top,window.innerHeight-alto-12));
    popup.style.left=Math.max(12,left)+'px';
    popup.style.top=top+'px';
  }
  function cambiarMes(delta) {mes=new Date(mes.getFullYear(),mes.getMonth()+delta,1);dibujar();}
  function seleccionar(d) {
    if (!abierto || !limite(abierto,d)) return;
    const input = abierto.input;
    const nuevo = formatoISO(d);
    const cambio = input.value !== nuevo;
    input.value = nuevo;
    sincronizar(abierto);
    cerrar(true);
    if (cambio) {
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
    }
  }
  function boton(texto,clase,onClick) {
    const b=document.createElement('button');b.type='button';b.className=clase;b.textContent=texto;b.addEventListener('click',onClick);return b;
  }
  function dibujar() {
    if (!abierto) return;
    popup.replaceChildren();
    const header=document.createElement('div');header.className='sg-je-calendar-top';
    const previo=boton('‹','sg-je-cal-arrow',()=>cambiarMes(-1));previo.setAttribute('aria-label','Mes anterior');
    const titulo=document.createElement('div');titulo.className='sg-je-calendar-title';const nombreMes=mes.toLocaleDateString('es-AR',{month:'long',year:'numeric'});titulo.textContent=nombreMes[0].toUpperCase()+nombreMes.slice(1);titulo.setAttribute('aria-live','polite');
    const sig=boton('›','sg-je-cal-arrow',()=>cambiarMes(1));sig.setAttribute('aria-label','Mes siguiente');
    header.append(previo,titulo,sig);popup.append(header);
    const dias=document.createElement('div');dias.className='sg-je-cal-days';
    ['L','M','M','J','V','S','D'].forEach((dia,i)=>{const sp=document.createElement('span');sp.className='sg-je-cal-weekday';sp.textContent=dia;sp.setAttribute('aria-label',['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'][i]);dias.append(sp);});
    popup.append(dias);
    const grid=document.createElement('div');grid.className='sg-je-cal-grid';
    const desplazamiento=(new Date(mes.getFullYear(),mes.getMonth(),1).getDay()+6)%7;
    const selected=parseISO(abierto.input.value);
    const val=selected?formatoISO(selected):'';
    const fechaHoy=formatoISO(hoy());
    for(let i=0;i<42;i++) {
      const d=new Date(mes.getFullYear(),mes.getMonth(),i-desplazamiento+1);
      const clave=formatoISO(d);
      const b=boton(String(d.getDate()),'sg-je-cal-day',()=>seleccionar(d));
      b.dataset.fecha=clave;
      b.setAttribute('aria-label',etiqueta(d));
      b.setAttribute('aria-pressed',String(clave===val));
      if (d.getMonth()!==mes.getMonth()) b.classList.add('otra-mes');
      if (clave===val) b.classList.add('elegido');
      if (clave===fechaHoy) b.classList.add('hoy');
      if (!limite(abierto,d)) b.disabled=true;
      grid.append(b);
    }
    popup.append(grid);
    const actions=document.createElement('div');actions.className='sg-je-cal-actions';
    actions.append(boton('Borrar fecha','',()=>{
      const input=abierto.input, cambiada=!!input.value;
      input.value='';sincronizar(abierto);cerrar(true);
      if (cambiada){input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}
    }),boton('Ir a hoy','',()=>{const d=hoy();mes=new Date(d.getFullYear(),d.getMonth(),1);dibujar();posicionar();popup.querySelector(`[data-fecha="${formatoISO(d)}"]`)?.focus();}));
    popup.append(actions);
    requestAnimationFrame(posicionar);
  }
  function abrir(ref) {
    if (ref.input.disabled) return;
    if(abierto===ref){cerrar();return;}
    cerrar();abierto=ref;const d=parseISO(ref.input.value)||hoy();
    mes=new Date(d.getFullYear(),d.getMonth(),1);
    popup.hidden=false;ref.boton.setAttribute('aria-expanded','true');
    dibujar();
    requestAnimationFrame(()=>popup.querySelector(`[data-fecha="${formatoISO(d)}"]`)?.focus());
  }
  function mejorar(input) {
    if (controles.has(input) || input.dataset.sgCalendarIgnore==='true') return;
    if (!input.parentNode) return;
    const shell=document.createElement('div');shell.className='sg-cal-shell';
    const b=document.createElement('button');b.type='button';b.className='sg-cal-btn';
    b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-expanded','false');b.setAttribute('aria-controls','sg-global-calendar');
    const sp=document.createElement('span');sp.className='sg-cal-label';
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('width','18');svg.setAttribute('height','18');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','2');svg.setAttribute('aria-hidden','true');
    const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d','M7 2v4M17 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z');svg.append(p);
    b.append(sp,svg);
    input.parentNode.insertBefore(shell,input);shell.append(input,b);
    input.classList.add('sg-cal-native');input.setAttribute('aria-hidden','true');input.tabIndex=-1;
    const ref={input,boton:b,label:sp};controles.set(input,ref);
    input.addEventListener('change',()=>sincronizar(ref));
    input.addEventListener('input',()=>sincronizar(ref));
    b.addEventListener('click',()=>abrir(ref));
    const etiquetaPadre=document.querySelector(`label[for="${CSS.escape(input.id||'__sin_id__')}"]`);
    if(etiquetaPadre) etiquetaPadre.addEventListener('click',e=>{e.preventDefault();abrir(ref);});
    sincronizar(ref);
  }
  function mejorarTodos(root=document){
    if(root instanceof HTMLInputElement && root.type==='date')mejorar(root);
    if(root.querySelectorAll)root.querySelectorAll('input[type="date"]').forEach(mejorar);
  }
  function iniciar(){
    popup=document.createElement('div');popup.id='sg-global-calendar';popup.className='sg-global-calendar';popup.setAttribute('role','dialog');popup.setAttribute('aria-label','Seleccionar fecha');popup.setAttribute('aria-modal','false');popup.hidden=true;document.body.append(popup);
    mejorarTodos();
    const obs=new MutationObserver(ms=>{for(const m of ms)for(const n of m.addedNodes)if(n.nodeType===1)mejorarTodos(n);});
    obs.observe(document.body,{childList:true,subtree:true});
    document.addEventListener('pointerdown',e=>{if(abierto && !popup.contains(e.target) && !abierto.boton.contains(e.target))cerrar();},true);
    document.addEventListener('keydown',e=>{
      if(!abierto)return;
      if(e.key==='Escape'){e.preventDefault();cerrar(true);return;}
      if(!popup.contains(document.activeElement))return;
      const offset=({'ArrowLeft':-1,'ArrowRight':1,'ArrowUp':-7,'ArrowDown':7})[e.key];
      if(offset==null)return;
      const d=parseISO(document.activeElement.dataset?.fecha||'');if(!d)return;
      e.preventDefault();d.setDate(d.getDate()+offset);
      if(d.getMonth()!==mes.getMonth()){mes=new Date(d.getFullYear(),d.getMonth(),1);dibujar();}
      popup.querySelector(`[data-fecha="${formatoISO(d)}"]`)?.focus();
    });
    window.addEventListener('resize',posicionar);
    window.addEventListener('scroll',()=>{if(abierto)posicionar();},true);
    document.addEventListener('reset',()=>setTimeout(actualizar,0),true);
  }
  window.SavageCalendario={actualizar,mejorarTodos,cerrar};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',iniciar,{once:true});else iniciar();
})();
