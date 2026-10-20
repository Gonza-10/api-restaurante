/* ==========================================================================
   LÓGICA GLOBAL Y MÓDULO DE ADMINISTRACIÓN - PyLP III
   ========================================================================== */

const API_URL = 'http://localhost:8080/api/v1/productos';
const API_CATEGORIAS_URL = 'http://localhost:8080/api/v1/categorias';
const API_PEDIDOS_URL = 'http://localhost:8080/api/v1/pedidos';

const contenedorLista = document.getElementById('listado');
const alertaError = document.getElementById('caja-error');
const alertaExito = document.getElementById('caja-exito');
const formulario = document.getElementById('formulario-registro');

/* ==========================================================================
   SISTEMA DE AUTENTICACIÓN Y SEGURIDAD JWT
   ========================================================================== */

function obtenerToken() {
    return sessionStorage.getItem('savage_token');
}

function obtenerUsuarioActual() {
    const usr = sessionStorage.getItem('savage_usuario');
    return usr ? JSON.parse(usr) : null;
}

function cerrarSesion() {
    sessionStorage.removeItem('savage_token');
    sessionStorage.removeItem('savage_usuario');
    window.location.href = 'login.html';
}

// Reemplazo global de fetch() que inyecta el Token y soporta FormData para imágenes
async function apiFetch(ruta, opciones = {}) {
    const token = obtenerToken();
    const esFormData = opciones.body instanceof FormData;
    const headers = { ...opciones.headers };

    // Solo forzamos JSON si no es un archivo adjunto
    if (!esFormData && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(ruta, { ...opciones, headers });
        if (response.status === 401) {
            cerrarSesion();
            throw new Error("Sesión expirada o inválida.");
        }
        return response;
    } catch (error) {
        console.error("Error en petición a la API:", error);
        throw error;
    }
}

/* ==========================================================================
   SISTEMA DE TEMA (MODO CLARO / OSCURO CON LOCALSTORAGE)
   ========================================================================== */
function inicializarTema() {
    const temaGuardado = localStorage.getItem('savage-tema');
    if (temaGuardado === 'light') document.body.classList.add('light-mode');

    const btnTema = document.createElement('button');
    btnTema.className = 'btn-tema';
    
    const actualizarTexto = () => {
        btnTema.innerHTML = document.body.classList.contains('light-mode') ? 'Modo: Claro' : 'Modo: Oscuro';
    };
    
    actualizarTexto();
    
    btnTema.onclick = () => {
        document.body.classList.toggle('light-mode');
        actualizarTexto();
        const esClaro = document.body.classList.contains('light-mode');
        localStorage.setItem('savage-tema', esClaro ? 'light' : 'dark');
    };
    
    document.body.appendChild(btnTema);
}

document.addEventListener('DOMContentLoaded', inicializarTema);

/* ==========================================================================
   UTILIDADES COMPARTIDAS
   ========================================================================== */
function procesarImagen(url) {
    if (!url) return 'https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=500&q=80';
    if (url.startsWith('/media/')) return `http://localhost:8080${url}`;
    return url;
}

/* ==========================================================================
   MÓDULO DE ADMINISTRACIÓN (ABM PRODUCTOS)
   ========================================================================== */
