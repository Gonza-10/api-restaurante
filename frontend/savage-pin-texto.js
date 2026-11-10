/* Sustituye un mensaje tecnico del acceso de mesa sin cambiar su validacion. */
(function(){
  const cambio='Tu experiencia Savage Grill empieza acá.';
  function actualizar(){
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    let nodo;
    while((nodo=walker.nextNode())) {
      if(nodo.nodeValue.includes('Sistema conectado al servidor local')) {
        nodo.nodeValue=nodo.nodeValue.replaceAll('Sistema conectado al servidor local',cambio);
      }
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',actualizar);else actualizar();
})();
