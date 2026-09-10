/* ==========================================================================
   LÓGICA DEL CLIENTE WEB (ASINCRONÍA Y FETCH API) - PyLP III
   ========================================================================== */

const API_URL = 'http://localhost:8080/api/v1/productos';

const contenedorLista = document.getElementById('listado');
const alertaError = document.getElementById('caja-error');
const alertaExito = document.getElementById('caja-exito');
const formulario = document.getElementById('formulario-registro');

function limpiarAlertas() {
    alertaError.style.display = 'none';
    alertaExito.style.display = 'none';
}

async function obtenerRegistros() {
    try {
        const respuesta = await fetch(API_URL);
        if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);

        const items = await respuesta.json();
        contenedorLista.innerHTML = '';

        if (items.length === 0) {
            contenedorLista.innerHTML = '<p style="color: var(--text-muted); font-size: 14px;">No hay registros almacenados.</p>';
            return;
        }

        items.forEach(item => {
            const tarjeta = document.createElement('div');
            tarjeta.className = 'product-item';
            tarjeta.innerHTML = `
                <div class="prod-info">
                    <p>ID #${item.id}</p>
                    <h3>${item.nombre}</h3>
                </div>
                <div class="prod-price">
                    $${item.precio.toFixed(2)}
                </div>
            `;
            contenedorLista.appendChild(tarjeta);
        });
    } catch (error) {
        contenedorLista.innerHTML = '<p style="color: var(--error); font-size: 14px;">Fallo de conexión con el servidor.</p>';
    }
}

formulario.addEventListener('submit', async (e) => {
    e.preventDefault(); 
    limpiarAlertas();

    const nombre = document.getElementById('campo-nombre').value.trim(); 
    const precio = parseFloat(document.getElementById('campo-precio').value); 
    const payload = { nombre: nombre, precio: precio };

    try {
        const respuesta = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const resultado = await respuesta.json();

        if (respuesta.status === 201) {
            alertaExito.textContent = `Guardado con éxito (ID #${resultado.id})`;
            alertaExito.style.display = 'flex';
            formulario.reset();
            obtenerRegistros(); 
        } else if (respuesta.status === 400) {
            // ACÁ ATRAPAMOS LA VALIDACIÓN DEL BACKEND (PRECIO <= 0)
            alertaError.textContent = resultado.error || 'Datos inválidos.';
            alertaError.style.display = 'flex';
        } else {
            alertaError.textContent = 'Error desconocido en el servidor.';
            alertaError.style.display = 'flex';
        }
    } catch (error) {
        alertaError.textContent = 'Fallo de conexión. ¿Está encendido SERV_WEB.py?';
        alertaError.style.display = 'flex';
    }
});

obtenerRegistros();