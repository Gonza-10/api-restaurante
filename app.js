/* ==========================================================================
   LÓGICA GLOBAL Y MÓDULO DE ADMINISTRACIÓN - PyLP III
   ========================================================================== */

const API_URL = 'http://localhost:8080/api/v1/productos';
const API_PEDIDOS_URL = 'http://localhost:8080/api/v1/pedidos';

// Captura de nodos del DOM (Pueden ser null dependiendo de la pantalla actual)
const contenedorLista = document.getElementById('listado');
const alertaError = document.getElementById('caja-error');
const alertaExito = document.getElementById('caja-exito');
const formulario = document.getElementById('formulario-registro');

/* ==========================================================================
   SISTEMA DE TEMA (MODO CLARO / OSCURO CON LOCALSTORAGE)
   ========================================================================== */
function inicializarTema() {
    // Lee la preferencia guardada en el navegador del usuario
    const temaGuardado = localStorage.getItem('savage-tema');
    if (temaGuardado === 'light') document.body.classList.add('light-mode');

    // Creación dinámica del botón
    const btnTema = document.createElement('button');
    btnTema.className = 'btn-tema';
    btnTema.title = 'Cambiar tema visual';

    // Función interna para actualizar el texto según el estado
    const actualizarTexto = () => {
        btnTema.innerHTML = document.body.classList.contains('light-mode') ? 'Modo: Claro' : 'Modo: Oscuro';
    };

    actualizarTexto(); // Setear el texto inicial

    // Alternancia de clases y guardado de estado local al hacer clic
    btnTema.onclick = () => {
        document.body.classList.toggle('light-mode');
        actualizarTexto(); // Cambia el texto en vivo
        const esClaro = document.body.classList.contains('light-mode');
        localStorage.setItem('savage-tema', esClaro ? 'light' : 'dark');
    };

    document.body.appendChild(btnTema);
}

// Dispara la función apenas carga la página
document.addEventListener('DOMContentLoaded', inicializarTema);

/* ==========================================================================
   UTILIDADES COMPARTIDAS (Imágenes y Descripciones)
   ========================================================================== */
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

/* ==========================================================================
   MÓDULO DE ADMINISTRACIÓN (Solo se ejecuta si existe el formulario principal)
   ========================================================================== */
if (formulario) {
    function limpiarAlertas() {
        if(alertaError) alertaError.style.display = 'none';
        if(alertaExito) alertaExito.style.display = 'none';
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
                // Validación del estado de Soft Delete (asume true si no viene definido en la DB)
                const estaActivo = item.activo !== false; 

                // Aplicación de estilos dinámicos para el borrado lógico (Grisado visual)
                const opacidad = estaActivo ? '1' : '0.5';
                const filtroGris = estaActivo ? 'none' : 'grayscale(100%)';
                const textoBoton = estaActivo ? 'Ocultar Plato' : 'Reactivar Plato';
                const colorBoton = estaActivo ? 'var(--text-muted)' : '#4CAF50';
                const valorInvertido = !estaActivo; 

                const nombreSeguro = item.nombre.replace(/'/g, "\\'");

                const tarjeta = document.createElement('div');
                tarjeta.className = 'product-card';
                tarjeta.style.width = '300px';
                tarjeta.style.opacity = opacidad;
                tarjeta.style.filter = filtroGris;
                tarjeta.style.transition = 'all 0.3s ease';

                tarjeta.innerHTML = `
                    <img src="${obtenerImagenPorNombre(item.nombre)}" alt="${item.nombre}" style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                    <div style="display: flex; flex-direction: column; flex-grow: 1;">
                        <h3 style="color: var(--text-main); font-size: 18px; margin: 0 0 6px 0;">${item.nombre} ${estaActivo ? '' : '(INACTIVO)'}</h3>
                        <p style="color: var(--text-muted); font-size: 13px; margin: 0 0 12px 0;">${obtenerDetallesPorNombre(item.nombre).desc}</p>

                        <div style="display: flex; flex-direction: column; gap: 10px; margin-top: auto;">
                            <span style="font-size: 20px; font-weight: 900; color: var(--text-main); text-align: right;">$${parseFloat(item.precio).toFixed(2)}</span>
                            
                            <div style="display: flex; gap: 8px;">
                                <!-- Botón de Edición Limpio (SVG) -->
                                <button onclick="abrirModalEditar(${item.id}, '${nombreSeguro}', ${item.precio})" style="padding: 8px 12px; border-radius: 8px; font-weight: bold; cursor: pointer; border: 1px solid var(--primary-orange); background: transparent; color: var(--primary-orange); display: flex; align-items: center; justify-content: center;" title="Editar plato">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                </button>
                                
                                <!-- Botón para alternar el borrado lógico en BD -->
                                <button onclick="cambiarEstadoProducto(${item.id}, ${valorInvertido})" style="flex-grow: 1; padding: 8px; border-radius: 8px; font-weight: bold; cursor: pointer; border: 1px solid ${colorBoton}; background: transparent; color: ${colorBoton}; transition: all 0.2s;">
                                    ${textoBoton}
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                contenedorLista.appendChild(tarjeta);
            });
        } catch (error) {
            contenedorLista.innerHTML = '<p style="color: var(--error); font-size: 14px;">Fallo de conexión con el servidor.</p>';
        }
    }

    // Funciones del Modal de Edición
    window.abrirModalEditar = function(id, nombre, precio) {
        document.getElementById('editar-id').value = id;
        document.getElementById('editar-nombre').value = nombre;
        document.getElementById('editar-precio').value = precio;
        document.getElementById('modal-editar').style.display = 'flex';
    };

    window.cerrarModalEditar = function() {
        document.getElementById('modal-editar').style.display = 'none';
    };

    const formEditar = document.getElementById('formulario-editar');
    if (formEditar) {
        formEditar.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('editar-id').value;
            const nombre = document.getElementById('editar-nombre').value.trim();
            const precio = parseFloat(document.getElementById('editar-precio').value);

            try {
                const btn = e.target.querySelector('button');
                const textOriginal = btn.textContent;
                btn.textContent = 'Guardando...';

                const respuesta = await fetch(`${API_URL}/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nombre: nombre, precio: precio })
                });

                if (respuesta.ok) {
                    cerrarModalEditar();
                    obtenerRegistros();
                } else {
                    alert("Error al guardar los cambios en el servidor.");
                }
                btn.textContent = textOriginal;
            } catch (error) {
                console.error("Fallo de red al editar.");
                alert("Fallo de conexión al intentar editar el plato.");
            }
        });
    }

    // Función de Soft Delete
    window.cambiarEstadoProducto = async function(idProducto, nuevoEstadoBoolean) {
        try {
            const respuesta = await fetch(`${API_URL}/${idProducto}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ activo: nuevoEstadoBoolean })
            });

            if (respuesta.ok) {
                obtenerRegistros();
            } else {
                console.warn("Aviso: El backend de David aún no procesó el PATCH o no soporta el campo 'activo'.");
                obtenerRegistros();
            }
        } catch (error) {
            console.error("Fallo de red al actualizar estado del producto.");
        }
    };

    formulario.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        limpiarAlertas();

        const nombre = document.getElementById('campo-nombre').value.trim(); 
        const precio = parseFloat(document.getElementById('campo-precio').value); 
        const payload = { nombre: nombre, precio: precio, activo: true }; 

        try {
            const respuesta = await fetch(API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (respuesta.status === 201) {
                const resultado = await respuesta.json();
                alertaExito.textContent = `Guardado con éxito (ID #${resultado.id})`;
                alertaExito.style.display = 'flex';
                formulario.reset();
                obtenerRegistros(); 
            } else {
                alertaError.textContent = 'Datos inválidos o error en el servidor.';
                alertaError.style.display = 'flex';
            }
        } catch (error) {
            alertaError.textContent = 'Fallo de conexión de red.';
            alertaError.style.display = 'flex';
        }
    });

    obtenerRegistros();
}

