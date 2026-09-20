/* ==========================================================================
   LÓGICA DEL CLIENTE WEB (ASINCRONÍA Y FETCH API) - PyLP III
   Módulo de Autogestión y Catálogo de Productos
   ========================================================================== */

const API_URL = 'http://localhost:8080/api/v1/productos';

const contenedorLista = document.getElementById('listado');
const alertaError = document.getElementById('caja-error');
const alertaExito = document.getElementById('caja-exito');
const formulario = document.getElementById('formulario-registro');

/**
 * Asigna dinámicamente una imagen según palabras clave en el nombre del producto.
 */
function obtenerImagenPorNombre(nombre) {
    const nombreMin = nombre.toLowerCase();
    
    if (nombreMin.includes('milanesa')) return 'https://marubotana.tv/uploads/2026/03/milanesa-napolitana.webp';
    if (nombreMin.includes('pizza')) return 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=500&q=80';
    if (nombreMin.includes('hamburguesa') || nombreMin.includes('burger')) return 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=500&q=80';
    if (nombreMin.includes('galeto') || nombreMin.includes('pollo')) return 'https://images.unsplash.com/photo-1598514982205-f36b96d1e8d4?auto=format&fit=crop&w=500&q=80';
    if (nombreMin.includes('pasta') || nombreMin.includes('fideo')) return 'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=500&q=80';
    if (nombreMin.includes('ensalada')) return 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=500&q=80';
    if (nombreMin.includes('picada') || nombreMin.includes('tabla')) return 'https://picadasxl.com/wp-content/uploads/2024/08/inicio.png';
    
    // Foto por defecto
    return 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=500&q=80'; 
}

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
            contenedorLista.innerHTML = '<p style="color: var(--text-muted); font-size: 14px;">No hay registros almacenados en la base de datos.</p>';
            return;
        }

        items.forEach(item => {
            const tarjeta = document.createElement('div');
            tarjeta.className = 'product-card';
            tarjeta.innerHTML = `
                <img src="${obtenerImagenPorNombre(item.nombre)}" 
                     alt="${item.nombre}" 
                     style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                <div style="display: flex; flex-direction: column; flex-grow: 1;">
                    <span style="color: var(--primary-orange); font-size: 12px; font-weight: 700; text-transform: uppercase;">Destacado</span>
                    <h3 style="color: var(--text-main); font-size: 18px; margin: 4px 0 12px 0;">${item.nombre}</h3>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
                        <span style="font-size: 20px; font-weight: 800; color: var(--text-main);">$${parseFloat(item.precio).toFixed(2)}</span>
                        <button class="btn-orange" title="Agregar al carrito">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                        </button>
                    </div>
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
            
            const nuevaTarjeta = document.createElement('div');
            nuevaTarjeta.className = 'product-card';
            nuevaTarjeta.innerHTML = `
                <img src="${obtenerImagenPorNombre(resultado.nombre)}" 
                     alt="${resultado.nombre}" 
                     style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                <div style="display: flex; flex-direction: column; flex-grow: 1;">
                    <span style="color: var(--primary-orange); font-size: 12px; font-weight: 700; text-transform: uppercase;">Nuevo</span>
                    <h3 style="color: var(--text-main); font-size: 18px; margin: 4px 0 12px 0;">${resultado.nombre}</h3>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
                        <span style="font-size: 20px; font-weight: 800; color: var(--text-main);">$${parseFloat(resultado.precio).toFixed(2)}</span>
                        <button class="btn-orange" title="Agregar al carrito">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
            
            contenedorLista.prepend(nuevaTarjeta);
            
        } else if (respuesta.status === 400) {
            alertaError.textContent = resultado.error || 'Datos inválidos.';
            alertaError.style.display = 'flex';
        } else {
            alertaError.textContent = 'Error desconocido en el servidor.';
            alertaError.style.display = 'flex';
        }
    } catch (error) {
        alertaError.textContent = 'Fallo de conexión de red o servidor inactivo.';
        alertaError.style.display = 'flex';
    }
});

obtenerRegistros();