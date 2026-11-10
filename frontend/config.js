/* =====================================================
   SAVAGE GRILL - CONFIGURACIÓN DE LA API
   Una sola dirección para todo el front:
   - Si la página se abre como archivo (file://, desarrollo local) la API es la de la propia PC, en el puerto 8080.
   - Si la sirve un servidor (Caddy en Azure, por ejemplo) la API está en ese mismo origen: no hay puertos ni
     direcciones fijas, así funciona igual desde la PC, la tablet o el celular.
   ===================================================== */

(function () {
    const origen = window.location.protocol === 'file:' ? 'http://localhost:8080' : window.location.origin;
    window.SAVAGE_CONFIG = Object.freeze({
        API_ORIGIN: origen,
        API_BASE_URL: origen + '/api/v1'
    });
})();