/* ==========================================================================
   PROCESAMIENTO TRANSACCIONAL Y RABBITMQ (CHECKOUT CLIENTE)
   ========================================================================== */
function generarUUID() {
    return crypto.randomUUID();
}

function estructurarComanda(carritoData, mesaId) {
    return {
        id_comanda_uuid: generarUUID(),
        mesa_id: mesaId,
        items: carritoData,
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
            throw new Error(errorData.error || `Error: ${respuesta.status}`);
        }
    } catch (error) {
        console.error('Fallo en la comunicación:', error);
        throw error;
    }
}

async function confirmarPedido() {
    // Verificamos el array global carrito instanciado en catalogo.html
    if (typeof window.carrito === 'undefined' || window.carrito.length === 0) return; 

    const btnModal = document.getElementById('btn-confirmar-modal');
    const textoOriginalBtn = btnModal.textContent;

    // Feedback visual asíncrono (Bloqueo de UI)
    btnModal.style.pointerEvents = 'none';
    btnModal.style.backgroundColor = '#666'; 
    btnModal.innerHTML = '<span class="spinner" style="display:inline-block; width:15px; height:15px; border:2px solid white; border-top:2px solid transparent; border-radius:50%; animation: spin 1s linear infinite; margin-right: 10px; vertical-align: middle;"></span> Procesando...';

    try {
        // Lee el PIN desde la memoria (Si no hay PIN, usa "00")
        const pinGuardado = localStorage.getItem('savage-mesa-pin') || '0000';
        const mesaDinamica = pinGuardado.substring(0, 2);

        // Armado del contrato inyectando el array real de productos y mesa dinámica
        const payload = estructurarComanda(window.carrito, mesaDinamica);

        // Envío al backend
        const resultado = await enviarComandaServidor(payload);

        if (resultado.exito) {
            btnModal.style.backgroundColor = '#4CAF50'; 
            btnModal.textContent = '¡Orden enviada con éxito!';

            // Limpieza total del carrito y restauración visual
            setTimeout(() => {
                window.carrito = []; // Vaciamos el array
                window.totalPedido = 0;
                document.getElementById('texto-pedido').textContent = 'Mi pedido (0)';
                document.getElementById('total-pedido').textContent = '$0.00';
                document.getElementById('modal-carrito').style.display = 'none';
                btnModal.style.backgroundColor = 'var(--primary-orange)';
                btnModal.style.pointerEvents = 'auto';
                btnModal.textContent = textoOriginalBtn;
            }, 2500);
        }
    } catch (error) {
        // Fallo de red
        console.error("Fallo transaccional:", error);
        btnModal.style.backgroundColor = 'var(--error)';
        btnModal.textContent = 'Error de conexión. Reintentar.';

        setTimeout(() => {
            btnModal.style.backgroundColor = 'var(--primary-orange)';
            btnModal.textContent = textoOriginalBtn;
            btnModal.style.pointerEvents = 'auto';
        }, 3000);
    }
}