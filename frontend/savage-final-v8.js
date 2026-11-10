/* Savage Grill · consolidación visual v8. No altera los montos ni confirma pagos por fuera de la API. */
(()=>{'use strict';
  const $=id=>document.getElementById(id);
  const api=(window.SAVAGE_CONFIG?.API_BASE_URL||'http://localhost:8080/api/v1').replace(/\/+$/,'');
  const money=v=>{
    if(v==null||v==='')return '—';
    let s=String(v).trim().replace(/,/g,'.');if(!/^-?\d+(?:\.\d+)?$/.test(s))return String(v);
    const neg=s.startsWith('-');s=s.replace(/^-/,'');let [ent,dec='']=s.split('.');
    // El redondeo es únicamente de presentación; la API conserva su Decimal original.
    const digits=dec.padEnd(3,'0');const cent=(+digits.slice(0,2))+(+digits[2]>=5?1:0);
    const entero=(BigInt(ent||'0')+(cent===100?1n:0n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g,'.');
    return (neg?'-':'')+'$'+entero+','+String(cent%100).padStart(2,'0');
  };
  const svg=(n)=>{
   const g={chevron:'<path d="m6 9 6 6 6-6"/>',back:'<path d="m15 18-6-6 6-6"/>',card:'<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>'};
   return `<svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${g[n]||g.chevron}</svg>`;
  };
  function customSelects(){
    for(const select of document.querySelectorAll('body.sg-cobros-portal select:not([data-sg8-select])')){
      if(!select.options.length)continue;
      select.dataset.sg8Select='1';
      const wrap=document.createElement('span');wrap.className='sg-select-v8';wrap.dataset.open='false';
      select.parentNode.insertBefore(wrap,select);wrap.append(select);
      const trigger=document.createElement('button');trigger.type='button';trigger.className='sg-select-trigger-v8';
      trigger.setAttribute('aria-label',(select.closest('label')?.firstChild?.textContent||select.getAttribute('aria-label')||'Seleccionar opción').trim());
      trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-expanded','false');
      const txt=document.createElement('span'),arrow=document.createElement('span');arrow.innerHTML=svg('chevron');trigger.append(txt,arrow);
      const list=document.createElement('div');list.className='sg-select-list-v8';list.setAttribute('role','listbox');list.tabIndex=-1;
      wrap.append(trigger,list);
      let focusIndex=-1;
      const close=()=>{wrap.dataset.open='false';trigger.setAttribute('aria-expanded','false');};
      const render=()=>{
        txt.textContent=select.options[select.selectedIndex]?.textContent || 'Seleccionar';
        list.replaceChildren();
        [...select.options].forEach((o,i)=>{
          const b=document.createElement('button');b.type='button';b.className='sg-select-option-v8';b.setAttribute('role','option');b.setAttribute('aria-selected',String(select.selectedIndex===i));b.textContent=o.textContent;
          b.disabled=o.disabled;b.tabIndex=select.selectedIndex===i?0:-1;
          b.addEventListener('click',()=>{if(o.disabled)return;select.value=o.value;select.dispatchEvent(new Event('change',{bubbles:true}));render();close();trigger.focus();});list.append(b);
        });
      };
      render();select.addEventListener('change',render);
      trigger.addEventListener('click',()=>{const opening=wrap.dataset.open!=='true';document.querySelectorAll('.sg-select-v8[data-open="true"]').forEach(w=>{w.dataset.open='false';w.querySelector('.sg-select-trigger-v8')?.setAttribute('aria-expanded','false');});wrap.dataset.open=String(opening);trigger.setAttribute('aria-expanded',String(opening));if(opening){focusIndex=select.selectedIndex;const opts=[...list.querySelectorAll('.sg-select-option-v8')];opts[focusIndex]?.focus();}});
      wrap.addEventListener('keydown',e=>{
        if(e.key==='Escape'){close();trigger.focus();e.preventDefault();return;}
        if(wrap.dataset.open!=='true')return;
        if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
          const opts=[...list.querySelectorAll('.sg-select-option-v8')].filter(o=>!o.disabled);if(!opts.length)return;
          let i=opts.indexOf(document.activeElement);
          i=e.key==='Home'?0:e.key==='End'?opts.length-1:e.key==='ArrowDown'?(i+1)%opts.length:(i-1+opts.length)%opts.length;
          opts[i].focus();e.preventDefault();
        }
        if(e.key==='Enter'||e.key===' '){if(document.activeElement?.classList.contains('sg-select-option-v8')){document.activeElement.click();e.preventDefault();}}
      });
      document.addEventListener('click',e=>{if(!wrap.contains(e.target))close();});
    }
  }
  function catalogHead(){
    const header=document.querySelector('body:not(.sg-cobros-portal) header.sg-header');
    const brand=header?.querySelector('.logo-restaurante');const actions=header?.querySelector('.sg-header-actions');
    if(!brand||!actions||!$('txt-nro-mesa')||!document.querySelector('.sg-salir-cliente'))return;
    header.classList.add('sg8-catalog-head');
    const left=document.createElement('div'),mid=document.createElement('div'),right=document.createElement('div');
    left.className='sg8-catalog-left';mid.className='sg8-catalog-center';right.className='sg8-catalog-right';
    const exit=actions.querySelector('.sg-salir-cliente'),theme=actions.querySelector('[data-savage-theme]'),badge=actions.querySelector('.sg-mesa-badge');
    left.append(exit);if(theme)left.append(theme);mid.append(brand);if(badge)mid.append(badge);
    const pay=document.createElement('a');pay.href='mi-cuenta.html';pay.className='sg8-pay-link';pay.textContent='Pagar';pay.setAttribute('aria-label','Ver cuenta y elegir pago');right.append(pay);
    header.replaceChildren(left,mid,right);
  }
  function toServerNotice(method){
    const mesa=Number(sessionStorage.getItem('savage-mesa-numero'));const pin=sessionStorage.getItem('savage-mesa-pin');
    if(!Number.isSafeInteger(mesa)||!/^\d{4}$/.test(pin||''))return Promise.reject(new Error('Entrá con el PIN de tu mesa para solicitar la cuenta.'));
    // La API marca "solicita cuenta"; todavía no persiste el medio elegido.
    return fetch(api+'/solicitar-cuenta',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({numero_mesa:mesa,pin})}).then(async r=>{
      if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.error||d.detail||'No se pudo avisar al mozo.');}
      return method;
    });
  }
  function cliente(){
    const result=$('resultado-cliente'),form=$('form-cliente'),choose=$('sg-elegir-pago-v8'),actions=$('acciones-cliente'),dlg=$('sg-mp-dialog-v8');
    if(!choose||!form||!actions||!dlg)return;
    const update=()=>{
      const identificado=!result.hidden;
      document.body.classList.toggle('sg-cliente-identificado-v8',identificado);
      choose.hidden=!identificado;const seguimiento=$('sg-estado-pago-v8');if(seguimiento)seguimiento.hidden=!identificado;
    };
    const obs=new MutationObserver(update);obs.observe(result,{attributes:true,attributeFilter:['hidden']});update();
    document.querySelectorAll('[data-sg-tipo]').forEach(b=>b.addEventListener('click',async()=>{
      const tipo=b.dataset.sgTipo,alerta=$('sg-pago-aviso-v8');alerta.textContent='';
      if(tipo==='mp'){
        if(actions.hidden){alerta.textContent='Todavía no se puede iniciar el pago. Los pedidos deben estar listos y la caja abierta.';return;}
        dlg.showModal();return;
      }
      const titulo={efectivo:'efectivo',tarjeta:'tarjeta',transferencia:'transferencia'}[tipo]||'el medio elegido';
      b.disabled=true;
      try{await toServerNotice(titulo);
        alerta.textContent=`Se avisó al mozo que querés pagar. Comentale que elegiste ${titulo}. El pago se registrará cuando el personal confirme la operación.`;
      }catch(e){alerta.textContent=e.message||'No se pudo enviar el aviso.';}
      finally{b.disabled=false;}
    }));
    $('sg-cerrar-mp-v8')?.addEventListener('click',()=>dlg.close());
    dlg.addEventListener('click',e=>{if(e.target===dlg)dlg.close();});
    // Si se abrió desde el PIN, los datos ya se precargan por savage-cobros.js.
  }
  function staffRates(){
    const dst=$('sg-cotizaciones-personal');if(!dst)return;
    const show=async()=>{
      try{
        const r=await fetch(api+'/cotizaciones',{headers:{Accept:'application/json'},cache:'no-store'});
        if(!r.ok)throw new Error('No disponibles');const d=await r.json();dst.replaceChildren();
        const vals=Array.isArray(d.cotizaciones)?d.cotizaciones:[];
        for(const code of ['ARS','USD','BRL','PYG']){
          const item=code==='ARS'?{valor:'1.00'}:(vals.find(x=>x.moneda===code)||{});const el=document.createElement('div');el.className='sg-rate-v8';
          const head=document.createElement('small'),price=document.createElement('strong'),note=document.createElement('em');
          head.textContent=code==='ARS'?'Peso argentino (ARS)':code==='USD'?'Dólar (USD)':code==='BRL'?'Real (BRL)':'Guaraní (PYG)';price.textContent=money(item.valor);note.textContent=code==='ARS'?'Moneda base':'Pesos argentinos por 1 unidad';el.append(head,price,note);dst.append(el);
        }
      }catch{dst.textContent='No pudimos consultar las cotizaciones. Intentá nuevamente.';}
    };
    document.querySelector('[data-sg-panel="caja"]')?.addEventListener('click',()=>setTimeout(show,120));
    $('cotizacion-actualizar')?.addEventListener('click',()=>setTimeout(show,1300));
    show();
  }
  function fechaBonita(iso){try{const d=new Date(iso);return Number.isNaN(d.getTime())?String(iso||'—'):d.toLocaleString('es-AR',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});}catch{return String(iso||'—');}}
  function staffCaja(){
    const el=$('caja-estado');if(!el)return;
    const observer=new MutationObserver(()=>{
      if(el.dataset.sg8Update==='1')return;
      const rows=[...el.querySelectorAll('.fila-dato')];
      let edited=false;
      for(const row of rows){const label=row.querySelector('span'),value=row.querySelector('strong');if(!label||!value)continue;
        if(label.textContent.trim()==='Apertura'&&value.textContent.includes('T')){value.textContent=fechaBonita(value.textContent);edited=true;}
        if(label.textContent.trim()==='Arqueo esperado'&&value.textContent.trim().startsWith('{')){
          // El texto del JS original está truncado: lo ocultamos antes que mostrar JSON ilegible.
          label.textContent='Arqueo';value.textContent='Consultá el detalle al cerrar caja';edited=true;
        }
      }
      if(edited){el.dataset.sg8Update='1';queueMicrotask(()=>{delete el.dataset.sg8Update;});}
    });
    observer.observe(el,{childList:true,subtree:true});
  }
  function staff(){customSelects();staffRates();staffCaja();}
  function init(){
    const portal=document.body.dataset.sgPortal;
    if(portal==='personal')staff();else if(portal==='cliente'){customSelects();cliente();}
    else if(location.pathname.endsWith('/catalogo.html'))catalogHead();
    // Remove stray interface-only wording about cutlery from unrelated surfaces.
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
