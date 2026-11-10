/* Savage Grill · Gerencia mobile: menú accesible, tema compartido, sin tocar API ni empleados. */
(() => {
'use strict';
function iniciar(){
 const sidebar=document.getElementById('g-nav-drawer');
 const open=document.getElementById('g-menu-open');
 const close=document.getElementById('g-menu-close');
 const backdrop=document.getElementById('g-mobile-overlay');
 const view=document.getElementById('g-mobile-view');
 const theme=document.querySelector('[data-savage-theme]');
 const mobile=document.getElementById('g-theme-mobile-slot');
 const desktop=document.getElementById('g-theme-desktop-slot');
 if(![sidebar,open,close,backdrop,view,theme,mobile,desktop].every(Boolean))return;
 const media=window.matchMedia('(max-width:1100px)');
 let wasOpen=false, previousFocus=null;
 const options=sidebar.querySelectorAll('[data-vista],#g-ir-admin');
 function updateView(){
   const active=sidebar.querySelector('[data-vista].active');
   view.textContent=active?.textContent?.trim()||'Gestión de personal';
 }
 function openDrawer(value,{returnFocus=true}={}){
   wasOpen=Boolean(value&&media.matches);
   document.body.classList.toggle('g-nav-open',wasOpen);
   backdrop.hidden=!wasOpen;
   open.setAttribute('aria-expanded',String(wasOpen));
   sidebar.setAttribute('aria-hidden',String(media.matches&&!wasOpen));
   if('inert' in sidebar)sidebar.inert=Boolean(media.matches&&!wasOpen);
   if(wasOpen){previousFocus=document.activeElement;close.focus();}
   else if(returnFocus&&previousFocus&&media.matches){(previousFocus.isConnected?previousFocus:open).focus();previousFocus=null;}
 }
 function relocateTheme(){
   if(media.matches){mobile.appendChild(theme);}else{desktop.appendChild(theme);}
   window.SavageTheme?.montar?.();
 }
 open.addEventListener('click',()=>openDrawer(true));
 close.addEventListener('click',()=>openDrawer(false));
 backdrop.addEventListener('click',()=>openDrawer(false));
 options.forEach(el=>el.addEventListener('click',()=>{updateView();openDrawer(false,{returnFocus:false});}));
 document.addEventListener('keydown',event=>{
   if(!wasOpen)return;
   if(event.key==='Escape'){event.preventDefault();openDrawer(false);}
   if(event.key==='Tab'){
     const nodes=[...sidebar.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])')]
       .filter(el=>el.getClientRects().length && el.offsetParent!==null && !el.hidden);
     const first=nodes[0],last=nodes[nodes.length-1];
     if(!first)return;
     if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
     if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
   }
 });
 function updateMedia(){openDrawer(false,{returnFocus:false});relocateTheme();updateView();}
 if(media.addEventListener)media.addEventListener('change',updateMedia);
 else media.addListener(updateMedia);
 const observer=new MutationObserver(updateView);
 sidebar.querySelectorAll('[data-vista]').forEach(el=>observer.observe(el,{attributes:true,attributeFilter:['class']}));
 relocateTheme();updateView();openDrawer(false,{returnFocus:false});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',iniciar,{once:true});
else iniciar();
})();