if (formulario) {
    window.productosAdmin = [];

    function limpiarAlertas() {
        if(alertaError) alertaError.style.display = 'none';
        if(alertaExito) alertaExito.style.display = 'none';
    }

    async function cargarCategoriasSelect() {
        const selectNuevo = document.getElementById('campo-categoria');
        const selectEditar = document.getElementById('editar-categoria');
        if (!selectNuevo && !selectEditar) return;
        
        try {
            const resp = await apiFetch(API_CATEGORIAS_URL);
            if (resp.ok) {
                const categorias = await resp.json();
                const opcionesHTML = categorias.map(c => 
                    `<option value="${c.id}" style="background: #181818; color: white;">${c.nombre}</option>`
                ).join('');
                
                if (selectNuevo) selectNuevo.innerHTML = '<option value="" disabled selected>Seleccioná...</option>' + opcionesHTML;
                if (selectEditar) selectEditar.innerHTML = opcionesHTML;
            }
        } catch (e) {
            console.error("No se pudieron cargar las categorías.");
        }
    }

    async function obtenerRegistros() {
        try {
            const respuesta = await apiFetch(`${API_URL}?incluir_inactivos=true`);
            if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);

            const items = await respuesta.json();
            window.productosAdmin = items;
            contenedorLista.innerHTML = '';

            if (items.length === 0) {
                contenedorLista.innerHTML = '<p style="color: var(--text-muted); font-size: 14px;">No hay registros almacenados en el catálogo.</p>';
                return;
            }

            items.forEach(item => {
                const estaActivo = item.activo !== false; 
                const opacidad = estaActivo ? '1' : '0.5';
                const filtroGris = estaActivo ? 'none' : 'grayscale(100%)';
                const textoBoton = estaActivo ? 'Ocultar Plato' : 'Reactivar Plato';
                const colorBoton = estaActivo ? 'var(--text-muted)' : '#4CAF50';
                
                // Formateo de etiquetas de seguridad alimentaria
                let badges = '';
                if (item.vegetariano) badges += '<span style="background: #2ecc71; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px;">VEG</span>';
                if (item.sin_tacc) badges += '<span style="background: #f39c12; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px;">SIN TACC</span>';

                const tarjeta = document.createElement('div');
                tarjeta.className = 'product-card';
                tarjeta.style.width = '300px';
                tarjeta.style.opacity = opacidad;
                tarjeta.style.filter = filtroGris;
                tarjeta.style.transition = 'all 0.3s ease';
                
                tarjeta.innerHTML = `
                    <img src="${procesarImagen(item.imagen_url)}" alt="${item.nombre}" style="width: 100%; height: 180px; border-radius: 16px; object-fit: cover; margin-bottom: 12px;">
                    <div style="display: flex; flex-direction: column; flex-grow: 1;">
                        <h3 style="color: var(--text-main); font-size: 18px; margin: 0 0 6px 0;">
                            ${item.nombre} ${estaActivo ? '' : '(INACTIVO)'} ${badges}
                        </h3>
                        <span style="color: var(--primary-orange); font-size: 11px; font-weight: bold; text-transform: uppercase; margin-bottom: 6px;">${item.categoria_nombre || 'Sin categoría'}</span>
                        <p style="color: var(--text-muted); font-size: 13px; margin: 0 0 12px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${item.descripcion || 'Sin descripción detallada.'}</p>
                        
                        <div style="display: flex; flex-direction: column; gap: 10px; margin-top: auto;">
                            <span style="font-size: 20px; font-weight: 900; color: var(--text-main); text-align: right;">$${parseFloat(item.precio).toFixed(2)}</span>
                            
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <button onclick="cambiarEstadoProducto(${item.id}, ${!estaActivo})" style="flex: 1; padding: 8px 12px; border-radius: 8px; font-weight: bold; cursor: pointer; border: 1px solid ${colorBoton}; background: transparent; color: ${colorBoton}; transition: all 0.2s;">
                                    ${textoBoton}
                                </button>
                                <button onclick="abrirModalEditar(${item.id})" title="Editar producto" style="padding: 8px 12px; border-radius: 8px; cursor: pointer; border: 1px solid var(--glass-border); background: rgba(255,255,255,0.04); color: var(--text-main); display: flex; align-items: center; justify-content: center; transition: all 0.2s;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                    </svg>
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

    window.cambiarEstadoProducto = async function(idProducto, nuevoEstadoBoolean) {
        try {
            const respuesta = await apiFetch(`${API_URL}/${idProducto}`, {
                method: 'PATCH',
                body: JSON.stringify({ activo: nuevoEstadoBoolean })
            });

            if (respuesta.ok) {
                obtenerRegistros();
            } else {
                alert("Aviso: No se pudo cambiar el estado del producto.");
            }
        } catch (error) {
            console.error("Fallo de red al actualizar estado.");
        }
    };

    window.abrirModalEditar = function(idProducto) {
        const prod = window.productosAdmin.find(p => p.id === idProducto);
        if (!prod) return;

        document.getElementById('editar-id').value = prod.id;
        document.getElementById('editar-nombre').value = prod.nombre;
        document.getElementById('editar-precio').value = parseFloat(prod.precio).toFixed(2);
        document.getElementById('editar-categoria').value = prod.categoria || "";
        document.getElementById('editar-vegetariano').checked = Boolean(prod.vegetariano);
        document.getElementById('editar-sintacc').checked = Boolean(prod.sin_tacc);
        document.getElementById('editar-descripcion').value = prod.descripcion || "";
        document.getElementById('editar-imagen-url').value = prod.imagen_url && prod.imagen_url.startsWith('http') ? prod.imagen_url : "";
        document.getElementById('editar-imagen-archivo').value = ""; // limpia el input file
        
        document.getElementById('editar-error').style.display = 'none';
        document.getElementById('modal-editar').style.display = 'flex';
    };

    window.cerrarModalEditar = function() {
        document.getElementById('modal-editar').style.display = 'none';
    };

    const formEditar = document.getElementById('formulario-editar');
    if (formEditar) {
        formEditar.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idProd = document.getElementById('editar-id').value;
            const errorBox = document.getElementById('editar-error');
            const btnSubmit = document.getElementById('btn-guardar-edicion');
            
            errorBox.style.display = 'none';
            btnSubmit.disabled = true;
            btnSubmit.textContent = 'Guardando...';

            const payload = {
                nombre: document.getElementById('editar-nombre').value.trim(),
                precio: parseFloat(document.getElementById('editar-precio').value),
                categoria: parseInt(document.getElementById('editar-categoria').value, 10),
                vegetariano: document.getElementById('editar-vegetariano').checked,
                sin_tacc: document.getElementById('editar-sintacc').checked,
                descripcion: document.getElementById('editar-descripcion').value.trim()
            };

            const urlImg = document.getElementById('editar-imagen-url').value.trim();
            if (urlImg) payload.imagen_url = urlImg;

            try {
                // 1. Guardar datos JSON
                const respuesta = await apiFetch(`${API_URL}/${idProd}`, {
                    method: 'PATCH',
                    body: JSON.stringify(payload)
                });

                if (respuesta.ok) {
                    // 2. Si hay archivo local, subirlo también
                    const archivoInput = document.getElementById('editar-imagen-archivo');
                    if (archivoInput.files.length > 0) {
                        const formData = new FormData();
                        formData.append('imagen', archivoInput.files[0]);
                        await apiFetch(`${API_URL}/${idProd}/imagen`, {
                            method: 'POST',
                            body: formData
                        });
                    }
                    cerrarModalEditar();
                    obtenerRegistros();
                } else {
                    errorBox.textContent = 'No se pudo actualizar. Verificá los datos.';
                    errorBox.style.display = 'flex';
                }
            } catch (err) {
                errorBox.textContent = 'Error de conexión con el servidor.';
                errorBox.style.display = 'flex';
            } finally {
                btnSubmit.disabled = false;
                btnSubmit.textContent = 'Guardar Cambios';
            }
        });
    }

    formulario.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        limpiarAlertas();

        const payload = {
            nombre: document.getElementById('campo-nombre').value.trim(),
            precio: parseFloat(document.getElementById('campo-precio').value),
            categoria: parseInt(document.getElementById('campo-categoria').value, 10),
            vegetariano: document.getElementById('campo-vegetariano').checked,
            sin_tacc: document.getElementById('campo-sintacc').checked,
            descripcion: document.getElementById('campo-descripcion').value.trim(),
            activo: true
        };

        const urlImg = document.getElementById('campo-imagen-url').value.trim();
        if (urlImg) payload.imagen_url = urlImg;

        const btnSubmit = document.getElementById('btn-submit-registro');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = 'Guardando...';

        try {
            // 1. Creamos el producto base
            const respuesta = await apiFetch(API_URL, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            if (respuesta.status === 201) {
                const resultado = await respuesta.json();
                
                // 2. Si eligió un archivo, lo subimos a la URL del nuevo producto
                const archivoInput = document.getElementById('campo-imagen-archivo');
                if (archivoInput.files.length > 0) {
                    const formData = new FormData();
                    formData.append('imagen', archivoInput.files[0]);
                    await apiFetch(`${API_URL}/${resultado.id}/imagen`, {
                        method: 'POST',
                        body: formData
                    });
                }

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
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Guardar Producto <span class="btn-arrow">→</span>';
        }
    });

    cargarCategoriasSelect();
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
        const respuesta = await apiFetch(API_PEDIDOS_URL, {
            method: 'POST',
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
    if (typeof window.carrito === 'undefined' || window.carrito.length === 0) return; 

    const btnModal = document.getElementById('btn-confirmar-modal');
    const textoOriginalBtn = btnModal.textContent;

    btnModal.style.pointerEvents = 'none';
    btnModal.style.backgroundColor = '#666'; 
    btnModal.innerHTML = '<span class="spinner" style="display:inline-block; width:15px; height:15px; border:2px solid white; border-top:2px solid transparent; border-radius:50%; animation: spin 1s linear infinite; margin-right: 10px; vertical-align: middle;"></span> Procesando...';

    try {
        const numeroMesa = parseInt(sessionStorage.getItem('savage-mesa-numero'), 10) || 2;
        const payload = estructurarComanda(window.carrito, numeroMesa);

        const resultado = await enviarComandaServidor(payload);

        if (resultado.exito) {
            btnModal.style.backgroundColor = '#4CAF50'; 
            btnModal.textContent = '¡Orden enviada con éxito!';

            setTimeout(() => {
                window.carrito = [];
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