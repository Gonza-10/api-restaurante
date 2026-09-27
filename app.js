/* ==========================================================================
   LÓGICA DEL CLIENTE WEB (ASINCRONÍA Y FETCH API) - PyLP III
   Módulo de Autogestión, Catálogo de Productos y Checkout
   ========================================================================== */

const API_URL = 'http://localhost:8080/api/v1/productos';
const API_PEDIDOS_URL = 'http://localhost:8080/api/v1/pedidos';

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
    if (n.includes('hamburguesa') || n.includes('burger')) return 'https://chiplotegrill.com/wp-content/uploads/2021/02/HAMBURGUESA-COMPLETA.jpg';
    if (n.includes('galeto') || n.includes('pollo')) return 'https://images.unsplash.com/photo-1598514982205-f36b96d1e8d4?auto=format&fit=crop&w=500&q=80';
    if (n.includes('pasta') || n.includes('fideo')) return 'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=500&q=80';
    if (n.includes('ensalada')) return 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=500&q=80';
    if (n.includes('picada') || n.includes('tabla')) return 'https://picadasxl.com/wp-content/uploads/2024/08/inicio.png';
    return 'https://chiplotegrill.com/wp-content/uploads/2021/02/HAMBURGUESA-COMPLETA.jpg'; 
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

/* ==========================================================================
   PROCESAMIENTO TRANSACCIONAL DE COMANDAS Y CONTROL DE IDEMPOTENCIA
   ========================================================================== */

function generarUUID() {
    return crypto.randomUUID();
}

function estructurarComanda(carrito, mesaId) {
    return {
        id_comanda_uuid: generarUUID(),
        mesa_id: mesaId,
        items: carrito,
        timestamp: new Date().toISOString()
    };
}

async function enviarComandaServidor(comandaPayload) {
    try {
        const respuesta = await fetch(API_PEDIDOS_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(comandaPayload)
        });

        if (respuesta.status === 202) {
            return { exito: true, estado: 'en_cola' };
        } else if (respuesta.status === 200 || respuesta.status === 201) {
            return { exito: true, estado: 'confirmado' };
        } else {
            const errorData = await respuesta.json().catch(() => ({}));
            throw new Error(errorData.error || `Error en el procesamiento: ${respuesta.status}`);
        }
    } catch (error) {
        console.error('Fallo en la comunicación con el servicio de comandas:', error);
        throw error;
    }
}

/* ==========================================================================
   EVENTO DE CONFIRMACIÓN DE COMPRA (ASINCRONÍA UI)
   ========================================================================== */

async function confirmarPedido() {
    if (cantidadItems === 0) return; // Evita mandar pedidos vacíos

    const botonCarrito = document.getElementById('boton-carrito');
    const textoOriginal = document.getElementById('texto-pedido').textContent;
    const totalOriginal = document.getElementById('total-pedido').textContent;

    // 1. Feedback visual asíncrono (deshabilita el botón)
    botonCarrito.style.pointerEvents = 'none';
    botonCarrito.style.backgroundColor = '#666'; // Gris para indicar espera
    document.getElementById('texto-pedido').textContent = 'Enviando a cocina...';
    document.getElementById('total-pedido').innerHTML = '<span class="spinner" style="display:inline-block; width:15px; height:15px; border:2px solid white; border-top:2px solid transparent; border-radius:50%; animation: spin 1s linear infinite;"></span>';

    try {
        // 2. Prepara el payload con el UUID
        const payload = estructurarComanda([{ cantidad: cantidadItems, total: totalPedido }], "04");

        // 3. Envía a RabbitMQ y espera el código 202
        const resultado = await enviarComandaServidor(payload);

        if (resultado.exito) {
            // Éxito: RabbitMQ aceptó el mensaje.
            botonCarrito.style.backgroundColor = '#4CAF50'; // Verde éxito
            document.getElementById('texto-pedido').textContent = '¡Orden en preparación!';
            document.getElementById('total-pedido').textContent = 'Cocina avisada';
            
            // Resetea el carrito local después de 3 segundos
            setTimeout(() => {
                totalPedido = 0;
                cantidadItems = 0;
                document.getElementById('texto-pedido').textContent = 'Mi pedido (0)';
                document.getElementById('total-pedido').textContent = '$0.00';
                botonCarrito.style.backgroundColor = 'var(--primary-orange)';
                botonCarrito.style.pointerEvents = 'auto';
            }, 3000);
        }
    } catch (error) {
        // Fallo: Restaura el botón para que el usuario intente de nuevo
        console.error("Fallo al enviar:", error);
        botonCarrito.style.backgroundColor = 'var(--error)';
        document.getElementById('texto-pedido').textContent = 'Error de red';
        
        setTimeout(() => {
            botonCarrito.style.backgroundColor = 'var(--primary-orange)';
            document.getElementById('texto-pedido').textContent = textoOriginal;
            document.getElementById('total-pedido').textContent = totalOriginal;
            botonCarrito.style.pointerEvents = 'auto';
        }, 3000);
    }
}

obtenerRegistros();