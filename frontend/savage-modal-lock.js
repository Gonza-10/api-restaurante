/* Savage Grill · Bloqueo de desplazamiento cuando hay un modal.
   No reemplaza ni modifica la lógica de los formularios, las APIs o las sesiones.
   Mantiene el scroll interno de cada diálogo y restaura la posición del fondo. */
(() => {
    'use strict';
    if (window.SavageModalLock) return;

    // Solo capas realmente modales; los dropdowns, el calendario y los avisos
    // pequeños no deben congelar la pantalla al abrirse.
    const CAPAS = [
        '#modal-abrir', '#modal-pedidos', '#modal-aviso', '#modal-confirmar-cierre',
        '#modal-editar-plato', '#modal-mesa', '#modal-detalle', '#modal-editar',
        '#admin-confirmacion', '#g-modal-editar', '#g-modal-confirmar',
        '#cocina-modal-salida'
    ];
    const SELECTOR = CAPAS.join(', ');
    let bloqueado = false;
    let scrollGuardado = 0;
    let observador = null;

    function visible(capa) {
        if (!capa.isConnected || capa.hidden) return false;
        // Oculta también las capas que viven en una sección invisible.
        const estilo = window.getComputedStyle(capa);
        return estilo.display !== 'none' && estilo.visibility !== 'hidden' &&
            capa.getClientRects().length > 0;
    }

    function sincronizar() {
        if (!document.body) return;
        const hayModal = [...document.querySelectorAll(SELECTOR)].some(visible);
        if (hayModal === bloqueado) return;
        if (hayModal) {
            // Guardar el punto exacto del documento ANTES de fijar el body.
            scrollGuardado = window.scrollY || document.documentElement.scrollTop || 0;
            document.body.style.setProperty('--sg-modal-offset', `-${scrollGuardado}px`);
            document.documentElement.classList.add('sg-modal-lock');
            document.body.classList.add('sg-modal-lock');
            bloqueado = true;
        } else {
            // Soltar la página solo cuando se cerraron TODAS las capas (modales anidados).
            document.body.classList.remove('sg-modal-lock');
            document.documentElement.classList.remove('sg-modal-lock');
            document.body.style.removeProperty('--sg-modal-offset');
            bloqueado = false;
            window.scrollTo(0, scrollGuardado);
        }
    }

    function iniciar() {
        if (!document.body || observador) return;
        observador = new MutationObserver(cambios => {
            // Sincronizar solamente cuando cambian capas modales, o se monta una
            // capa nueva. Evita hacer trabajo por cada actualización de las comandas.
            const relevante = cambios.some(c => {
                if (c.type === 'attributes') return c.target.matches?.(SELECTOR);
                return [...c.addedNodes, ...c.removedNodes].some(n => n.nodeType === 1 &&
                    (n.matches?.(SELECTOR) || n.querySelector?.(SELECTOR)));
            });
            if (relevante) sincronizar();
        });
        observador.observe(document.body, {
            subtree:true, childList:true, attributes:true,
            attributeFilter:['hidden','style','class','aria-hidden']
        });
        sincronizar();
        // Resguardo para navegación con historial de navegador / pestaña reanudada.
        window.addEventListener('pageshow', sincronizar);
        window.addEventListener('pagehide', () => {
            if (!bloqueado) return;
            document.body.classList.remove('sg-modal-lock');
            document.documentElement.classList.remove('sg-modal-lock');
            document.body.style.removeProperty('--sg-modal-offset');
            bloqueado = false;
        });
    }
    if (document.readyState === 'loading')
        document.addEventListener('DOMContentLoaded', iniciar, {once:true});
    else iniciar();
    window.SavageModalLock = {sincronizar, activo:()=>bloqueado};
})();
