/* ==========================================================================
   LÓGICA DEL CLIENTE WEB (ASINCRONÍA Y FETCH API) - PyLP III
   Módulo de Autogestión y Catálogo de Productos
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

function obtenerImagenPorNombre(nombre) {
    const n = nombre.toLowerCase();
    if (n.includes('milanesa')) return 'https://marubotana.tv/uploads/2026/03/milanesa-napolitana.webp';
    if (n.includes('pizza')) return 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=500&q=80';
    if (n.includes('hamburguesa') || n.includes('burger')) return 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=500&q=80';
    if (n.includes('galeto') || n.includes('pollo')) return 'https://images.unsplash.com/photo-1598514982205-f36b96d1e8d4?auto=format&fit=crop&w=500&q=80';
    if (n.includes('pasta') || n.includes('fideo')) return 'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=500&q=80';
    if (n.includes('ensalada')) return 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=500&q=80';
    if (n.includes('picada') || n.includes('tabla')) return 'https://images.unsplash.com/photo-1602928321679-560bb453f190?auto=format&fit=crop&w=500&q=80';
    return 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=500&q=80'; 
}

function obtenerDetallesPorNombre(nombre) {
    const n = nombre.toLowerCase();
    if (n.includes('milanesa')) return { desc: 'Milanesa de ternera gratinada con mozzarella, salsa de tomate y guarnición.', tiempo: '25 min' };
    if (n.includes('pizza')) return { desc: 'Masa madre a la piedra, salsa natural, mozzarella y aceite de oliva.', tiempo: '20 min' };
    if (n.includes('burger') || n.includes('hamburguesa')) return { desc: 'Medallón 100% carne de pastura, cheddar derretido, bacon y aderezos.', tiempo: '15 min' };
    if (n.includes('galeto') || n.includes('pollo')) return { desc: 'Pollo marinado al limón, asado lentamente con finas hierbas aromáticas.', tiempo: '35 min' };
    if (n.includes('pasta') || n.includes('fideo')) return { desc: 'Pasta artesanal salteada al wok con salsa a elección y queso sardo.', tiempo: '20 min' };
    if (n.includes('ensalada')) return { desc: 'Mix de hojas verdes de estación, tomates cherry, croutons y vinagreta.', tiempo: '10 min' };
    if (n.includes('picada') || n.includes('tabla')) return { desc: 'Selección premium de fiambres ahumados, quesos duros y panes caseros.', tiempo: '10 min' };
    return { desc: 'Especialidad de la casa elaborada en el momento con ingredientes frescos.', tiempo: '20 min' }; 
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
            tarjeta.style.width = '300px';
            tarjeta.innerHTML = `
                <img src="${obtenerImagenPorNombre(item.nombre)}" 
                     alt="${item.nombre}" 
                     style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                <div style="display: flex; flex-direction: column; flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="color: var(--primary-orange); font-size: 12px; font-weight: 700; text-transform: uppercase;">Gestión de Carta</span>
                        <div style="display: flex; align-items: center; gap: 4px; color: var(--text-muted); font-size: 12px; font-weight: bold;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                            ${obtenerDetallesPorNombre(item.nombre).tiempo}
                        </div>
                    </div>
                    <h3 style="color: var(--text-main); font-size: 18px; margin: 0 0 6px 0;">${item.nombre}</h3>
                    <p style="color: var(--text-muted); font-size: 13px; margin: 0 0 12px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4;">
                        ${obtenerDetallesPorNombre(item.nombre).desc}
                    </p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
                        <span style="font-size: 20px; font-weight: 900; color: var(--text-main);">$${parseFloat(item.precio).toFixed(2)}</span>
                        <button class="btn-orange" title="Editar plato" style="background-color: transparent; border: 1px solid var(--primary-orange); color: var(--primary-orange);">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 20h9"></path>
                                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
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
            nuevaTarjeta.style.width = '300px';
            nuevaTarjeta.innerHTML = `
                <img src="${obtenerImagenPorNombre(resultado.nombre)}" 
                     alt="${resultado.nombre}" 
                     style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                <div style="display: flex; flex-direction: column; flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="color: var(--primary-orange); font-size: 12px; font-weight: 700; text-transform: uppercase;">Gestión de Carta</span>
                        <div style="display: flex; align-items: center; gap: 4px; color: var(--text-muted); font-size: 12px; font-weight: bold;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                            ${obtenerDetallesPorNombre(resultado.nombre).tiempo}
                        </div>
                    </div>
                    <h3 style="color: var(--text-main); font-size: 18px; margin: 0 0 6px 0;">${resultado.nombre}</h3>
                    <p style="color: var(--text-muted); font-size: 13px; margin: 0 0 12px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4;">
                        ${obtenerDetallesPorNombre(resultado.nombre).desc}
                    </p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto;">
                        <span style="font-size: 20px; font-weight: 900; color: var(--text-main);">$${parseFloat(resultado.precio).toFixed(2)}</span>
                        <button class="btn-orange" title="Editar plato" style="background-color: transparent; border: 1px solid var(--primary-orange); color: var(--primary-orange);">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 20h9"></path>
                                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
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