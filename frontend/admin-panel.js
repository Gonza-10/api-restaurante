/* ============================================================
   SAVAGE GRILL - PANEL ADMINISTRATIVO (ETAPA 1)
   Menú lateral + ABM proveedores e insumos. No modifica app.js ni CSS global.
   ============================================================ */
(() => {
    'use strict';

    const raiz = (window.SAVAGE_CONFIG?.API_BASE_URL || '/api/v1').replace(/\/+$/, '');
    const $ = (id) => document.getElementById(id);
    const estado = { proveedores: [], editandoId: null, cargando: false, peticionLista: 0, autorizado: false };

    /* =============================================================
       SAVAGE SELECT — Desplegables con estética del sistema
       Mantiene el <select> original como fuente de valores, por lo
       tanto no cambia los formularios ni los datos enviados a Django.
       Se aplica también a selectores agregados dinámicamente.
       ============================================================= */
    const sgSelect = (() => {
        const controles = new WeakMap();
        let actual = null;
        let menu = null;
        let opcionesAbiertas = [];
        let indiceResaltado = -1;
        let prefijoBusqueda = '';
        let relojBusqueda;

        function crearMenu() {
            if (menu) return menu;
            menu = document.createElement('div');
            menu.id = 'sg-select-listado';
            menu.className = 'sg-select-list';
            menu.setAttribute('role', 'listbox');
            menu.setAttribute('aria-label', 'Opciones de selección');
            menu.hidden = true;
            document.body.appendChild(menu);
            return menu;
        }

        function etiquetaDe(select) {
            const etiquetas = select.labels ? Array.from(select.labels) : [];
            const etiqueta = etiquetas[0];
            if (etiqueta) return (etiqueta.textContent || '').replace(/\*/g, '').trim();
            return select.getAttribute('aria-label') || 'Seleccionar una opción';
        }

        function actualizarBoton(select) {
            const ref = controles.get(select);
            if (!ref) return;
            const opcion = select.options[select.selectedIndex];
            ref.valor.textContent = opcion?.textContent || 'Seleccioná una opción';
            ref.boton.classList.toggle('sg-select-placeholder', !select.value);
            ref.boton.disabled = select.disabled;
            ref.boton.setAttribute('aria-label', `${etiquetaDe(select)}: ${ref.valor.textContent}`);
            if (actual?.select === select && !menu.hidden) {
                actual = ref;
                mostrarOpciones();
            }
        }

        function cerrar({ devolverFoco = false } = {}) {
            if (!actual) return;
            const ref = actual;
            actual = null;
            if (menu) {
                menu.hidden = true;
                menu.replaceChildren();
            }
            opcionesAbiertas = [];
            indiceResaltado = -1;
            ref.boton.setAttribute('aria-expanded', 'false');
            ref.boton.removeAttribute('aria-activedescendant');
            if (devolverFoco && ref.boton.isConnected) ref.boton.focus();
        }

        function ubicarMenu() {
            if (!actual || !menu || menu.hidden) return;
            const r = actual.boton.getBoundingClientRect();
            if (!r.width || !r.height) { cerrar(); return; }
            const margen = 8;
            const ancho = Math.max(160, Math.min(r.width, window.innerWidth - margen * 2));
            menu.style.width = `${ancho}px`;
            const izquierdo = Math.max(margen, Math.min(r.left, window.innerWidth - ancho - margen));
            menu.style.left = `${izquierdo}px`;
            menu.style.top = `${r.bottom + 6}px`;
            menu.style.maxHeight = `${Math.min(300, Math.max(100, window.innerHeight - 24))}px`;
            const alto = menu.getBoundingClientRect().height;
            const debajo = window.innerHeight - r.bottom - 8;
            const arriba = r.top - 8;
            if (debajo < Math.min(alto, 190) && arriba > debajo) {
                menu.style.top = `${Math.max(margen, r.top - alto - 6)}px`;
            } else if (debajo < alto) {
                menu.style.maxHeight = `${Math.max(90, debajo - 6)}px`;
            }
        }

        function resaltar(indice) {
            const habilitadas = opcionesAbiertas
                .map((registro, idx) => ({ registro, idx }))
                .filter(({ registro }) => !registro.option.disabled);
            if (!habilitadas.length) return;
            const encontrada = habilitadas.find(x => x.idx === indice);
            if (!encontrada) return;
            indiceResaltado = indice;
            opcionesAbiertas.forEach(({ nodo }, idx) => {
                nodo.classList.toggle('sg-select-highlight', idx === indice);
            });
            actual.boton.setAttribute('aria-activedescendant', encontrada.registro.nodo.id);
            encontrada.registro.nodo.scrollIntoView({ block: 'nearest' });
        }

        function mostrarOpciones() {
            if (!actual) return;
            const lista = crearMenu();
            lista.replaceChildren();
            opcionesAbiertas = [];
            const opciones = Array.from(actual.select.options);
            opciones.forEach((option, index) => {
                const fila = document.createElement('div');
                fila.className = 'sg-select-option';
                fila.id = `sg-select-opcion-${index}`;
                fila.setAttribute('role', 'option');
                fila.setAttribute('aria-selected', String(option.selected));
                fila.setAttribute('aria-disabled', String(option.disabled));
                fila.textContent = option.textContent;
                fila.addEventListener('pointerdown', e => e.preventDefault());
                fila.addEventListener('click', () => elegir(index));
                lista.appendChild(fila);
                opcionesAbiertas.push({ option, nodo: fila, index });
            });
            lista.hidden = false;
            ubicarMenu();
            const seleccionado = opciones.findIndex(o => o.selected && !o.disabled);
            const primeroHabilitado = opciones.findIndex(o => !o.disabled);
            resaltar(seleccionado >= 0 ? seleccionado : primeroHabilitado);
        }

        function abrir(ref) {
            if (ref.select.disabled) return;
            if (actual === ref) { cerrar({ devolverFoco: true }); return; }
            cerrar();
            actual = ref;
            ref.boton.setAttribute('aria-expanded', 'true');
            mostrarOpciones();
        }

        function elegir(indice) {
            if (!actual) return;
            const registro = opcionesAbiertas[indice];
            if (!registro || registro.option.disabled) return;
            const { select } = actual;
            const antes = select.value;
            select.selectedIndex = indice;
            actualizarBoton(select);
            cerrar({ devolverFoco: true });
            if (select.value !== antes) {
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function recorrer(direccion) {
            if (!actual) return;
            const habilitadas = opcionesAbiertas.map((x, i) => i).filter(i => !opcionesAbiertas[i].option.disabled);
            if (!habilitadas.length) return;
            let pos = habilitadas.indexOf(indiceResaltado);
            if (pos < 0) pos = 0;
            resaltar(habilitadas[(pos + direccion + habilitadas.length) % habilitadas.length]);
        }

        function manejarTeclado(evento, ref) {
            const abierto = actual === ref;
            if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                evento.preventDefault();
                if (!abierto) abrir(ref);
                else recorrer(evento.key === 'ArrowDown' ? 1 : -1);
                return;
            }
            if (evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                if (abierto && indiceResaltado >= 0) elegir(indiceResaltado);
                else abrir(ref);
                return;
            }
            if (evento.key === 'Escape' && abierto) {
                evento.preventDefault();
                cerrar({ devolverFoco: true });
                return;
            }
            if (evento.key === 'Tab' && abierto) { cerrar(); return; }
            if (!abierto) return;
            if (evento.key === 'Home' || evento.key === 'End') {
                evento.preventDefault();
                const lista = opcionesAbiertas.map((x, i) => i).filter(i => !opcionesAbiertas[i].option.disabled);
                resaltar(evento.key === 'Home' ? lista[0] : lista.at(-1));
                return;
            }
            if (evento.key.length === 1 && !evento.ctrlKey && !evento.altKey && !evento.metaKey) {
                clearTimeout(relojBusqueda);
                prefijoBusqueda += evento.key.toLocaleLowerCase('es');
                const posicion = opcionesAbiertas.findIndex(x => !x.option.disabled &&
                    (x.option.textContent || '').trim().toLocaleLowerCase('es').startsWith(prefijoBusqueda));
                if (posicion >= 0) resaltar(posicion);
                relojBusqueda = setTimeout(() => { prefijoBusqueda = ''; }, 700);
            }
        }

        function mejorar(select) {
            if (!select || controles.has(select) || select.multiple || select.size > 1) return;
            const padre = select.parentNode;
            if (!padre) return;
            const wrapper = document.createElement('span');
            wrapper.className = 'sg-select-shell';
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'sg-select-button';
            boton.setAttribute('aria-haspopup', 'listbox');
            boton.setAttribute('aria-controls', 'sg-select-listado');
            boton.setAttribute('aria-expanded', 'false');
            const valor = document.createElement('span');
            valor.className = 'sg-select-value';
            const flecha = document.createElement('span');
            flecha.className = 'sg-select-arrow';
            flecha.setAttribute('aria-hidden', 'true');
            boton.append(valor, flecha);
            padre.insertBefore(wrapper, select);
            wrapper.append(select, boton);
            select.classList.add('sg-select-native');
            select.tabIndex = -1;
            select.setAttribute('aria-hidden', 'true');
            const ref = { select, boton, valor };
            controles.set(select, ref);
            boton.addEventListener('click', () => abrir(ref));
            boton.addEventListener('keydown', evento => manejarTeclado(evento, ref));
            select.addEventListener('change', () => actualizarBoton(select));
            select.addEventListener('invalid', evento => {
                evento.preventDefault();
                boton.focus();
                boton.setAttribute('aria-invalid', 'true');
            });
            boton.addEventListener('focus', () => {
                boton.removeAttribute('aria-invalid');
                actualizarBoton(select);
            });
            const observarOpciones = new MutationObserver(() => actualizarBoton(select));
            observarOpciones.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected', 'label', 'value'] });
            actualizarBoton(select);
        }

        function mejorarTodos(raiz = document) {
            if (raiz instanceof HTMLSelectElement) mejorar(raiz);
            if (typeof raiz.querySelectorAll === 'function') {
                raiz.querySelectorAll('select').forEach(mejorar);
            }
        }

        function iniciar() {
            mejorarTodos();
            crearMenu();
            const observador = new MutationObserver(cambios => {
                for (const cambio of cambios) {
                    for (const nodo of cambio.addedNodes) {
                        if (nodo.nodeType === Node.ELEMENT_NODE) mejorarTodos(nodo);
                    }
                }
            });
            observador.observe(document.body, { childList: true, subtree: true });
            document.addEventListener('pointerdown', evento => {
                if (actual && !actual.boton.contains(evento.target) && !menu.contains(evento.target)) cerrar();
            }, true);
            document.addEventListener('click', evento => {
                const etiqueta = evento.target.closest?.('label[for]');
                if (!etiqueta) return;
                const select = document.getElementById(etiqueta.htmlFor);
                const ref = select ? controles.get(select) : null;
                if (!ref) return;
                evento.preventDefault();
                ref.boton.focus();
                abrir(ref);
            });
            document.addEventListener('reset', () => setTimeout(() => {
                document.querySelectorAll('select.sg-select-native').forEach(actualizarBoton);
            }, 0), true);
            window.addEventListener('resize', ubicarMenu);
            window.addEventListener('scroll', ubicarMenu, true);
            document.addEventListener('focusin', evento => {
                if (actual && !actual.boton.contains(evento.target) && !menu.contains(evento.target)) cerrar();
            });
        }

        return { iniciar, actualizar: () => document.querySelectorAll('select.sg-select-native').forEach(actualizarBoton) };
    })();

    // Mantiene la última sección abierta durante esta sesión de navegación.
    const CLAVE_VISTA_ADMIN = 'savage-admin-ultima-vista';
    const VISTAS_HABILITADAS = ['menu', 'proveedores', 'insumos', 'compras', 'movimientos', 'ajustes', 'recetas', 'reposicion', 'jornada', 'cobros', 'reservas', 'mesas'];

    const modalConfirmacion = {
        activa: false,
        origen: null,
        resolver: null,
        cancelar: null,
        aceptar: null,
        tecla: null
    };

    function cerrarConfirmacion(resultado) {
        const fondo = $('admin-confirmacion');
        if (!fondo || !modalConfirmacion.activa) return;
        fondo.hidden = true;
        fondo.setAttribute('aria-hidden', 'true');
        modalConfirmacion.aceptar?.removeEventListener('click', modalConfirmacion.resolver);
        modalConfirmacion.cancelar?.removeEventListener('click', modalConfirmacion.cancelarHandler);
        fondo.removeEventListener('click', modalConfirmacion.clicFondoHandler);
        document.removeEventListener('keydown', modalConfirmacion.tecla);
        const resolver = modalConfirmacion.resolverPromise;
        const foco = modalConfirmacion.origen;
        modalConfirmacion.activa = false;
        modalConfirmacion.origen = null;
        modalConfirmacion.resolver = null;
        modalConfirmacion.cancelarHandler = null;
        modalConfirmacion.clicFondoHandler = null;
        modalConfirmacion.resolverPromise = null;
        modalConfirmacion.tecla = null;
        if (foco && typeof foco.focus === 'function') foco.focus();
        if (typeof resolver === 'function') resolver(resultado);
    }

    function pedirConfirmacion({ titulo, texto, aceptar = 'Confirmar', cancelar = 'Cancelar', variante = 'danger', icono = '⚠', origen = null }) {
        const fondo = $('admin-confirmacion');
        const tituloEl = $('admin-confirmacion-titulo');
        const textoEl = $('admin-confirmacion-texto');
        const iconoEl = $('admin-confirmacion-icono');
        const btnCancelar = $('admin-confirmacion-cancelar');
        const btnAceptar = $('admin-confirmacion-aceptar');
        if (!fondo || !tituloEl || !textoEl || !btnCancelar || !btnAceptar || !iconoEl) {
            return Promise.resolve(window.confirm(texto || titulo || '¿Querés continuar?'));
        }
        tituloEl.textContent = titulo || 'Confirmar acción';
        textoEl.textContent = texto || '¿Querés continuar?';
        iconoEl.textContent = icono;
        btnCancelar.textContent = cancelar;
        btnAceptar.textContent = aceptar;
        btnAceptar.className = `sg-admin-confirm-ok ${variante}`;
        fondo.hidden = false;
        fondo.setAttribute('aria-hidden', 'false');
        modalConfirmacion.activa = true;
        modalConfirmacion.origen = origen || document.activeElement;
        modalConfirmacion.aceptar = btnAceptar;
        modalConfirmacion.cancelar = btnCancelar;
        return new Promise((resolve) => {
            modalConfirmacion.resolverPromise = resolve;
            modalConfirmacion.resolver = () => cerrarConfirmacion(true);
            modalConfirmacion.cancelarHandler = () => cerrarConfirmacion(false);
            modalConfirmacion.clicFondoHandler = (evento) => {
                if (evento.target === fondo) cerrarConfirmacion(false);
            };
            modalConfirmacion.tecla = (evento) => {
                if (!modalConfirmacion.activa) return;
                if (evento.key === 'Escape') {
                    evento.preventDefault();
                    cerrarConfirmacion(false);
                }
                if (evento.key === 'Tab') {
                    const focusables = [btnCancelar, btnAceptar].filter(Boolean);
                    const primero = focusables[0];
                    const ultimo = focusables[focusables.length - 1];
                    if (evento.shiftKey && document.activeElement === primero) {
                        evento.preventDefault();
                        ultimo.focus();
                    } else if (!evento.shiftKey && document.activeElement === ultimo) {
                        evento.preventDefault();
                        primero.focus();
                    }
                }
            };
            btnAceptar.addEventListener('click', modalConfirmacion.resolver);
            btnCancelar.addEventListener('click', modalConfirmacion.cancelarHandler);
            fondo.addEventListener('click', modalConfirmacion.clicFondoHandler);
            document.addEventListener('keydown', modalConfirmacion.tecla);
            setTimeout(() => btnAceptar.focus(), 20);
        });
    }


    // Compartimos el modal existente con el ABM de productos de app.js.
    window.savageAdminConfirmar = (opciones) => pedirConfirmacion(opciones);

    function aviso(id, texto, tipo = 'error') {
        const elemento = $(id);
        if (!elemento) return;
        elemento.textContent = texto;
        elemento.className = `sg-admin-msg ${tipo}`;
        elemento.hidden = !texto;
    }

    function mensajeError(payload, status) {
        if (typeof payload === 'string' && payload.trim()) return payload;
        if (!payload || typeof payload !== 'object') return `Error HTTP ${status}`;
        const partes = [];
        for (const clave of ['error', 'mensaje', 'detail', 'texto']) {
            if (payload[clave] != null) partes.push(String(payload[clave]));
        }
        for (const [campo, detalle] of Object.entries(payload)) {
            if (['error', 'mensaje', 'detail', 'texto'].includes(campo)) continue;
            const texto = Array.isArray(detalle) ? detalle.join(' ') : (typeof detalle === 'string' ? detalle : JSON.stringify(detalle));
            if (texto) partes.push(`${campo}: ${texto}`);
        }
        return partes.join('\n') || `Error HTTP ${status}`;
    }

    async function llamarApi(ruta, opciones = {}) {
        const token = sessionStorage.getItem('savage_token');
        if (!token) {
            window.location.href = 'login.html';
            throw new Error('No hay sesión iniciada.');
        }
        const controlador = new AbortController();
        const limite = setTimeout(() => controlador.abort(), 12000);
        let respuesta;
        try {
            respuesta = await fetch(`${raiz}${ruta}`, {
                ...opciones,
                signal: controlador.signal,
                cache: 'no-store',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    ...(opciones.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
                    ...opciones.headers
                }
            });
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('La consulta demoró demasiado. Intentá nuevamente.');
            throw new Error('No se pudo conectar con la API. Comprobá que Django esté ejecutándose en el puerto 8080 y que config.js tenga la dirección correcta. Si continúa, revisá Network (Red) en F12.');
        } finally {
            clearTimeout(limite);
        }
        const texto = await respuesta.text();
        let datos = null;
        if (texto) {
            try { datos = JSON.parse(texto); } catch (_) { datos = texto; }
        }
        if (!respuesta.ok) {
            const error = new Error(mensajeError(datos, respuesta.status));
            error.status = respuesta.status;
            if (respuesta.status === 401) {
                sessionStorage.removeItem('savage_token');
                sessionStorage.removeItem('savage_usuario');
                sessionStorage.removeItem(CLAVE_VISTA_ADMIN);
                setTimeout(() => { window.location.href = 'login.html'; }, 1000);
            }
            throw error;
        }
        return datos;
    }

    function activarVista(vista) {
        if (!estado.autorizado) return;
        // No restaurar secciones aún no desarrolladas o botones deshabilitados.
        if (!VISTAS_HABILITADAS.includes(vista)) vista = 'menu';
        const botonVista = document.querySelector(`[data-admin-tab="${vista}"]`);
        if (!botonVista || botonVista.disabled || !$(`vista-${vista}`)) vista = 'menu';
        sessionStorage.setItem(CLAVE_VISTA_ADMIN, vista);
        for (const id of VISTAS_HABILITADAS) {
            const elemento = $(`vista-${id}`);
            if (elemento) elemento.hidden = id !== vista;
        }
        for (const boton of document.querySelectorAll('[data-admin-tab]')) {
            const seleccionada = boton.dataset.adminTab === vista;
            boton.classList.toggle('active', seleccionada);
            if (seleccionada) boton.setAttribute('aria-current', 'page');
            else boton.removeAttribute('aria-current');
        }
        if (vista === 'proveedores') cargarProveedores();
        if (vista === 'insumos') { cargarInsumos(); cargarProveedoresParaInsumos(); }
        if (vista === 'compras') iniciarCompras();
        if (vista === 'movimientos') iniciarMovimientos();
        if (vista === 'ajustes') iniciarAjustes();
        if (vista === 'recetas') moduloRecetas.iniciar();
        if (vista === 'reposicion') moduloReposicion.iniciar();
        if (vista === 'jornada') moduloJornadaEspeciales.iniciar();
        // Cobros y Reservas viven en su propia pantalla, embebida: se carga la primera vez que se abre.
        const marco = $(`marco-${vista}`);
        if (marco && !marco.getAttribute('src')) marco.setAttribute('src', marco.dataset.src);
        const contenido = $('admin-contenido');
        if (contenido) contenido.classList.toggle('sg-con-marco', Boolean(marco));
    }

    function campo(nombre) {
        return $(`proveedor-${nombre}`);
    }

    function datosFormulario() {
        // Los campos coinciden exactamente con ProveedorSerializer.
        return {
            nombre: campo('nombre').value.trim(),
            contacto: campo('contacto').value.trim(),
            telefono: campo('telefono').value.trim(),
            email: campo('email').value.trim(),
            direccion: campo('direccion').value.trim(),
            notas: campo('notas').value.trim()
        };
    }

    function limpiarFormulario() {
        $('proveedor-form').reset();
        estado.editandoId = null;
        $('proveedor-form-titulo').textContent = 'Nuevo Proveedor';
        $('proveedor-guardar').textContent = 'Guardar proveedor';
        $('proveedor-cancelar').hidden = true;
        aviso('proveedor-form-mensaje', '');
    }

    function agregarTexto(padre, etiqueta, texto, clase = '') {
        const elemento = document.createElement(etiqueta);
        if (clase) elemento.className = clase;
        elemento.textContent = texto;
        padre.appendChild(elemento);
        return elemento;
    }

    function crearBoton(texto, clase, accion) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = clase;
        boton.textContent = texto;
        boton.addEventListener('click', accion);
        return boton;
    }

    function editarProveedor(proveedor) {
        for (const nombre of ['nombre', 'contacto', 'telefono', 'email', 'direccion', 'notas']) {
            campo(nombre).value = proveedor[nombre] ?? '';
        }
        estado.editandoId = proveedor.id;
        $('proveedor-form-titulo').textContent = 'Editar Proveedor';
        $('proveedor-guardar').textContent = 'Guardar cambios';
        $('proveedor-cancelar').hidden = false;
        aviso('proveedor-form-mensaje', '');
        campo('nombre').focus();
        $('proveedor-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    async function cambiarActivo(proveedor, evento = null) {
        const activo = proveedor.activo !== false;
        const confirmar = await pedirConfirmacion({
            titulo: activo ? 'Desactivar proveedor' : 'Reactivar proveedor',
            texto: activo
                ? `¿Querés desactivar a "${proveedor.nombre}"? El proveedor no se elimina: quedará inactivo y seguirá existiendo para conservar el historial de compras.`
                : `¿Querés reactivar a "${proveedor.nombre}" para volver a usarlo en el sistema?`,
            aceptar: activo ? 'Sí, desactivar' : 'Sí, reactivar',
            cancelar: 'Cancelar',
            variante: activo ? 'danger' : 'success',
            icono: activo ? '⚠' : '↺',
            origen: evento?.currentTarget || document.activeElement
        });
        if (!confirmar) return;
        aviso('proveedor-lista-mensaje', 'Guardando cambios...', '');
        try {
            if (activo) {
                await llamarApi(`/proveedores/${encodeURIComponent(proveedor.id)}`, { method: 'DELETE' });
            } else {
                await llamarApi(`/proveedores/${encodeURIComponent(proveedor.id)}`, {
                    method: 'PATCH', body: JSON.stringify({ activo: true })
                });
            }
            if (estado.editandoId === proveedor.id) limpiarFormulario();
            await cargarProveedores();
            aviso('proveedor-form-mensaje', `Proveedor ${activo ? 'desactivado' : 'reactivado'} correctamente.`, 'success');
        } catch (error) {
            aviso('proveedor-lista-mensaje', error.message);
        }
    }

    function pintarProveedores() {
        const contenedor = $('proveedor-lista');
        contenedor.replaceChildren();
        const buscar = campo('buscar').value.trim().toLocaleLowerCase();
        const mostrarInactivos = campo('inactivos').checked;
        const visibles = estado.proveedores.filter(p =>
            (mostrarInactivos || p.activo !== false) &&
            (p.nombre || '').toLocaleLowerCase().includes(buscar)
        );
        if (!visibles.length) {
            aviso('proveedor-lista-mensaje', buscar ? 'No se encontraron proveedores con ese nombre.' : 'No hay proveedores para mostrar.', '');
            return;
        }
        aviso('proveedor-lista-mensaje', '');
        for (const proveedor of visibles) {
            const tarjeta = document.createElement('article');
            tarjeta.className = 'sg-admin-card';
            const cabecera = document.createElement('div');
            cabecera.style.cssText = 'display:flex;align-items:start;justify-content:space-between;gap:10px;';
            agregarTexto(cabecera, 'h3', proveedor.nombre);
            agregarTexto(cabecera, 'span', proveedor.activo !== false ? 'ACTIVO' : 'INACTIVO',
                `sg-admin-status ${proveedor.activo !== false ? 'activo' : 'inactivo'}`);
            tarjeta.appendChild(cabecera);
            const propiedades = [
                ['Contacto', proveedor.contacto], ['Teléfono', proveedor.telefono],
                ['Correo', proveedor.email], ['Dirección', proveedor.direccion], ['Notas', proveedor.notas]
            ];
            for (const [etiqueta, dato] of propiedades) {
                if (!dato) continue;
                const fila = document.createElement('p');
                const fuerte = document.createElement('strong');
                fuerte.textContent = `${etiqueta}: `;
                fila.append(fuerte, document.createTextNode(String(dato)));
                tarjeta.appendChild(fila);
            }
            const acciones = document.createElement('div');
            acciones.className = 'sg-admin-card-footer';
            acciones.appendChild(crearBoton('Editar', 'sg-admin-secondary', () => editarProveedor(proveedor)));
            acciones.appendChild(crearBoton(proveedor.activo !== false ? 'Desactivar' : 'Reactivar',
                `sg-admin-secondary ${proveedor.activo !== false ? 'sg-admin-danger' : ''}`,
                (evento) => cambiarActivo(proveedor, evento)));
            tarjeta.appendChild(acciones);
            contenedor.appendChild(tarjeta);
        }
    }

    async function cargarProveedores() {
        const numero = ++estado.peticionLista;
        aviso('proveedor-lista-mensaje', 'Cargando proveedores...', '');
        try {
            const proveedores = await llamarApi('/proveedores?incluir_inactivos=true');
            if (numero !== estado.peticionLista) return;
            if (!Array.isArray(proveedores)) throw new Error('El servidor no devolvió una lista de proveedores.');
            estado.proveedores = proveedores;
            pintarProveedores();
        } catch (error) {
            if (numero !== estado.peticionLista) return;
            $('proveedor-lista').replaceChildren();
            aviso('proveedor-lista-mensaje', error.message);
        }
    }

    async function guardarProveedor(evento) {
        evento.preventDefault();
        if (estado.cargando) return;
        const datos = datosFormulario();
        if (!datos.nombre) {
            aviso('proveedor-form-mensaje', 'El nombre no puede estar vacío.');
            campo('nombre').focus();
            return;
        }
        const editando = estado.editandoId !== null;
        estado.cargando = true;
        const boton = $('proveedor-guardar');
        boton.disabled = true;
        const textoOriginal = boton.textContent;
        boton.textContent = 'Guardando...';
        aviso('proveedor-form-mensaje', '');
        try {
            await llamarApi(editando ? `/proveedores/${encodeURIComponent(estado.editandoId)}` : '/proveedores', {
                method: editando ? 'PATCH' : 'POST',
                body: JSON.stringify(datos)
            });
            limpiarFormulario();
            await cargarProveedores();
            aviso('proveedor-form-mensaje', editando ? 'Proveedor actualizado correctamente.' : 'Proveedor registrado correctamente.', 'success');
        } catch (error) {
            aviso('proveedor-form-mensaje', error.message);
        } finally {
            estado.cargando = false;
            boton.disabled = false;
            boton.textContent = estado.editandoId !== null ? 'Guardar cambios' : 'Guardar proveedor';
        }
    }


    // ==================== INSUMOS ====================
    const estadoInsumos = {
        insumos: [], proveedores: [], proveedoresListos: false, proveedoresError: '',
        editandoId: null, relacionId: null, guardando: false, guardandoRelacion: false,
        peticionLista: 0
    };
    const UNIDAD_INSUMO = { Masa: 'g', Volumen: 'ml', Unidad: 'unidades' };
    const AYUDA_UNIDAD = {
        Masa: 'Ingresá la cantidad en gramos (no en kilogramos).',
        Volumen: 'Ingresá la cantidad en mililitros (no en litros).',
        Unidad: 'Ingresá la cantidad en unidades enteras.'
    };

    function formatoCantidad(valor) {
        if (valor === null || valor === undefined || valor === '') return '—';
        const numero = Number(valor);
        return Number.isFinite(numero) ? new Intl.NumberFormat('es-AR', { maximumFractionDigits: 3 }).format(numero) : String(valor);
    }

    function unidadInsumo(tipo) {
        return UNIDAD_INSUMO[tipo] || tipo || '';
    }

    function actualizarUnidadInsumo() {
        const tipo = $('insumo-tipo-medida').value;
        $('insumo-unidad-form').textContent = unidadInsumo(tipo);
        $('insumo-ayuda-unidad').textContent = AYUDA_UNIDAD[tipo] || '';
        const cantidad = $('insumo-stock-objetivo');
        cantidad.step = tipo === 'Unidad' ? '1' : '0.001';
    }

    function limpiarFormularioInsumo() {
        $('insumo-form').reset();
        estadoInsumos.editandoId = null;
        $('insumo-form-titulo').textContent = 'Nuevo Insumo';
        $('insumo-guardar').textContent = 'Guardar insumo';
        $('insumo-cancelar').hidden = true;
        actualizarUnidadInsumo();
        aviso('insumo-form-mensaje', '');
    }

    function editarInsumo(insumo) {
        estadoInsumos.editandoId = insumo.id;
        $('insumo-nombre').value = insumo.nombre ?? '';
        $('insumo-tipo-medida').value = insumo.tipo_medida ?? 'Masa';
        $('insumo-stock-objetivo').value = insumo.stock_objetivo ?? '0';
        $('insumo-umbral-bajo').value = insumo.umbral_bajo_pct ?? 50;
        $('insumo-umbral-critico').value = insumo.umbral_critico_pct ?? 20;
        $('insumo-form-titulo').textContent = 'Editar Insumo';
        $('insumo-guardar').textContent = 'Guardar cambios';
        $('insumo-cancelar').hidden = false;
        actualizarUnidadInsumo();
        aviso('insumo-form-mensaje', '');
        $('insumo-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
        $('insumo-nombre').focus({ preventScroll: true });
    }

    function datosFormularioInsumo() {
        const nombre = $('insumo-nombre').value.trim();
        const tipo = $('insumo-tipo-medida').value;
        const objetivoTexto = $('insumo-stock-objetivo').value.trim().replace(',', '.');
        const objetivo = Number(objetivoTexto);
        const bajo = Number($('insumo-umbral-bajo').value);
        const critico = Number($('insumo-umbral-critico').value);
        if (!nombre) throw new Error('El nombre del insumo es obligatorio.');
        if (!Object.hasOwn(UNIDAD_INSUMO, tipo)) throw new Error('Elegí un tipo de medida válido.');
        if (!/^\d+(?:\.\d{1,3})?$/.test(objetivoTexto) || !Number.isFinite(objetivo) || objetivo < 0 || objetivo > 999999999.999) {
            throw new Error('El stock objetivo debe ser una cantidad válida de 0 o más, con hasta 3 decimales.');
        }
        if (tipo === 'Unidad' && !Number.isInteger(objetivo)) {
            throw new Error('Para un insumo medido en unidades, el objetivo debe ser un número entero.');
        }
        if (!Number.isInteger(bajo) || bajo < 1 || bajo > 100) throw new Error('El umbral bajo debe estar entre 1 y 100.');
        if (!Number.isInteger(critico) || critico < 0 || critico > 99) throw new Error('El umbral crítico debe estar entre 0 y 99.');
        if (critico >= bajo) throw new Error('El umbral crítico (rojo) tiene que ser menor que el umbral bajo (amarillo).');
        return {
            nombre, tipo_medida: tipo, stock_objetivo: objetivoTexto,
            umbral_bajo_pct: bajo, umbral_critico_pct: critico
        };
    }

    async function guardarInsumo(evento) {
        evento.preventDefault();
        if (estadoInsumos.guardando) return;
        let datos;
        try { datos = datosFormularioInsumo(); }
        catch (error) { aviso('insumo-form-mensaje', error.message); return; }
        const id = estadoInsumos.editandoId;
        const editando = id !== null;
        const boton = $('insumo-guardar');
        estadoInsumos.guardando = true;
        boton.disabled = true;
        boton.textContent = 'Guardando...';
        aviso('insumo-form-mensaje', '');
        try {
            await llamarApi(editando ? `/insumos/${encodeURIComponent(id)}` : '/insumos', {
                method: editando ? 'PATCH' : 'POST',
                body: JSON.stringify(datos)
            });
            limpiarFormularioInsumo();
            await cargarInsumos();
            aviso('insumo-form-mensaje', editando
                ? 'Insumo actualizado correctamente.'
                : 'Insumo registrado correctamente. Su stock inicial es 0. Para incorporarle existencias, registrá una compra o un ajuste. Podés asociarle proveedores desde su tarjeta.', 'success');
        } catch (error) {
            aviso('insumo-form-mensaje', error.message);
        } finally {
            estadoInsumos.guardando = false;
            boton.disabled = false;
            boton.textContent = estadoInsumos.editandoId !== null ? 'Guardar cambios' : 'Guardar insumo';
        }
    }

    function agregarMetricaInsumo(tarjeta, etiqueta, valor) {
        const fila = document.createElement('div');
        fila.className = 'sg-admin-metric';
        agregarTexto(fila, 'span', etiqueta);
        agregarTexto(fila, 'strong', valor);
        tarjeta.appendChild(fila);
    }

    function pintarInsumos() {
        const contenedor = $('insumo-lista');
        contenedor.replaceChildren();
        const texto = $('insumo-buscar').value.trim().toLocaleLowerCase();
        const tipo = $('insumo-filtrar-tipo').value;
        const mostrarInactivos = $('insumo-inactivos').checked;
        const visibles = estadoInsumos.insumos.filter((insumo) =>
            (mostrarInactivos || insumo.activo !== false) &&
            (!tipo || insumo.tipo_medida === tipo) &&
            String(insumo.nombre || '').toLocaleLowerCase().includes(texto)
        );
        if (!visibles.length) {
            aviso('insumo-lista-mensaje', texto || tipo ? 'No se encontraron insumos con esos filtros.' : 'No hay insumos para mostrar.', '');
            return;
        }
        aviso('insumo-lista-mensaje', '');
        for (const insumo of visibles) {
            const tarjeta = document.createElement('article');
            tarjeta.className = 'sg-admin-card';
            const cabecera = document.createElement('div');
            cabecera.className = 'sg-admin-minirow';
            agregarTexto(cabecera, 'h3', insumo.nombre);
            agregarTexto(cabecera, 'span', insumo.activo !== false ? 'ACTIVO' : 'INACTIVO',
                `sg-admin-status ${insumo.activo !== false ? 'activo' : 'inactivo'}`);
            tarjeta.appendChild(cabecera);
            const unidad = unidadInsumo(insumo.tipo_medida);
            agregarMetricaInsumo(tarjeta, 'Tipo', `${insumo.tipo_medida} (${unidad})`);
            agregarMetricaInsumo(tarjeta, 'Cantidad actual', `${formatoCantidad(insumo.stock_actual)} ${unidad}`);
            agregarMetricaInsumo(tarjeta, 'Objetivo', `${formatoCantidad(insumo.stock_objetivo)} ${unidad}`);
            agregarMetricaInsumo(tarjeta, 'Umbrales', `Bajo ${insumo.umbral_bajo_pct}% · Crítico ${insumo.umbral_critico_pct}%`);
            const estadoStock = String(insumo.estado || 'SinObjetivo');
            const estadoClave = estadoStock.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '');
            const estadoFila = document.createElement('div');
            estadoFila.className = 'sg-admin-minirow';
            agregarTexto(estadoFila, 'span', 'Estado del stock', 'sg-admin-muted-note');
            const porcentaje = insumo.porcentaje === null || insumo.porcentaje === undefined ? '' : ` · ${formatoCantidad(insumo.porcentaje)}%`;
            agregarTexto(estadoFila, 'span', `${estadoStock}${porcentaje}`, `sg-admin-state ${estadoClave}`);
            tarjeta.appendChild(estadoFila);
            const proveedores = Array.isArray(insumo.proveedores) ? insumo.proveedores : [];
            agregarMetricaInsumo(tarjeta, 'Proveedores', proveedores.length
                ? proveedores.map((p) => `${p.nombre || `#${p.id}`}${p.es_principal ? ' (principal)' : ''}`).join(', ')
                : 'Sin asignar');
            const acciones = document.createElement('div');
            acciones.className = 'sg-admin-card-footer';
            acciones.appendChild(crearBoton('Editar', 'sg-admin-secondary', () => editarInsumo(insumo)));
            acciones.appendChild(crearBoton('Proveedores', 'sg-admin-secondary', () => abrirProveedoresInsumo(insumo)));
            acciones.appendChild(crearBoton(insumo.activo !== false ? 'Desactivar' : 'Reactivar',
                `sg-admin-secondary ${insumo.activo !== false ? 'sg-admin-danger' : ''}`,
                (evento) => cambiarActivoInsumo(insumo, evento)));
            tarjeta.appendChild(acciones);
            contenedor.appendChild(tarjeta);
        }
    }

    async function cargarInsumos() {
        const numero = ++estadoInsumos.peticionLista;
        aviso('insumo-lista-mensaje', 'Cargando insumos...', '');
        try {
            const insumos = await llamarApi('/insumos?incluir_inactivos=true');
            if (numero !== estadoInsumos.peticionLista) return;
            if (!Array.isArray(insumos)) throw new Error('El servidor no devolvió una lista de insumos.');
            estadoInsumos.insumos = insumos;
            pintarInsumos();
        } catch (error) {
            if (numero !== estadoInsumos.peticionLista) return;
            $('insumo-lista').replaceChildren();
            aviso('insumo-lista-mensaje', error.message);
        }
    }

    async function cambiarActivoInsumo(insumo, evento) {
        const activo = insumo.activo !== false;
        const confirmar = await pedirConfirmacion({
            titulo: activo ? 'Desactivar insumo' : 'Reactivar insumo',
            texto: activo
                ? `¿Querés desactivar \"${insumo.nombre}\"? Solo se permite si ya no tiene stock; el historial se conserva.`
                : `¿Querés reactivar \"${insumo.nombre}\"?`,
            aceptar: activo ? 'Sí, desactivar' : 'Sí, reactivar',
            variante: activo ? 'danger' : 'success',
            icono: activo ? '⚠' : '↺',
            origen: evento?.currentTarget || document.activeElement
        });
        if (!confirmar) return;
        aviso('insumo-lista-mensaje', 'Guardando cambios...', '');
        try {
            if (activo) {
                await llamarApi(`/insumos/${encodeURIComponent(insumo.id)}`, { method: 'DELETE' });
            } else {
                await llamarApi(`/insumos/${encodeURIComponent(insumo.id)}`, {
                    method: 'PATCH', body: JSON.stringify({ activo: true })
                });
            }
            if (estadoInsumos.editandoId === insumo.id) limpiarFormularioInsumo();
            if (estadoInsumos.relacionId === insumo.id) cerrarProveedoresInsumo();
            await cargarInsumos();
            aviso('insumo-lista-mensaje', `Insumo ${activo ? 'desactivado' : 'reactivado'} correctamente.`, 'success');
        } catch (error) {
            aviso('insumo-lista-mensaje', error.message);
        }
    }

    // La asociación de proveedores es independiente del alta/edición de insumos,
    // para no provocar cambios parciales y mantener el historial de compras.
    async function cargarProveedoresParaInsumos() {
        estadoInsumos.proveedoresListos = false;
        estadoInsumos.proveedoresError = '';
        try {
            const respuesta = await llamarApi('/proveedores?incluir_inactivos=true');
            if (!Array.isArray(respuesta)) throw new Error('El servidor no devolvió una lista de proveedores.');
            estadoInsumos.proveedores = respuesta;
            estadoInsumos.proveedoresListos = true;
        } catch (error) {
            estadoInsumos.proveedores = [];
            estadoInsumos.proveedoresError = error.message;
        }
    }

    function cerrarProveedoresInsumo() {
        estadoInsumos.relacionId = null;
        $('insumo-asociacion-box').hidden = true;
        aviso('insumo-proveedores-mensaje', '');
    }

    function proveedoresSeleccionados() {
        return [...$('insumo-proveedores-opciones').querySelectorAll('input[type="checkbox"]:checked')]
            .map((input) => Number(input.value));
    }

    function actualizarPrincipalInsumo(principalPreferido = '') {
        const seleccionados = new Set(proveedoresSeleccionados());
        const opciones = $('insumo-proveedor-principal');
        const anterior = principalPreferido === '' ? opciones.value : String(principalPreferido);
        opciones.replaceChildren(new Option('Ninguno', ''));
        for (const proveedor of estadoInsumos.proveedores.filter((p) => p.activo !== false && seleccionados.has(Number(p.id)))) {
            opciones.add(new Option(proveedor.nombre, String(proveedor.id)));
        }
        opciones.value = [...opciones.options].some((o) => o.value === anterior) ? anterior : '';
    }

    async function abrirProveedoresInsumo(insumo) {
        // Recargar proveedores para incorporar cualquier alta/baja realizada en la pestaña anterior.
        await cargarProveedoresParaInsumos();
        estadoInsumos.relacionId = insumo.id;
        $('insumo-asociacion-box').hidden = false;
        $('insumo-asociacion-titulo').textContent = `Proveedores de ${insumo.nombre}`;
        aviso('insumo-proveedores-mensaje', '');
        const contenedor = $('insumo-proveedores-opciones');
        contenedor.replaceChildren();
        const guardar = $('insumo-proveedores-guardar');
        guardar.disabled = !estadoInsumos.proveedoresListos;
        if (!estadoInsumos.proveedoresListos) {
            aviso('insumo-proveedores-mensaje', `No se pudieron cargar los proveedores. ${estadoInsumos.proveedoresError}`);
        }
        const asignados = Array.isArray(insumo.proveedores) ? insumo.proveedores : [];
        const ids = new Set(asignados.map((p) => Number(p.id)));
        const principal = asignados.find((p) => p.es_principal)?.id ?? '';
        const inactivosAsociados = asignados.filter((p) =>
            !estadoInsumos.proveedores.some((a) => Number(a.id) === Number(p.id) && a.activo !== false)
        );
        $('insumo-asociacion-aviso').textContent = inactivosAsociados.length
            ? 'Atención: hay proveedores anteriores que ya no están activos. Si guardás, la asignación será reemplazada por los proveedores activos que selecciones.'
            : 'Marcá los proveedores que suministran este insumo; solo uno puede ser principal.';
        for (const proveedor of estadoInsumos.proveedores.filter((p) => p.activo !== false)) {
            const label = document.createElement('label');
            label.className = 'sg-admin-supplier-choice';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.value = String(proveedor.id);
            input.checked = ids.has(Number(proveedor.id));
            input.addEventListener('change', () => actualizarPrincipalInsumo());
            label.append(input, document.createTextNode(proveedor.nombre));
            contenedor.appendChild(label);
        }
        actualizarPrincipalInsumo(principal);
        $('insumo-asociacion-box').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function guardarProveedoresInsumo(evento) {
        evento.preventDefault();
        if (estadoInsumos.guardandoRelacion || estadoInsumos.relacionId === null || !estadoInsumos.proveedoresListos) return;
        const seleccionados = proveedoresSeleccionados();
        const principal = $('insumo-proveedor-principal').value;
        if (principal && !seleccionados.includes(Number(principal))) {
            aviso('insumo-proveedores-mensaje', 'El proveedor principal debe estar entre los seleccionados.');
            return;
        }
        const lineas = seleccionados.map((id) => ({ proveedor: id, es_principal: String(id) === principal }));
        const boton = $('insumo-proveedores-guardar');
        estadoInsumos.guardandoRelacion = true;
        boton.disabled = true;
        boton.textContent = 'Guardando...';
        aviso('insumo-proveedores-mensaje', '');
        try {
            await llamarApi(`/insumos/${encodeURIComponent(estadoInsumos.relacionId)}/proveedores`, {
                method: 'PUT', body: JSON.stringify({ proveedores: lineas })
            });
            await cargarInsumos();
            aviso('insumo-proveedores-mensaje', 'Proveedores asociados correctamente.', 'success');
        } catch (error) {
            aviso('insumo-proveedores-mensaje', error.message);
        } finally {
            estadoInsumos.guardandoRelacion = false;
            boton.disabled = !estadoInsumos.proveedoresListos;
            boton.textContent = 'Guardar proveedores asignados';
        }
    }


    // ==================== COMPRAS Y LOTES ====================
    // Utiliza exclusivamente los contratos de views_stock.py y serializers_stock.py.
    const comprasEstado = { proveedores:[], insumos:[], lineas:0, guardando:false, loteBajaId:null, solicitando:false };
    const dineroAR = (valor) => new Intl.NumberFormat('es-AR', { style:'currency', currency:'ARS', minimumFractionDigits:2 }).format(Number(valor) || 0);

    function vaciar(el) { el.replaceChildren(); }
    function elem(tag, texto='', clase='') {
        const n=document.createElement(tag);
        if (clase) n.className=clase;
        if (texto !== '') n.textContent=String(texto);
        return n;
    }
    function opcion(valor, texto) {
        const opt=document.createElement('option'); opt.value=String(valor); opt.textContent=String(texto); return opt;
    }
    function rellenarSelect(select, data, inicial, valorActual='') {
        select.replaceChildren(opcion('',inicial));
        for (const item of data) select.appendChild(opcion(item.id,item.nombre));
        select.value=String(valorActual ?? '');
    }
    function nombreUnidad(insumo) { return ({Masa:'g', Volumen:'ml', Unidad:'unidades'})[insumo?.tipo_medida] || insumo?.unidad_base || ''; }
    function fechaAR(texto) {
        if (!texto) return '—';
        if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) {
            const [anio,mes,dia]=texto.split('-');
            return `${dia}/${mes}/${anio}`;
        }
        const d=new Date(texto);
        return Number.isNaN(d.getTime()) ? String(texto) : new Intl.DateTimeFormat('es-AR',{dateStyle:'short',timeStyle:'short'}).format(d);
    }
    function agregarLineaCompra() {
        if (comprasEstado.lineas >= 100) { aviso('compra-form-mensaje','Podés registrar hasta 100 líneas por compra.'); return; }
        const i=++comprasEstado.lineas;
        const bloque=elem('div','','sg-compra-linea'); bloque.dataset.linea=String(i);
        // HTML estático de la aplicación; los datos externos solo se insertan mediante textContent.
        bloque.innerHTML=`<div class="sg-compra-linea-header"><h3>Línea de compra</h3><button type="button" class="sg-admin-secondary" data-eliminar>Quitar línea</button></div>
          <div class="sg-compra-linea-grid">
            <div class="sg-admin-field sg-admin-span2"><label for="compra-insumo-${i}">Insumo *</label><select id="compra-insumo-${i}" data-insumo required><option value="">Seleccioná un insumo</option></select></div>
            <div class="sg-admin-field sg-admin-span2"><label for="compra-modo-${i}">Forma de indicar cantidad</label><select id="compra-modo-${i}" data-modo><option value="directa">Cantidad total en unidad base</option><option value="presentaciones">Cantidad de presentaciones × tamaño</option></select></div>
            <div class="sg-admin-field" data-directa><label for="compra-cantidad-${i}">Cantidad total *</label><input type="number" id="compra-cantidad-${i}" data-cantidad min="0.001" step="0.001" required><p class="sg-admin-muted-note" data-leyenda-unidad>Seleccioná un insumo</p></div>
            <div class="sg-admin-field" data-por-presentacion hidden><label for="compra-presentaciones-${i}">Cantidad de presentaciones *</label><input type="number" id="compra-presentaciones-${i}" data-presentaciones min="1" step="1"></div>
            <div class="sg-admin-field" data-por-presentacion hidden><label for="compra-tamano-${i}">Tamaño de cada presentación *</label><input type="number" id="compra-tamano-${i}" data-tamano min="0.001" step="0.001"><p class="sg-admin-muted-note" data-leyenda-tamano>Unidad base</p></div>
            <div class="sg-admin-field"><label for="compra-costo-${i}">Costo total de esta línea ($) *</label><input type="number" id="compra-costo-${i}" data-costo min="0" step="0.01" required placeholder="Ej.: 35000"></div>
            <div class="sg-admin-field"><label for="compra-vence-${i}">Fecha de vencimiento (opcional)</label><input type="date" id="compra-vence-${i}" data-vence></div>
          </div>`;
        const select=bloque.querySelector('[data-insumo]');
        rellenarSelect(select,comprasEstado.insumos,'Seleccioná un insumo');
        const actualizarModo=()=>{
            const presentaciones=bloque.querySelector('[data-modo]').value==='presentaciones';
            bloque.querySelector('[data-directa]').hidden=presentaciones;
            bloque.querySelectorAll('[data-por-presentacion]').forEach(el=>el.hidden=!presentaciones);
            bloque.querySelector('[data-cantidad]').required=!presentaciones;
            bloque.querySelector('[data-presentaciones]').required=presentaciones;
            bloque.querySelector('[data-tamano]').required=presentaciones;
        };
        const actualizarUnidad=()=>{
            const insumo=comprasEstado.insumos.find(x=>String(x.id)===select.value);
            const unidad=nombreUnidad(insumo);
            bloque.querySelector('[data-leyenda-unidad]').textContent=unidad?`Unidad base: ${unidad}`:'Seleccioná un insumo';
            bloque.querySelector('[data-leyenda-tamano]').textContent=unidad?`Tamaño en ${unidad}`:'Unidad base';
            const cantidad=bloque.querySelector('[data-cantidad]');
            const tamano=bloque.querySelector('[data-tamano]');
            const esUnidad=insumo?.tipo_medida==='Unidad';
            cantidad.step=esUnidad?'1':'0.001'; cantidad.min=esUnidad?'1':'0.001';
            tamano.step=esUnidad?'1':'0.001'; tamano.min=esUnidad?'1':'0.001';
        };
        bloque.querySelector('[data-modo]').addEventListener('change',actualizarModo);
        select.addEventListener('change',actualizarUnidad);
        bloque.querySelector('[data-eliminar]').addEventListener('click',()=>{
            if ($('compra-lineas').children.length===1) return aviso('compra-form-mensaje','La compra necesita al menos un insumo.');
            bloque.remove(); actualizarTotalPrevio();
        });
        bloque.querySelector('[data-costo]').addEventListener('input',actualizarTotalPrevio);
        $('compra-lineas').appendChild(bloque);
        actualizarModo(); actualizarUnidad(); actualizarTotalPrevio();
    }
    function actualizarTotalPrevio() {
        const total=[...$('compra-lineas').querySelectorAll('[data-costo]')].reduce((t,n)=>t+Math.max(0,Number(n.value)||0),0);
        $('compra-total-previo').textContent=`Total estimado: ${dineroAR(total)}`;
    }
    function limpiarCompra() {
        $('compra-form').reset(); $('compra-lineas').replaceChildren(); comprasEstado.lineas=0;
        aviso('compra-form-mensaje',''); agregarLineaCompra();
    }
    function construirCompra() {
        const proveedor=Number($('compra-proveedor').value);
        if (!proveedor) throw new Error('Seleccioná un proveedor antes de registrar la compra.');
        const bloques=[...$('compra-lineas').children];
        if (!bloques.length) throw new Error('Agregá al menos una línea de compra.');
        const hoy=new Date(); hoy.setHours(0,0,0,0);
        const lineas=bloques.map((bloque,pos)=>{
            const n=pos+1;
            const insumo=Number(bloque.querySelector('[data-insumo]').value);
            const ref=comprasEstado.insumos.find(x=>Number(x.id)===insumo);
            if (!ref) throw new Error(`Línea ${n}: elegí un insumo activo.`);
            const costoTotal=bloque.querySelector('[data-costo]').value;
            if (costoTotal==='' || !Number.isFinite(Number(costoTotal)) || Number(costoTotal)<0) throw new Error(`Línea ${n}: ingresá un costo total válido.`);
            const linea={insumo, costo_total:String(costoTotal)};
            if (bloque.querySelector('[data-modo]').value==='presentaciones') {
                const cantidad=Number(bloque.querySelector('[data-presentaciones]').value);
                const tamano=Number(bloque.querySelector('[data-tamano]').value);
                if (!Number.isInteger(cantidad) || cantidad<1 || !Number.isFinite(tamano) || tamano<=0) throw new Error(`Línea ${n}: revisá la cantidad y el tamaño de las presentaciones.`);
                if (ref.tipo_medida==='Unidad' && !Number.isInteger(cantidad*tamano)) throw new Error(`Línea ${n}: las unidades deben ser enteras.`);
                linea.cantidad_presentaciones=cantidad;
                linea.tamano_presentacion=String(tamano);
            } else {
                const valor=Number(bloque.querySelector('[data-cantidad]').value);
                if (!Number.isFinite(valor) || valor<=0) throw new Error(`Línea ${n}: ingresá una cantidad mayor a cero.`);
                if (ref.tipo_medida==='Unidad' && !Number.isInteger(valor)) throw new Error(`Línea ${n}: la cantidad de unidades debe ser entera.`);
                linea.cantidad=String(valor);
            }
            const fecha=bloque.querySelector('[data-vence]').value;
            if (fecha) {
                const d=new Date(`${fecha}T00:00:00`);
                if (Number.isNaN(d.getTime()) || d<hoy) throw new Error(`Línea ${n}: la fecha de vencimiento no puede ser anterior a hoy.`);
                linea.fecha_vencimiento=fecha;
            }
            return linea;
        });
        return {proveedor, numero_comprobante:$('compra-comprobante').value.trim(), nota:$('compra-nota').value.trim(), lineas};
    }
    async function registrarCompra(e) {
        e.preventDefault();
        if (comprasEstado.guardando) return;
        let payload;
        try { payload=construirCompra(); }
        catch(error) { aviso('compra-form-mensaje',error.message); return; }
        const p=comprasEstado.proveedores.find(x=>Number(x.id)===payload.proveedor);
        const confirmar=await pedirConfirmacion({
            titulo:'Confirmar compra',
            texto:`¿Querés registrar ${payload.lineas.length} línea(s) a ${p?.nombre||'este proveedor'} por ${dineroAR(payload.lineas.reduce((s,l)=>s+Number(l.costo_total),0))}? La operación agregará existencias y no se puede editar después.`,
            aceptar:'Sí, registrar', cancelar:'Revisar', variante:'success', icono:'✓'
        });
        if (!confirmar) return;
        comprasEstado.guardando=true;
        const btn=$('compra-guardar'); btn.disabled=true; btn.textContent='Registrando...';
        aviso('compra-form-mensaje','Enviando compra...','');
        try {
            const compra=await llamarApi('/compras',{method:'POST',body:JSON.stringify(payload)});
            limpiarCompra();
            aviso('compra-form-mensaje',`Compra #${compra?.id ?? ''} registrada correctamente. Los lotes y existencias se actualizaron.`,'success');
            await Promise.all([cargarHistorialCompras(),cargarLotes(),cargarInsumos()]);
        } catch(error) { aviso('compra-form-mensaje',error.message); }
        finally { comprasEstado.guardando=false; btn.disabled=false; btn.textContent='Registrar compra'; }
    }
    async function cargarOpcionesCompras() {
        const [proveedores,insumos]=await Promise.all([
            llamarApi('/proveedores'), llamarApi('/insumos')
        ]);
        if (!Array.isArray(proveedores)||!Array.isArray(insumos)) throw new Error('El servidor no devolvió las listas esperadas de proveedores e insumos.');
        comprasEstado.proveedores=proveedores.filter(p=>p.activo!==false);
        comprasEstado.insumos=insumos.filter(i=>i.activo!==false);
        const anterior=$('compra-proveedor').value;
        rellenarSelect($('compra-proveedor'),comprasEstado.proveedores,'Seleccioná un proveedor',anterior);
        const filtroPrevio=$('compra-filtrar-proveedor').value;
        rellenarSelect($('compra-filtrar-proveedor'),comprasEstado.proveedores,'Todos',filtroPrevio);
        const filtroInsumoPrevio=$('lote-filtrar-insumo').value;
        rellenarSelect($('lote-filtrar-insumo'),comprasEstado.insumos,'Todos',filtroInsumoPrevio);
        for (const bloque of $('compra-lineas').children) {
            const sel=bloque.querySelector('[data-insumo]'); const actual=sel.value;
            rellenarSelect(sel,comprasEstado.insumos,'Seleccioná un insumo',actual);
        }
    }
    function imprimirValor(padre,clave,valor) {
        const item=elem('span');
        const strong=elem('strong',`${clave}: `); strong.style.color='var(--text-main)';
        item.append(strong,document.createTextNode(String(valor??'—')));
        padre.appendChild(item);
    }
    async function cargarHistorialCompras() {
        aviso('compra-lista-mensaje','Cargando compras...','');
        $('compra-historial').replaceChildren();
        try {
            const filtro=$('compra-filtrar-proveedor').value;
            const url=filtro?`/compras?proveedor=${encodeURIComponent(filtro)}`:'/compras';
            const registros=await llamarApi(url);
            if (!Array.isArray(registros)) throw new Error('La API no devolvió el historial de compras en el formato esperado.');
            if (!registros.length) return aviso('compra-lista-mensaje','Todavía no hay compras con ese filtro.','');
            aviso('compra-lista-mensaje','');
            for(const compra of registros.slice(0,100)) {
                const card=elem('article','','sg-compra-tarjeta');
                const title=elem('h3',`Compra #${compra.id} — ${compra.proveedor_nombre || 'Proveedor'}`);
                const metadatos=elem('div','','sg-compra-details');
                imprimirValor(metadatos,'Fecha',fechaAR(compra.fecha_hora));
                imprimirValor(metadatos,'Total',dineroAR(compra.total));
                if (compra.numero_comprobante) imprimirValor(metadatos,'Comprobante',compra.numero_comprobante);
                if (compra.registrada_por) imprimirValor(metadatos,'Registró',compra.registrada_por);
                card.append(title,metadatos);
                if(compra.nota) card.appendChild(elem('p',compra.nota,'sg-admin-muted-note'));
                const lista=elem('div','','sg-compra-table-scroll');
                const tabla=elem('table','','sg-compra-table');
                const thead=elem('thead'); const trHead=elem('tr');
                ['Insumo','Cantidad inicial','Costo de línea','Vencimiento'].forEach(x=>trHead.appendChild(elem('th',x)));
                thead.appendChild(trHead); tabla.appendChild(thead);
                const body=elem('tbody');
                for (const lote of (compra.lineas||[])) {
                    const tr=elem('tr');
                    const cells=[lote.insumo_nombre||`Insumo #${lote.insumo}`,`${formatoCantidad(lote.cantidad_inicial)} ${lote.unidad_base||''}`,dineroAR(lote.costo_total),fechaAR(lote.fecha_vencimiento)];
                    cells.forEach(s=>tr.appendChild(elem('td',s)));
                    body.appendChild(tr);
                }
                tabla.appendChild(body); lista.appendChild(tabla); card.appendChild(lista);
                $('compra-historial').appendChild(card);
            }
        } catch(error) { aviso('compra-lista-mensaje',error.message); }
    }
    async function cargarLotes() {
        aviso('lote-mensaje','Consultando lotes...','');
        $('lote-tabla').replaceChildren();
        try {
            const params=new URLSearchParams();
            if($('lote-filtrar-estado').value) params.set('estado',$('lote-filtrar-estado').value);
            if($('lote-filtrar-insumo').value) params.set('insumo',$('lote-filtrar-insumo').value);
            const lotes=await llamarApi(`/lotes${params.toString()?'?'+params:''}`);
            if (!Array.isArray(lotes)) throw new Error('La API no devolvió una lista de lotes.');
            if (!lotes.length) return aviso('lote-mensaje','No se encontraron lotes para estos filtros.','');
            aviso('lote-mensaje','');
            const tabla=elem('table','','sg-compra-table');
            const cabecera=elem('thead'),tr=elem('tr');
            ['Lote','Insumo','Disponible','Vence','Estado','Acciones'].forEach(t=>tr.appendChild(elem('th',t)));
            cabecera.appendChild(tr);tabla.appendChild(cabecera);
            const body=elem('tbody');
            for(const lote of lotes.slice(0,200)) {
                const fila=elem('tr');
                [String(lote.id),lote.insumo_nombre||'—',`${formatoCantidad(lote.cantidad_actual)} ${lote.unidad_base||''}`,fechaAR(lote.fecha_vencimiento),lote.estado||'—'].forEach(t=>fila.appendChild(elem('td',t)));
                const acc=elem('td');
                if (String(lote.estado).toLowerCase()==='activo' && Number(lote.cantidad_actual)>0) {
                    const btn=elem('button','Dar de baja','sg-admin-secondary sg-admin-danger');btn.type='button';
                    btn.addEventListener('click',()=>abrirBajaLote(lote));acc.appendChild(btn);
                } else acc.textContent='—';
                fila.appendChild(acc);body.appendChild(fila);
            }
            tabla.appendChild(body);$('lote-tabla').appendChild(tabla);
        } catch(error) { aviso('lote-mensaje',error.message); }
    }
    function abrirBajaLote(lote) {
        comprasEstado.loteBajaId=lote.id;
        $('lote-baja-titulo').textContent=`Dar de baja lote #${lote.id} — ${lote.insumo_nombre}`;
        $('lote-baja-motivo').value='';aviso('lote-baja-mensaje','');
        $('lote-baja-contenedor').hidden=false;
        $('lote-baja-contenedor').scrollIntoView({behavior:'smooth',block:'center'});
        $('lote-baja-motivo').focus();
    }
    function cerrarBajaLote() { $('lote-baja-contenedor').hidden=true; comprasEstado.loteBajaId=null; aviso('lote-baja-mensaje',''); }
    async function registrarBajaLote(e) {
        e.preventDefault();
        if (comprasEstado.solicitando) return;
        const motivo=$('lote-baja-motivo').value.trim();
        if (!motivo) return aviso('lote-baja-mensaje','Ingresá un motivo de baja.');
        const id=comprasEstado.loteBajaId;
        if (id==null) return;
        const confirmar=await pedirConfirmacion({
            titulo:'Confirmar baja de lote', texto:`¿Querés retirar el stock del lote #${id}? La baja no se puede deshacer y quedará registrada como pérdida.`,
            aceptar:'Sí, dar de baja', cancelar:'Cancelar', variante:'danger', icono:'⚠'
        });
        if (!confirmar) return;
        comprasEstado.solicitando=true; $('lote-baja-confirmar').disabled=true;
        try {
            await llamarApi(`/lotes/${encodeURIComponent(id)}/baja`,{method:'POST',body:JSON.stringify({motivo})});
            cerrarBajaLote();
            await Promise.all([cargarLotes(),cargarInsumos()]);
            aviso('lote-mensaje',`Lote #${id} dado de baja correctamente.`,'success');
        } catch(error) { aviso('lote-baja-mensaje',error.message); }
        finally { comprasEstado.solicitando=false; $('lote-baja-confirmar').disabled=false; }
    }
    async function iniciarCompras() {
        if (!$('compra-lineas').children.length) agregarLineaCompra();
        aviso('compra-form-mensaje','');
        try { await cargarOpcionesCompras(); }
        catch(error) { aviso('compra-form-mensaje',error.message); }
        await Promise.all([cargarHistorialCompras(),cargarLotes()]);
    }


    /* ============================================================
       MOVIMIENTOS DE STOCK — GET /movimientos-stock
       Solo lectura, con filtros documentados por el backend.
       ============================================================ */
    const movimientosEstado = { secuencia: 0, cargando: false };

    async function cargarOpcionesMovimientos() {
        try {
            const insumos = await llamarApi('/insumos?incluir_inactivos=true');
            if (!Array.isArray(insumos)) throw new Error('El servidor no devolvió la lista de insumos esperada.');
            const selector = $('mov-insumo');
            const seleccionado = selector.value;
            selector.replaceChildren(opcion('', 'Todos los insumos'));
            for (const insumo of insumos) selector.appendChild(opcion(insumo.id, insumo.nombre));
            selector.value = seleccionado;
            sgSelect.actualizar();
        } catch (error) {
            aviso('mov-filtro-mensaje', error.message);
        }
    }

    function crearCeldaMovimiento(tr, texto, clase = '') {
        const td = document.createElement('td');
        if (clase) td.className = clase;
        td.textContent = String(texto ?? '—');
        tr.appendChild(td);
        return td;
    }

    function mostrarMovimientos(registros, limite) {
        const destino = $('mov-tabla');
        destino.replaceChildren();
        const info = $('mov-resumen');
        info.replaceChildren();
        const cantidad = document.createElement('strong');
        cantidad.textContent = `${registros.length} movimiento${registros.length === 1 ? '' : 's'}`;
        const nota = document.createElement('span');
        nota.textContent = registros.length >= limite
            ? `Se muestran hasta ${limite} registros. Aplicá filtros para acotar la consulta.`
            : 'Resultados de la consulta actual. No se suman unidades de distintos insumos.';
        info.append(cantidad, nota);
        if (!registros.length) {
            const vacio = document.createElement('p');
            vacio.className = 'sg-mov-sin-registros';
            vacio.textContent = 'No se encontraron movimientos con estos filtros.';
            destino.appendChild(vacio);
            return;
        }
        const tabla = document.createElement('table');
        tabla.className = 'sg-mov-tabla';
        const cabecera = document.createElement('thead');
        const filaCabecera = document.createElement('tr');
        for (const campo of ['Fecha y hora', 'Tipo', 'Insumo', 'Cantidad', 'Lote', 'Registró', 'Referencia / motivo']) {
            const th = document.createElement('th');
            th.scope = 'col';
            th.textContent = campo;
            filaCabecera.appendChild(th);
        }
        cabecera.appendChild(filaCabecera);
        tabla.appendChild(cabecera);
        const cuerpo = document.createElement('tbody');
        const formateador = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 3 });
        for (const registro of registros) {
            const fila = document.createElement('tr');
            crearCeldaMovimiento(fila, fechaAR(registro.fecha_hora));
            const tipo = String(registro.tipo || '—');
            const tdTipo = document.createElement('td');
            const etiqueta = document.createElement('span');
            etiqueta.className = `sg-mov-tipo ${tipo.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')}`;
            etiqueta.textContent = tipo;
            tdTipo.appendChild(etiqueta);
            fila.appendChild(tdTipo);
            const tdInsumo = crearCeldaMovimiento(fila, registro.insumo_nombre || `Insumo #${registro.insumo ?? '—'}`);
            if (registro.insumo != null) tdInsumo.title = `Insumo #${registro.insumo}`;
            const cantidad = Number(registro.cantidad);
            const textoCantidad = Number.isFinite(cantidad)
                ? `${cantidad > 0 ? '+' : ''}${formateador.format(cantidad)} ${registro.unidad_base || ''}`.trim()
                : `${registro.cantidad ?? '—'} ${registro.unidad_base || ''}`.trim();
            crearCeldaMovimiento(fila, textoCantidad, 'sg-mov-cantidad');
            crearCeldaMovimiento(fila, registro.lote != null ? `#${registro.lote}` : '—');
            crearCeldaMovimiento(fila, registro.registrado_por || 'Sistema');
            const referencias = [];
            if (registro.jornada != null) referencias.push(`Jornada #${registro.jornada}`);
            if (registro.comanda) referencias.push(`Comanda ${registro.comanda}`);
            if (registro.perdida != null) referencias.push(`Pérdida #${registro.perdida}`);
            if (registro.produccion != null) referencias.push(`Producción #${registro.produccion}`);
            const celdaDetalle = crearCeldaMovimiento(fila, referencias.join(' · ') || '—', 'sg-mov-detalle');
            for (const texto of [registro.motivo, registro.nota]) {
                if (!texto) continue;
                const nota = document.createElement('span');
                nota.className = 'sg-mov-motivo';
                nota.textContent = String(texto);
                celdaDetalle.appendChild(nota);
            }
            cuerpo.appendChild(fila);
        }
        tabla.appendChild(cuerpo);
        destino.appendChild(tabla);
    }

    function parametrosMovimientos() {
        const filtros = new URLSearchParams();
        const idInsumo = $('mov-insumo').value;
        const lote = $('mov-lote').value.trim();
        const tipo = $('mov-tipo').value;
        const desde = $('mov-desde').value;
        const hasta = $('mov-hasta').value;
        const limite = Number($('mov-limite').value) || 200;
        if (desde && hasta && desde > hasta) {
            throw new Error('La fecha «Desde» no puede ser posterior a «Hasta».');
        }
        if (lote && (!/^\d+$/.test(lote) || Number(lote) < 1)) {
            throw new Error('El número de lote debe ser un entero positivo.');
        }
        if (idInsumo) filtros.set('insumo', idInsumo);
        if (tipo) filtros.set('tipo', tipo);
        if (lote) filtros.set('lote', lote);
        if (desde) filtros.set('desde', desde);
        if (hasta) filtros.set('hasta', hasta);
        filtros.set('limite', String(limite));
        return { filtros, limite };
    }

    async function cargarMovimientos(evento) {
        evento?.preventDefault();
        let parametros;
        try {
            parametros = parametrosMovimientos();
            aviso('mov-filtro-mensaje', '');
        } catch (error) {
            aviso('mov-filtro-mensaje', error.message);
            return;
        }
        const secuencia = ++movimientosEstado.secuencia;
        const boton = $('mov-buscar');
        boton.disabled = true;
        aviso('mov-resultado-mensaje', 'Cargando movimientos...', '');
        try {
            const filas = await llamarApi(`/movimientos-stock?${parametros.filtros}`);
            if (secuencia !== movimientosEstado.secuencia) return;
            if (!Array.isArray(filas)) throw new Error('El servidor no devolvió una lista de movimientos.');
            mostrarMovimientos(filas, parametros.limite);
            aviso('mov-resultado-mensaje', '');
        } catch (error) {
            if (secuencia !== movimientosEstado.secuencia) return;
            $('mov-tabla').replaceChildren();
            $('mov-resumen').replaceChildren();
            aviso('mov-resultado-mensaje', error.message);
        } finally {
            if (secuencia === movimientosEstado.secuencia) boton.disabled = false;
        }
    }

    function limpiarFiltrosMovimientos() {
        $('mov-form').reset();
        sgSelect.actualizar();
        aviso('mov-filtro-mensaje', '');
        cargarMovimientos();
    }

    async function iniciarMovimientos() {
        // Recargar el historial al volver a la pestaña: una compra o una baja pueden haberlo cambiado.
        await Promise.all([cargarOpcionesMovimientos(), cargarMovimientos()]);
    }


    // P15: Conteo físico y verificación del libro. Contratos de views_stock.py.
    const ajustesEstado = { insumos: [], solicitando: false, consulta: 0, verificando: false };
    const numeroStock = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 3 });

    function insumoSeleccionadoAjuste() {
        return ajustesEstado.insumos.find(i => String(i.id) === $('ajuste-insumo').value) || null;
    }

    function formatoStockAjuste(cantidad, unidad) {
        const n = Number(cantidad);
        return Number.isFinite(n) ? `${numeroStock.format(n)} ${unidad || ''}`.trim() : '—';
    }

    function leerConteoFisico() {
        // Acepta separador decimal con coma o punto. No admite separadores de miles
        // para evitar enviar una cantidad distinta de la ingresada.
        const texto = $('ajuste-cantidad').value.trim();
        if (!texto) return null;
        if (!/^\d+(?:[.,]\d{1,3})?$/.test(texto)) return NaN;
        const n = Number(texto.replace(',', '.'));
        return n >= 0 && n <= 999999999.999 ? n : NaN;
    }

    function actualizarPreviaAjuste() {
        const insumo = insumoSeleccionadoAjuste();
        const unidad = insumo?.unidad_base || nombreUnidad(insumo);
        const registrado = insumo ? Number(insumo.stock_actual) : null;
        const contado = leerConteoFisico();
        $('ajuste-ayuda-unidad').textContent = insumo
            ? `Unidad base: ${unidad}. Ingresá el total contado, no lo que falta. Para decimales podés usar coma o punto (hasta 3 cifras).`
            : 'Seleccioná un insumo para ver la unidad de medida.';
        $('ajuste-stock-actual').textContent = insumo ? formatoStockAjuste(registrado, unidad) : '—';
        $('ajuste-stock-contado').textContent = insumo && contado !== null && Number.isFinite(contado)
            ? formatoStockAjuste(contado, unidad) : '—';
        const diferencia = $('ajuste-diferencia');
        diferencia.className = '';
        if (!insumo || contado === null || !Number.isFinite(contado) || !Number.isFinite(registrado)) {
            diferencia.textContent = '—';
            return;
        }
        const delta = Math.round((contado - registrado) * 1000) / 1000;
        diferencia.textContent = `${delta > 0 ? '+' : ''}${formatoStockAjuste(delta, unidad)}`;
        if (delta > 0) diferencia.classList.add('positivo');
        else if (delta < 0) diferencia.classList.add('negativo');
    }

    async function cargarInsumosAjuste() {
        const consulta = ++ajustesEstado.consulta;
        const previo = $('ajuste-insumo').value;
        aviso('ajuste-mensaje', 'Consultando existencias...', '');
        try {
            const insumos = await llamarApi('/insumos');
            if (consulta !== ajustesEstado.consulta) return;
            if (!Array.isArray(insumos)) throw new Error('El servidor no devolvió una lista de insumos.');
            ajustesEstado.insumos = insumos.filter(i => i.activo !== false);
            const selector = $('ajuste-insumo');
            selector.replaceChildren(opcion('', 'Seleccioná un insumo'));
            for (const insumo of ajustesEstado.insumos) selector.appendChild(opcion(insumo.id, insumo.nombre));
            if (ajustesEstado.insumos.some(i => String(i.id) === previo)) selector.value = previo;
            sgSelect.actualizar();
            actualizarPreviaAjuste();
            aviso('ajuste-mensaje', ajustesEstado.insumos.length ? '' : 'No hay insumos activos para ajustar.', '');
        } catch (error) {
            if (consulta !== ajustesEstado.consulta) return;
            aviso('ajuste-mensaje', error.message);
        }
    }

    function pintarVerificacion(datos) {
        const contenedor = $('verificacion-estado');
        const detalles = $('verificacion-detalles');
        contenedor.replaceChildren();
        detalles.replaceChildren();
        if (typeof datos?.consistente !== 'boolean' || !Array.isArray(datos.lotes_inconsistentes)) {
            throw new Error('La respuesta de verificación no tiene el formato esperado.');
        }
        const titulo = document.createElement('strong');
        const descripcion = document.createElement('span');
        contenedor.className = `sg-ajustes-estado ${datos.consistente ? 'consistente' : 'inconsistente'}`;
        if (datos.consistente) {
            titulo.textContent = '✓ Libro consistente';
            descripcion.textContent = 'Los movimientos de los lotes coinciden con sus cantidades actuales.';
        } else {
            titulo.textContent = '⚠ Se detectaron inconsistencias';
            descripcion.textContent = `Lotes observados: ${datos.lotes_inconsistentes.length}. Revisá el detalle antes de realizar nuevos ajustes.`;
        }
        contenedor.append(titulo, descripcion);
        if (!datos.consistente) {
            datos.lotes_inconsistentes.forEach((registro, indice) => {
                const ficha = document.createElement('article');
                ficha.className = 'sg-ajustes-incidencia';
                const encabezado = document.createElement('strong');
                encabezado.textContent = `Observación ${indice + 1}`;
                ficha.appendChild(encabezado);
                // El backend puede incorporar distintos campos en la incidencia;
                // se renderizan como texto seguro sin interpretar HTML.
                if (registro && typeof registro === 'object' && !Array.isArray(registro)) {
                    for (const [clave, valor] of Object.entries(registro)) {
                        const linea = document.createElement('p');
                        linea.textContent = `${clave}: ${typeof valor === 'object' ? JSON.stringify(valor) : String(valor)}`;
                        ficha.appendChild(linea);
                    }
                } else {
                    const linea = document.createElement('p');
                    linea.textContent = String(registro);
                    ficha.appendChild(linea);
                }
                detalles.appendChild(ficha);
            });
        }
    }

    async function verificarLibroAjustes() {
        if (ajustesEstado.verificando) return;
        ajustesEstado.verificando = true;
        const boton = $('verificacion-ejecutar');
        boton.disabled = true;
        boton.textContent = 'Verificando...';
        aviso('verificacion-mensaje', 'Consultando el libro de movimientos...', '');
        try {
            const resultado = await llamarApi('/stock/verificacion');
            pintarVerificacion(resultado);
            aviso('verificacion-mensaje', '');
        } catch (error) {
            $('verificacion-estado').className = 'sg-ajustes-estado';
            $('verificacion-estado').textContent = 'No se pudo completar la verificación.';
            $('verificacion-detalles').replaceChildren();
            aviso('verificacion-mensaje', error.message);
        } finally {
            boton.disabled = false;
            boton.textContent = 'Verificar consistencia';
            ajustesEstado.verificando = false;
        }
    }

    async function registrarAjuste(evento) {
        evento.preventDefault();
        if (ajustesEstado.solicitando) return;
        const insumo = insumoSeleccionadoAjuste();
        const contado = leerConteoFisico();
        const motivo = $('ajuste-motivo').value.trim();
        if (!insumo) return aviso('ajuste-mensaje', 'Seleccioná un insumo activo.');
        if (contado === null || !Number.isFinite(contado)) {
            return aviso('ajuste-mensaje', 'Ingresá una cantidad no negativa y válida, con hasta 3 decimales.');
        }
        if (insumo.tipo_medida === 'Unidad' && !Number.isInteger(contado)) {
            return aviso('ajuste-mensaje', 'Este insumo se cuenta en unidades enteras.');
        }
        if (!motivo) return aviso('ajuste-mensaje', 'Escribí el motivo del ajuste.');
        if (motivo.length > 100) return aviso('ajuste-mensaje', 'El motivo no puede superar los 100 caracteres.');
        const anterior = Number(insumo.stock_actual);
        const diferencia = Math.round((contado - anterior) * 1000) / 1000;
        if (Math.abs(diferencia) < 0.0005) return aviso('ajuste-mensaje', 'La cantidad contada coincide con el stock actual. No es necesario ajustar.');
        const unidad = insumo.unidad_base || nombreUnidad(insumo);
        const confirmado = await pedirConfirmacion({
            titulo: 'Confirmar ajuste de inventario',
            texto: `Insumo: ${insumo.nombre}. Stock registrado: ${formatoStockAjuste(anterior, unidad)}. Cantidad física contada: ${formatoStockAjuste(contado, unidad)}. Diferencia: ${diferencia > 0 ? '+' : ''}${formatoStockAjuste(diferencia, unidad)}. Motivo: ${motivo}. Esta operación modifica el stock y queda en el libro de movimientos.`,
            aceptar: 'Sí, registrar ajuste', cancelar: 'Cancelar',
            variante: diferencia < 0 ? 'danger' : 'success', icono: '⚖',
            origen: $('ajuste-guardar')
        });
        if (!confirmado) return;
        ajustesEstado.solicitando = true;
        const boton = $('ajuste-guardar');
        boton.disabled = true;
        boton.textContent = 'Guardando...';
        aviso('ajuste-mensaje', 'Registrando el ajuste...', '');
        try {
            const resultado = await llamarApi('/stock/ajustes', {
                method: 'POST',
                body: JSON.stringify({ insumo: insumo.id, cantidad_real: contado.toFixed(3), motivo })
            });
            $('ajuste-cantidad').value = '';
            $('ajuste-motivo').value = '';
            await cargarInsumosAjuste();
            const msg = resultado?.stock_nuevo != null
                ? `Ajuste registrado. Stock actualizado: ${formatoStockAjuste(resultado.stock_nuevo, unidad)}. Podés consultarlo en Movimientos de Stock.`
                : 'Ajuste registrado. Las existencias fueron actualizadas.';
            aviso('ajuste-mensaje', msg, 'success');
        } catch (error) {
            aviso('ajuste-mensaje', error.message);
        } finally {
            ajustesEstado.solicitando = false;
            boton.disabled = false;
            boton.textContent = 'Registrar ajuste';
            actualizarPreviaAjuste();
        }
    }

    async function iniciarAjustes() {
        // No verifica automáticamente: el usuario decide cuándo comprobar el libro.
        await cargarInsumosAjuste();
    }


    /* ================================================
       RECETAS, ELABORACIONES Y ASIGNACIÓN DE PRODUCTOS
       Usa exclusivamente las rutas del backend Savage.
       ================================================ */
    const moduloRecetas = (() => {
        const data = { insumos: [], recetas: [], elaboraciones: [], productos: [], sinReceta: [],
                       editandoReceta: null, editandoElaboracion: null, guardando: false, cargando: false };
        const CLAVE_SUBVISTA = 'savage-admin-receta-subvista';
        const lista = (valor) => Array.isArray(valor) ? valor : (Array.isArray(valor?.results) ? valor.results : (Array.isArray(valor?.items) ? valor.items : []));
        const num = (valor) => {
            if (valor === '' || valor === null || valor === undefined) return null;
            const n = Number(String(valor).trim().replace(',', '.'));
            return Number.isFinite(n) ? n : null;
        };
        const cantidadValida = (valor) => {
            const n = num(valor);
            return n !== null && n > 0 && n <= 999999999.999 && Math.round(n * 1000) === n * 1000;
        };
        const idInsumo = (item) => {
            const valor = item?.insumo ?? item?.insumo_id ?? item?.id_insumo;
            return typeof valor === 'object' ? valor?.id : valor;
        };
        const textoCantidad = (valor, unidad) => valor == null ? '—' : `${String(valor).replace('.', ',')} ${unidad || ''}`.trim();
        const insumo = (id) => data.insumos.find(i => String(i.id) === String(id));
        const nombreInsumo = (id) => insumo(id)?.nombre || `Insumo #${id}`;
        const unidad = (id) => insumo(id)?.unidad_base || { Masa:'g', Volumen:'ml', Unidad:'u' }[insumo(id)?.tipo_medida] || '';
        const el = (id) => $(id);
        const msg = (id, contenido, tipo='error') => aviso(id, contenido, tipo);
        const texto = (tag, valor, clase='') => {
            const n=document.createElement(tag); n.textContent=String(valor ?? ''); if(clase)n.className=clase; return n;
        };
        const boton = (titulo, css, accion) => {
            const b=document.createElement('button');b.type='button';b.textContent=titulo;b.className=css;b.addEventListener('click',accion);return b;
        };
        function opciones(select, elementos, placeholder, valorItem, nombreItem) {
            const anterior=select.value;
            select.replaceChildren(new Option(placeholder, ''));
            for (const item of elementos) select.add(new Option(nombreItem(item), String(valorItem(item))));
            if (Array.from(select.options).some(x=>x.value===anterior)) select.value=anterior;
            sgSelect.actualizar();
        }
        function cambiarPestana(subvista) {
            if (!['platos','elaboraciones','asignacion'].includes(subvista)) subvista='platos';
            sessionStorage.setItem(CLAVE_SUBVISTA,subvista);
            for(const v of ['platos','elaboraciones','asignacion']) el(`receta-subvista-${v}`).hidden=(v!==subvista);
            document.querySelectorAll('[data-receta-tab]').forEach(b=>{
                const activa=b.dataset.recetaTab===subvista;
                b.classList.toggle('active',activa);b.setAttribute('aria-pressed',String(activa));
            });
            if(subvista==='asignacion') cargarAsignaciones();
        }
        function crearIngrediente(tipo, elemento={}) {
            const id = idInsumo(elemento);
            const caja = document.createElement('div'); caja.className='sg-receta-ingrediente';
            const grid=document.createElement('div');grid.className='sg-receta-ing-grid';
            const grupo = document.createElement('div');grupo.className='sg-admin-field';
            const label=document.createElement('label');label.textContent='Insumo *';
            const select=document.createElement('select');select.className='sg-receta-insumo';select.required=true;
            select.id = `sg-r-ing-${crypto.randomUUID?.() || Math.random().toString(36).slice(2)}`;
            label.htmlFor=select.id;
            opciones(select,data.insumos,'Seleccioná un insumo',i=>i.id,i=>`${i.nombre} (${i.unidad_base||unidad(i.id)})`);
            if(id!=null) select.value=String(id);
            grupo.append(label,select);
            const cantGrupo=document.createElement('div');cantGrupo.className='sg-admin-field';
            const clabel=document.createElement('label');clabel.textContent='Cantidad *';
            const input=document.createElement('input');input.inputMode='decimal';input.required=true;
            input.className='sg-receta-cantidad';input.placeholder='Ej.: 250';input.value=elemento.cantidad == null ? '' : String(elemento.cantidad);
            input.id=`${select.id}-cant`;clabel.htmlFor=input.id;
            cantGrupo.append(clabel,input);grid.append(grupo,cantGrupo);
            const acciones=document.createElement('div');acciones.className='sg-receta-ing-actions';
            if(tipo==='receta') {
                const lab=document.createElement('label');lab.className='sg-receta-checkbox';
                const check=document.createElement('input');check.type='checkbox';check.className='sg-receta-quitable';
                check.checked=elemento.quitable===true || elemento.es_quitable===true;
                lab.append(check,document.createTextNode('El cliente puede pedir este plato SIN este ingrediente'));
                acciones.appendChild(lab);
            } else acciones.appendChild(texto('span','Se descuenta al producir la tanda.','sg-receta-small'));
            acciones.appendChild(boton('Quitar','sg-admin-secondary sg-admin-danger',()=>caja.remove()));
            caja.append(grid,acciones);
            el(tipo==='receta'?'receta-ingredientes':'elaboracion-ingredientes').appendChild(caja);
            sgSelect.actualizar();
            return caja;
        }
        function obtenerIngredientes(tipo) {
            const contenedor=el(tipo==='receta'?'receta-ingredientes':'elaboracion-ingredientes');
            const elementos=Array.from(contenedor.querySelectorAll('.sg-receta-ingrediente'));
            if(!elementos.length) throw new Error('Agregá al menos un ingrediente.');
            const vistos=new Set();
            const resultado=[];
            for(const [i,c] of elementos.entries()) {
                const id=c.querySelector('.sg-receta-insumo').value;
                const valor=c.querySelector('.sg-receta-cantidad').value;
                if(!id) throw new Error(`Elegí un insumo para el ingrediente ${i+1}.`);
                if(vistos.has(id)) throw new Error('El mismo insumo no puede repetirse. Sumá las cantidades en un único renglón.');
                vistos.add(id);
                if(!cantidadValida(valor)) throw new Error(`La cantidad del ingrediente ${i+1} debe ser positiva, con un máximo de tres decimales.`);
                const cantidad=Number(String(valor).replace(',','.'));
                if(insumo(id)?.tipo_medida==='Unidad' && !Number.isInteger(cantidad)) {
                    throw new Error(`«${nombreInsumo(id)}» se mide en unidades enteras.`);
                }
                const obj={insumo:Number(id),cantidad};
                if(tipo==='receta') obj.quitable=Boolean(c.querySelector('.sg-receta-quitable')?.checked);
                resultado.push(obj);
            }
            return resultado;
        }
        function limpiarReceta() {
            el('receta-form').reset();data.editandoReceta=null;
            el('receta-form-titulo').textContent='Nueva receta';el('receta-guardar').textContent='Guardar receta';
            el('receta-cancelar').hidden=true;el('receta-ingredientes').replaceChildren();
            crearIngrediente('receta');msg('receta-form-mensaje','');
        }
        function limpiarElaboracion() {
            el('elaboracion-form').reset();data.editandoElaboracion=null;
            el('elaboracion-form-titulo').textContent='Nueva elaboración';el('elaboracion-guardar').textContent='Guardar elaboración';
            el('elaboracion-cancelar').hidden=true;el('elaboracion-ingredientes').replaceChildren();
            crearIngrediente('elaboracion');actualizarUnidad();msg('elaboracion-form-mensaje','');
        }
        function pintarIngredientes(padre, items, tieneQuitables) {
            const ul=document.createElement('ul');ul.className='sg-receta-ingredientes-ver';
            const ingredientes=lista(items);
            for (const ing of ingredientes) {
                const id=idInsumo(ing); const unit=unidad(id);
                const li=document.createElement('li');
                const nombre=ing.insumo_nombre || ing.nombre || nombreInsumo(id);
                li.appendChild(document.createTextNode(`${nombre}: ${textoCantidad(ing.cantidad,unit)}`));
                if(tieneQuitables && (ing.quitable===true || ing.es_quitable===true)) li.appendChild(texto('span',' · Quitables','sg-receta-pill'));
                ul.appendChild(li);
            }
            if(!ul.childNodes.length) ul.appendChild(texto('li','No hay ingredientes detallados.'));
            padre.appendChild(ul);
        }
        function pintarRecetas() {
            const destino=el('receta-lista');destino.replaceChildren();
            el('receta-contador').textContent=`${data.recetas.length} receta(s)`;
            if(!data.recetas.length) { destino.appendChild(texto('p','Todavía no se registraron recetas.','sg-receta-small')); return; }
            for(const r of data.recetas) {
                const card=document.createElement('article');card.className='sg-admin-card';
                card.appendChild(texto('h3',r.nombre || `Receta #${r.id}`));
                pintarIngredientes(card,r.ingredientes,true);
                const costo = r.costo_completo === false ? 'Costo estimado incompleto' :
                    (r.costo != null ? `Costo estimado: $${String(r.costo).replace('.', ',')}` : '');
                if(costo) card.appendChild(texto('p',costo));
                if(r.porciones_posibles!=null) card.appendChild(texto('p',`Porciones posibles: ${r.porciones_posibles}`));
                const fila=document.createElement('div');fila.className='sg-admin-card-footer';
                fila.appendChild(boton('Editar','sg-admin-secondary',()=>editarReceta(r)));
                card.appendChild(fila);destino.appendChild(card);
            }
        }
        function editarReceta(r) {
            cambiarPestana('platos');data.editandoReceta=r.id;
            el('receta-form-titulo').textContent=`Editar receta #${r.id}`;el('receta-nombre').value=r.nombre||'';
            el('receta-guardar').textContent='Guardar cambios';el('receta-cancelar').hidden=false;
            el('receta-ingredientes').replaceChildren();
            for(const ingrediente of lista(r.ingredientes)) crearIngrediente('receta',ingrediente);
            if(!el('receta-ingredientes').children.length) crearIngrediente('receta');
            msg('receta-form-mensaje','');el('receta-form').scrollIntoView({behavior:'smooth',block:'start'});
            el('receta-nombre').focus();
        }
        async function consultarRecetas() {
            msg('receta-lista-mensaje','Cargando recetas...','');
            try {
                const respuesta=await llamarApi('/recetas');
                if(!Array.isArray(respuesta) && !Array.isArray(respuesta?.results)) throw new Error('El servidor no devolvió una lista válida de recetas.');
                data.recetas=lista(respuesta);pintarRecetas();msg('receta-lista-mensaje','');
                opciones(el('receta-asignada'),data.recetas,'Sin receta (sin control de ingredientes)',i=>i.id,i=>i.nombre||`Receta #${i.id}`);
            } catch(err) { msg('receta-lista-mensaje',err.message); }
        }
        async function guardarReceta(e) {
            e.preventDefault();if(data.guardando)return;
            try {
                const nombre=el('receta-nombre').value.trim();
                if(!nombre) throw new Error('Ingresá el nombre de la receta.');
                const ingredientes=obtenerIngredientes('receta');
                if(ingredientes.every(i=>i.quitable)) throw new Error('Al menos un ingrediente debe ser fijo (no quitable).');
                const editar=data.editandoReceta;
                if(editar!=null) {
                    const ok=await pedirConfirmacion({titulo:'Actualizar receta',texto:'Se reemplazará la lista de ingredientes de esta receta. Los pedidos futuros utilizarán las nuevas cantidades.',aceptar:'Guardar cambios',variante:'danger',icono:'✎'});
                    if(!ok)return;
                }
                data.guardando=true;el('receta-guardar').disabled=true;
                await llamarApi(editar==null?'/recetas':`/recetas/${encodeURIComponent(editar)}`,{
                    method: editar==null?'POST':'PUT',body:JSON.stringify({nombre,ingredientes})
                });
                limpiarReceta();await consultarRecetas();
                msg('receta-form-mensaje',editar==null?'Receta registrada correctamente.':'Receta actualizada correctamente.','success');
            } catch(err) {msg('receta-form-mensaje',err.message);} finally {data.guardando=false;el('receta-guardar').disabled=false;}
        }
        function actualizarUnidad() {
            const u=unidad(el('elaboracion-produce').value);
            el('elaboracion-unidad').textContent=`El rendimiento se mide en ${u || 'la unidad base del insumo producido'}.`;
        }
        function pintarElaboraciones() {
            const destino=el('elaboracion-lista');destino.replaceChildren();
            el('elaboracion-contador').textContent=`${data.elaboraciones.length} elaboración(es)`;
            if(!data.elaboraciones.length) {destino.appendChild(texto('p','Todavía no hay elaboraciones registradas.','sg-receta-small'));return;}
            for(const r of data.elaboraciones) {
                const card=document.createElement('article');card.className='sg-admin-card';
                const i=idInsumo(r);const producida=r.insumo_nombre || nombreInsumo(i);
                card.appendChild(texto('h3',producida));
                card.appendChild(texto('p',`Rinde por tanda: ${textoCantidad(r.rinde,unidad(i))}`));
                card.appendChild(texto('p',`Duración: ${r.dias_vencimiento ?? 'Sin especificar'} día(s)`));
                if(r.tandas_posibles!=null) card.appendChild(texto('p',`Tandas posibles con el stock actual: ${r.tandas_posibles}`));
                if(r.costo_tanda!=null) card.appendChild(texto('p',`Costo estimado por tanda: $${String(r.costo_tanda).replace('.',',')}`));
                pintarIngredientes(card,r.ingredientes,false);
                const fila=document.createElement('div');fila.className='sg-admin-card-footer';
                fila.appendChild(boton('Editar','sg-admin-secondary',()=>editarElaboracion(r)));
                card.appendChild(fila);destino.appendChild(card);
            }
        }
        function editarElaboracion(r) {
            cambiarPestana('elaboraciones');data.editandoElaboracion=r.id;
            el('elaboracion-form-titulo').textContent=`Editar elaboración #${r.id}`;
            el('elaboracion-produce').value=String(idInsumo(r)??'');sgSelect.actualizar();
            el('elaboracion-rinde').value=r.rinde??'';
            el('elaboracion-dias').value=r.dias_vencimiento??'';
            el('elaboracion-guardar').textContent='Guardar cambios';el('elaboracion-cancelar').hidden=false;
            el('elaboracion-ingredientes').replaceChildren();
            for(const ingr of lista(r.ingredientes)) crearIngrediente('elaboracion',ingr);
            if(!el('elaboracion-ingredientes').children.length) crearIngrediente('elaboracion');
            actualizarUnidad();msg('elaboracion-form-mensaje','');
            el('elaboracion-form').scrollIntoView({behavior:'smooth',block:'start'});
        }
        async function consultarElaboraciones() {
            msg('elaboracion-lista-mensaje','Cargando elaboraciones...','');
            try {
                const respuesta=await llamarApi('/elaboraciones');
                if(!Array.isArray(respuesta) && !Array.isArray(respuesta?.results)) throw new Error('El servidor no devolvió una lista válida de elaboraciones.');
                data.elaboraciones=lista(respuesta);pintarElaboraciones();msg('elaboracion-lista-mensaje','');
            }catch(err) {msg('elaboracion-lista-mensaje',err.message);}
        }
        async function guardarElaboracion(e) {
            e.preventDefault();if(data.guardando)return;
            try {
                const producido=el('elaboracion-produce').value;
                const rindeTexto=el('elaboracion-rinde').value;
                const diasTexto=el('elaboracion-dias').value;
                if(!producido) throw new Error('Seleccioná el insumo que se produce.');
                if(!cantidadValida(rindeTexto))throw new Error('El rendimiento debe ser positivo, con un máximo de 3 decimales.');
                const rinde=num(rindeTexto);
                if(insumo(producido)?.tipo_medida==='Unidad' && !Number.isInteger(rinde))throw new Error('El rendimiento debe ser entero para insumos medidos en unidades.');
                const ingredientes=obtenerIngredientes('elaboracion');
                if(ingredientes.some(i=>String(i.insumo)===String(producido)))throw new Error('Una elaboración no puede utilizar como ingrediente el mismo insumo que produce.');
                const dias=diasTexto.trim()===''?null:Number(diasTexto);
                if(dias!==null && (!Number.isInteger(dias) || dias<1))throw new Error('Los días de vencimiento deben ser un entero positivo.');
                const entrada={insumo:Number(producido),rinde,ingredientes};
                if(dias!==null) entrada.dias_vencimiento=dias;
                const editar=data.editandoElaboracion;
                if(editar!=null) {
                    const ok=await pedirConfirmacion({titulo:'Actualizar elaboración',texto:'Se reemplazará la composición de esta elaboración. Las producciones futuras usarán esta receta.',aceptar:'Guardar cambios',variante:'danger',icono:'✎'});
                    if(!ok)return;
                }
                data.guardando=true;el('elaboracion-guardar').disabled=true;
                await llamarApi(editar==null?'/elaboraciones':`/elaboraciones/${encodeURIComponent(editar)}`,{
                    method:editar==null?'POST':'PUT',body:JSON.stringify(entrada)
                });
                limpiarElaboracion();await consultarElaboraciones();
                msg('elaboracion-form-mensaje',editar==null?'Elaboración registrada. Cocina podrá producirla cuando haya ingredientes.':'Elaboración actualizada correctamente.','success');
            }catch(err) {msg('elaboracion-form-mensaje',err.message);} finally{data.guardando=false;el('elaboracion-guardar').disabled=false;}
        }
        function pintarSinReceta() {
            const destino=el('sin-receta-lista');destino.replaceChildren();
            if(!data.sinReceta.length) {destino.appendChild(texto('p','No hay productos pendientes de asignación.','sg-receta-small'));return;}
            for (const p of data.sinReceta) {
                const div=document.createElement('article');div.className='sg-admin-card';
                div.appendChild(texto('h3',p.nombre || `Producto #${p.id}`));
                div.appendChild(texto('p',`Producto #${p.id}`));
                div.appendChild(boton('Asignar receta','sg-admin-secondary',()=>{
                    el('receta-producto').value=String(p.id);sgSelect.actualizar();
                    el('receta-asignacion-form').scrollIntoView({behavior:'smooth',block:'start'});
                }));
                destino.appendChild(div);
            }
        }
        async function cargarAsignaciones() {
            msg('sin-receta-mensaje','Cargando productos...','');
            try {
                const [productos,pendientes]=await Promise.all([
                    llamarApi('/productos?incluir_inactivos=true'), llamarApi('/productos-sin-receta')
                ]);
                data.productos=lista(productos);data.sinReceta=lista(pendientes);
                if(!Array.isArray(productos)&&!Array.isArray(productos?.results)) throw new Error('El listado de productos no tiene el formato esperado.');
                opciones(el('receta-producto'),data.productos,'Seleccioná un producto',x=>x.id,x=>x.nombre || `Producto #${x.id}`);
                pintarSinReceta();msg('sin-receta-mensaje','');
            }catch(err){msg('sin-receta-mensaje',err.message);}
        }
        async function guardarAsignacion(e) {
            e.preventDefault();if(data.guardando)return;
            const producto=el('receta-producto').value;const receta=el('receta-asignada').value;
            if(!producto){msg('receta-asignacion-mensaje','Seleccioná un producto.');return;}
            const nombre=data.productos.find(p=>String(p.id)===String(producto))?.nombre || `#${producto}`;
            const esQuitar=receta==='';
            const ok=await pedirConfirmacion({
                titulo:esQuitar?'Dejar producto sin receta':'Asignar receta',
                texto:esQuitar?`El producto «${nombre}» quedará sin control automático de ingredientes. ¿Confirmás?`:
                    `Se actualizará la receta del producto «${nombre}». Los próximos pedidos usarán esa composición.`,
                aceptar:esQuitar?'Sí, quitar receta':'Sí, asignar',variante:esQuitar?'danger':'success',icono:esQuitar?'⚠':'✓'
            });
            if(!ok)return;
            try {
                data.guardando=true;el('receta-asignacion-guardar').disabled=true;
                await llamarApi(`/productos/${encodeURIComponent(producto)}/receta`,{
                    method:'PUT',body:JSON.stringify({receta:receta===''?null:Number(receta)})
                });
                await cargarAsignaciones();msg('receta-asignacion-mensaje',esQuitar?'Producto dejado sin receta.':'Receta asignada correctamente.','success');
            }catch(err){msg('receta-asignacion-mensaje',err.message);}finally{data.guardando=false;el('receta-asignacion-guardar').disabled=false;}
        }
        async function iniciar() {
            if(data.cargando)return;
            data.cargando=true;
            cambiarPestana(sessionStorage.getItem(CLAVE_SUBVISTA)||'platos');
            try {
                const [insumos] = await Promise.all([llamarApi('/insumos')]);
                data.insumos=lista(insumos).filter(i=>i.activo!==false);
                opciones(el('elaboracion-produce'),data.insumos,'Seleccioná un insumo',i=>i.id,i=>`${i.nombre} (${i.unidad_base||unidad(i.id)})`);
                limpiarReceta();limpiarElaboracion();
                await Promise.all([consultarRecetas(),consultarElaboraciones()]);
                if(sessionStorage.getItem(CLAVE_SUBVISTA)==='asignacion') await cargarAsignaciones();
            }catch(err){
                msg('receta-lista-mensaje',err.message);msg('elaboracion-lista-mensaje',err.message);
            }finally{data.cargando=false;}
        }
        function conectar() {
            document.querySelectorAll('[data-receta-tab]').forEach(b=>b.addEventListener('click',()=>cambiarPestana(b.dataset.recetaTab)));
            el('receta-agregar-ingrediente').addEventListener('click',()=>crearIngrediente('receta'));
            el('elaboracion-agregar-ingrediente').addEventListener('click',()=>crearIngrediente('elaboracion'));
            el('receta-form').addEventListener('submit',guardarReceta);
            el('elaboracion-form').addEventListener('submit',guardarElaboracion);
            el('receta-cancelar').addEventListener('click',limpiarReceta);
            el('elaboracion-cancelar').addEventListener('click',limpiarElaboracion);
            el('elaboracion-produce').addEventListener('change',actualizarUnidad);
            el('receta-actualizar').addEventListener('click',consultarRecetas);
            el('elaboracion-actualizar').addEventListener('click',consultarElaboraciones);
            el('receta-asignacion-form').addEventListener('submit',guardarAsignacion);
            el('sin-receta-actualizar').addEventListener('click',cargarAsignaciones);
            el('receta-asignacion-actualizar').addEventListener('click',cargarAsignaciones);
        }
        return { iniciar, conectar };
    })();


    /* ============================================================
       P28 — Reposición y pérdidas. Sin alterar Cocina ni stock.
       La API es fuente de verdad: jamás se modifica stock desde JS.
       ============================================================ */
    const moduloReposicion = (() => {
        const d = { subvista: 'reposicion', motivos: [], insumos: [], productos: [], perdidas: [], cargando: false, guardando: false };
        const $rp = id => document.getElementById(id);
        const extraer = x => Array.isArray(x) ? x : Array.isArray(x?.results) ? x.results : [];
        const numero = x => Number(String(x ?? '').replace(',', '.'));
        const dinero = x => Number.isFinite(numero(x)) ? numero(x).toLocaleString('es-AR', {style:'currency',currency:'ARS'}) : '—';
        const cantidadFmt = x => Number.isFinite(numero(x)) ? numero(x).toLocaleString('es-AR',{maximumFractionDigits:3}) : '—';
        const txt = x => String(x ?? '');
        function mensaje(id, valor, ok=false) { aviso(id, valor, ok?'success':'error'); }
        function crear(tag, texto='', clase='') { const node=document.createElement(tag); if(clase)node.className=clase; node.textContent=txt(texto); return node; }
        function par(contenedor, etiqueta, valor) { const p=crear('p'); const b=crear('strong', `${etiqueta}: `); p.append(b, document.createTextNode(txt(valor))); contenedor.append(p); }
        function opciones(id, listado, etiqueta, valor, mostrar) {
            const select=$rp(id);if(!select)return;
            select.replaceChildren(new Option(etiqueta, ''));
            for(const item of listado)select.add(new Option(txt(mostrar(item)),txt(valor(item))));
            sgSelect.actualizar();
        }
        function setSubvista(nombre) {
            d.subvista = nombre === 'perdidas' ? 'perdidas' : 'reposicion';
            ['reposicion','perdidas'].forEach(t => {
                $rp(`sg-rp-subview-${t}`).hidden=t!==d.subvista;
                const b=document.querySelector(`[data-rp-tab="${t}"]`);
                b.setAttribute('aria-selected',String(t===d.subvista));b.tabIndex=t===d.subvista?0:-1;
            });
            sessionStorage.setItem('savage-admin-rp-subvista',d.subvista);
            if(d.subvista==='perdidas') cargarPerdidas(); else cargarReposicion();
        }
        // El reporte real del backend (hito 6) separa las recomendaciones
        // entre "comprar" (agrupadas por proveedor) y "producir" (elaboraciones).
        // Se conserva compatibilidad con listados planos de otras versiones.
        function columnasReposicion(datos) {
            if(Array.isArray(datos))return datos;
            if(!datos || typeof datos !== 'object')return null;
            const nombres=['insumos','reposicion','sugerencias','items','productos','faltantes','alertas','results'];
            for(const n of nombres)if(Array.isArray(datos[n]))return datos[n];
            if(!Array.isArray(datos.comprar) && !Array.isArray(datos.producir))return null;

            const registros=[];
            function sumar(lista,tipo,proveedor='') {
                for(const it of lista) {
                    if(!it || typeof it!=='object')continue;
                    const subitems=Array.isArray(it.items)?it.items:[it];
                    const nombreProveedor=tipo==='Compra' ? (
                        typeof it.proveedor==='string'?it.proveedor:
                        it.proveedor?.nombre ?? it.proveedor_nombre ?? proveedor
                    ) : '';
                    for(const item of subitems) {
                        if(!item || typeof item!=='object')continue;
                        registros.push({...item,
                            _tipo_reposicion:tipo,
                            _proveedor_reposicion:nombreProveedor || proveedor || ''
                        });
                    }
                }
            }
            sumar(datos.comprar||[],'Compra');
            sumar(datos.producir||[],'Elaboración');
            return registros;
        }
        async function cargarReposicion() {
            mensaje('rp-mensaje','');const cont=$rp('rp-lista');cont.replaceChildren(crear('p','Consultando sugerencias...','sg-rp-note'));
            $rp('rp-actualizar').disabled=true;
            try {
                const datos=await llamarApi('/stock/reposicion');
                const registros=columnasReposicion(datos);
                cont.replaceChildren();
                if(registros===null){
                    mensaje('rp-mensaje','La API respondió con un formato de reposición no reconocido. No se modificó inventario.');
                    return;
                }
                if(!registros.length){
                    cont.append(crear('p','No hay necesidades de reposición informadas por el servidor.','sg-rp-note'));
                    return;
                }
                for(const item of registros){
                    const div=crear('article','','sg-rp-card');
                    const insumo=item.insumo && typeof item.insumo==='object'?item.insumo:null;
                    const titulo=txt(item.nombre ?? item.insumo_nombre ?? insumo?.nombre ?? item.producto_nombre ?? 'Insumo');
                    const head=crear('div','','sg-rp-card-head');head.append(crear('h3',titulo));
                    const est=txt(item._tipo_reposicion ?? item.estado ?? item.semaforo ?? item.prioridad ?? 'Sugerencia');
                    head.append(crear('span',est,'sg-rp-badge'));div.append(head);
                    const proveedor=item._proveedor_reposicion || item.proveedor_principal || item.proveedor_nombre || item.proveedor;
                    const proveedorTxt=typeof proveedor==='object'?proveedor?.nombre:proveedor;
                    const campos=[
                        ['Stock actual',item.stock_texto ?? item.stock_actual ?? item.cantidad_actual ?? item.stock ?? item.actual],
                        ['Objetivo',item.objetivo_texto ?? item.stock_objetivo ?? item.objetivo],
                        ['Faltante',item.faltante_texto ?? item.faltante ?? item.cantidad_a_reponer ?? item.reponer ?? item.cantidad_sugerida],
                        ['Proveedor',proveedorTxt],
                        ['Tandas sugeridas',item.tandas ?? item.tandas_necesarias ?? item.plan?.tandas],
                        ['Costo estimado',item.costo_estimado ?? item.costo_reposicion ?? item.costo_total]
                    ];
                    let visibles=0;
                    for(const [et,valor] of campos)if(valor !== undefined && valor !== null && valor !== ''){
                        par(div,et,valor);visibles++;
                    }
                    if(!visibles)par(div,'Detalle',item.mensaje ?? 'Consultá el inventario para validar esta sugerencia.');
                    cont.append(div);
                }
            }catch(err){cont.replaceChildren();mensaje('rp-mensaje',err.message);}
            finally{$rp('rp-actualizar').disabled=false;}
        }
        function actualizarNota() {
            const motivo=d.motivos.find(m=>txt(m.codigo) === $rp('rp-motivo').value);
            $rp('rp-nota').required=Boolean(motivo?.requiere_nota);
            $rp('rp-nota-requerida').textContent=motivo?.requiere_nota?'*':'';
        }
        function cambiarTipo() {
            const plato=$rp('rp-tipo').value==='plato';
            $rp('rp-caja-insumo').hidden=plato;
            $rp('rp-caja-plato').hidden=!plato;
            $rp('rp-unidad').textContent=plato?'Cantidad de platos preparados (número entero).':'Cantidad en la unidad base del insumo seleccionado.';
        }
        async function cargarSelectores() {
            // Motivos, insumos y productos se consultan de forma independiente.
            const fuentes=[
                ['/perdidas/motivos',r=>{d.motivos=extraer(r);opciones('rp-motivo',d.motivos,'Seleccioná un motivo',x=>x.codigo,x=>x.etiqueta ?? x.codigo);actualizarNota();}],
                ['/insumos',r=>{d.insumos=extraer(r).filter(x=>x.activo!==false);opciones('rp-insumo',d.insumos,'Seleccioná un insumo',x=>x.id,x=>x.nombre);}],
                ['/productos',r=>{d.productos=extraer(r);opciones('rp-plato',d.productos,'Seleccioná un producto',x=>x.id,x=>x.nombre);}]
            ];
            const res=await Promise.allSettled(fuentes.map(async ([ruta,fn])=>fn(await llamarApi(ruta))));
            const errores=res.filter(r=>r.status==='rejected').map(r=>r.reason?.message).filter(Boolean);
            mensaje('rp-form-mensaje',errores.length?`Algunos campos no pudieron cargarse: ${errores.join(' | ')}`:'');
        }
        function pintarPerdidas() {
            const cont=$rp('rp-historial');cont.replaceChildren();
            const filtro=$rp('rp-buscar').value.toLocaleLowerCase('es-AR').trim();
            const registros=d.perdidas.filter(item=>[item.insumo_nombre,item.producto_nombre,item.motivo_etiqueta,item.motivo,item.nota,item.insumo?.nombre,item.producto?.nombre].map(txt).join(' ').toLocaleLowerCase('es-AR').includes(filtro));
            $rp('rp-total-registros').textContent=String(registros.length);
            if(!registros.length){cont.append(crear('p',filtro?'No hay coincidencias con tu búsqueda.':'No hay pérdidas registradas en la consulta actual.','sg-rp-note'));return;}
            registros.forEach(item=>{
                const div=crear('article','','sg-rp-card');const head=crear('div','','sg-rp-card-head');
                head.append(crear('h3',item.insumo_nombre ?? item.producto_nombre ?? item.insumo?.nombre ?? item.producto?.nombre ?? `Pérdida #${item.id ?? '—'}`));
                head.append(crear('span',item.motivo_etiqueta ?? item.motivo ?? 'Pérdida','sg-rp-badge'));div.append(head);
                if(item.cantidad!=null)par(div,'Cantidad',cantidadFmt(item.cantidad));
                if(item.fecha_hora ?? item.fecha) {
                    const fecha=new Date(item.fecha_hora ?? item.fecha);
                    par(div,'Fecha',Number.isFinite(fecha.getTime())?fecha.toLocaleString('es-AR'):item.fecha_hora ?? item.fecha);
                }
                if(item.nota)par(div,'Observaciones',item.nota);
                if(item.empleado_nombre)par(div,'Registró',item.empleado_nombre);
                div.append(crear('p','Registro histórico de solo lectura.'));
                cont.append(div);
            });
        }
        async function cargarPerdidas() {
            mensaje('rp-historial-mensaje','');$rp('rp-recargar-perdidas').disabled=true;
            try {
                const [lista, resumen]=await Promise.allSettled([llamarApi('/perdidas'),llamarApi('/perdidas/resumen')]);
                if(lista.status==='rejected')throw lista.reason;
                if(!Array.isArray(lista.value) && !Array.isArray(lista.value?.results)) throw new Error('El historial de pérdidas no devolvió una lista reconocible.');
                d.perdidas=extraer(lista.value);pintarPerdidas();
                $rp('rp-ultima-actualizacion').textContent=new Date().toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'});
                if(resumen.status==='fulfilled') {
                    const d0=resumen.value;
                    const costo=d0?.costo_total ?? d0?.total_costo ?? d0?.total_perdidas_costo ?? d0?.total_estimado;
                    $rp('rp-total-costo').textContent=costo!==undefined&&costo!==null?dinero(costo):'No informado';
                } else {
                    $rp('rp-total-costo').textContent='No disponible';
                    mensaje('rp-historial-mensaje','El historial cargó, pero no se pudo consultar el resumen de costos.');
                }
            }catch(err){d.perdidas=[];pintarPerdidas();mensaje('rp-historial-mensaje',err.message);}
            finally{$rp('rp-recargar-perdidas').disabled=false;}
        }
        async function registrar(e) {
            e.preventDefault();if(d.guardando)return;
            const tipo=$rp('rp-tipo').value;
            const motivo=$rp('rp-motivo').value;
            const valor=$rp('rp-cantidad').value.trim();
            const cantidad=numero(valor);
            const id=tipo==='plato'?$rp('rp-plato').value:$rp('rp-insumo').value;
            const nota=$rp('rp-nota').value.trim();
            if(!motivo||!d.motivos.some(x=>txt(x.codigo)===motivo)){mensaje('rp-form-mensaje','Seleccioná un motivo válido del servidor.');return;}
            if(!id||!Number.isInteger(Number(id))||Number(id)<=0){mensaje('rp-form-mensaje','Seleccioná un insumo o producto válido.');return;}
            if(!valor||!Number.isFinite(cantidad)||cantidad<=0||(tipo==='plato'&&!Number.isInteger(cantidad))||(!/^\d+(?:[.,]\d{1,3})?$/.test(valor))){mensaje('rp-form-mensaje','Ingresá una cantidad positiva válida. Para platos, un entero; para insumos, hasta tres decimales.');return;}
            const m=d.motivos.find(x=>txt(x.codigo)===motivo);
            if(m?.requiere_nota&&!nota){mensaje('rp-form-mensaje','Este motivo requiere una observación.');return;}
            const obj=tipo==='plato'?d.productos.find(x=>String(x.id)===id):d.insumos.find(x=>String(x.id)===id);
            const nombre=obj?.nombre??`ID ${id}`;
            const ok=await pedirConfirmacion({titulo:'Confirmar pérdida', texto:`Se descontarán ${cantidadFmt(cantidad)} ${tipo==='plato'?'platos':'unidades base'} de «${nombre}». Esta operación afecta el stock y queda registrada. ¿Confirmás?`,aceptar:'Sí, registrar pérdida',variante:'danger',icono:'!',origen:$rp('rp-guardar')});
            if(!ok)return;
            const payload={tipo,motivo,cantidad};
            payload[tipo==='plato'?'producto':'insumo']=Number(id);
            if(nota)payload.nota=nota;
            d.guardando=true;$rp('rp-guardar').disabled=true;mensaje('rp-form-mensaje','');
            try {
                await llamarApi('/perdidas',{method:'POST',body:JSON.stringify(payload)});
                $rp('rp-perdida-form').reset();cambiarTipo();actualizarNota();
                mensaje('rp-form-mensaje','Pérdida registrada correctamente. El servidor actualizó el inventario. Si necesitás comprobar cantidades, consultá Insumos o Movimientos de stock.',true);
                await cargarPerdidas();
            }catch(err){mensaje('rp-form-mensaje',err.message);}
            finally{d.guardando=false;$rp('rp-guardar').disabled=false;}
        }
        let configurado=false;
        function conectar() {
            if(configurado)return;configurado=true;
            document.querySelectorAll('[data-rp-tab]').forEach(b=>b.addEventListener('click',()=>setSubvista(b.dataset.rpTab)));
            $rp('rp-actualizar').addEventListener('click',cargarReposicion);
            $rp('rp-ir-compras').addEventListener('click',()=>activarVista('compras'));
            $rp('rp-tipo').addEventListener('change',cambiarTipo);
            $rp('rp-motivo').addEventListener('change',actualizarNota);
            $rp('rp-buscar').addEventListener('input',pintarPerdidas);
            $rp('rp-recargar-perdidas').addEventListener('click',cargarPerdidas);
            $rp('rp-perdida-form').addEventListener('submit',registrar);
            $rp('rp-perdida-form').addEventListener('reset',()=>setTimeout(()=>{cambiarTipo();actualizarNota();},0));
        }
        let iniciado=false;
        async function iniciar() {
            conectar();
            if(!iniciado){iniciado=true;await cargarSelectores();}
            setSubvista(sessionStorage.getItem('savage-admin-rp-subvista')||'reposicion');
        }
        return {iniciar, conectar};
    })();


    /* ============================================================
       P30 - Jornada y Especiales
       La API es la única fuente de información. Ninguna fecha,
       oferta o apertura de jornada se inventa en el frontend.
       ============================================================ */
    const moduloJornadaEspeciales = (() => {
        const q = id => document.getElementById(id);
        const datos = { subvista:'jornada', turnos:[], productos:[], especiales:[], jornadas:[], actual:null, editando:null, conectado:false, cargando:false, guardando:false };
        const dias = ['','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
        const array = x => Array.isArray(x) ? x : Array.isArray(x?.results) ? x.results : Array.isArray(x?.data) ? x.data : [];
        const texto = x => String(x ?? '').trim();
        const num = x => { const raw=String(x??'').trim().replace(/\s/g,''); const val=raw.includes(',')?raw.replace(/\./g,'').replace(',','.'):raw; return Number(val); };
        const money = x => Number.isFinite(Number(x)) ? Number(x).toLocaleString('es-AR',{style:'currency',currency:'ARS'}) : '—';
        const el = (tag, content='', classname='') => { const x=document.createElement(tag); x.textContent=texto(content); if(classname)x.className=classname; return x; };
        const field = (item,...keys) => {for(const k of keys)if(item?.[k]!==undefined&&item[k]!==null)return item[k];return null;};
        const objId = item => field(item,'id','id_especial','idEspecial','IdEspecial');
        const productoId = item => { const p=field(item,'producto','id_producto','producto_id','IdProducto'); return (p && typeof p==='object') ? field(p,'id','IdProducto') : p; };
        const turnoId = item => { const t=field(item,'turno','id_turno','turno_id','IdTurno'); return (t && typeof t==='object') ? field(t,'id','IdTurno') : t; };
        const precioEspecial = item => field(item,'precio_especial','precioEspecial','PrecioEspecial');
        const dia = item => field(item,'dia_semana','diaSemana','DiaSemana');
        const fecha = item => field(item,'fecha','Fecha');
        function avisoJe(id,text,success=false){aviso(id,text,success?'success':'error');}
        function opcion(id, items, placeholder, val, label) {
            const s=q(id); if(!s)return;
            s.replaceChildren(new Option(placeholder,''));
            items.forEach(i=>s.add(new Option(texto(label(i)),texto(val(i)))));
            sgSelect.actualizar();
        }
        function marca(id, abierto){const o=q(id);if(o)o.hidden=!abierto;}
        function cambiarTab(nombre) {
            datos.subvista=nombre==='especiales'?'especiales':'jornada';
            calendarioFecha.cerrar();
            ['jornada','especiales'].forEach(k=>{
                marca(`sg-je-subview-${k}`,k===datos.subvista);
                const b=document.querySelector(`[data-je-tab="${k}"]`);
                if(b){b.setAttribute('aria-selected',String(k===datos.subvista));b.tabIndex=k===datos.subvista?0:-1;}
            });
            sessionStorage.setItem('sg-admin-je-tab',datos.subvista);
            if(datos.subvista==='jornada') actualizarJornada(); else actualizarEspeciales();
        }
        function formatoFecha(s){
            if(!s)return '—';
            const match=texto(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
            return match?`${match[3]}/${match[2]}/${match[1]}`:texto(s);
        }
        function formatoFechaHora(s) {
            if(!s)return '—';
            const d=new Date(s);
            return Number.isNaN(d.getTime())?texto(s):d.toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});
        }
        function turnoNombre(item){return texto(field(item,'nombre','descripcion','etiqueta','Nombre','Descripcion')) || (objId(item)!=null?`Turno #${objId(item)}`:'Sin turno informado');}
        function nombreProducto(p) {return texto(field(p,'nombre','Nombre','titulo')) || `Producto #${objId(p)}`;}
        function pProducto(id){return datos.productos.find(p=>String(objId(p))===String(id));}
        function pTurno(id){return datos.turnos.find(t=>String(objId(t))===String(id));}
        function precioLista(p){return field(p,'precio','precio_lista','precio_venta','Precio','PrecioLista');}
        function pintarResumen() {
            const panel=q('je-estado'); panel.replaceChildren();
            const d=datos.actual;
            if(!d || (d.jornada===null) || d.activa===false || d.estado==='CERRADA'){
                panel.append(el('h3','No hay una jornada abierta'),el('p','Si corresponde, seleccioná un turno para abrir una nueva jornada.'));
                return;
            }
            const actual=(d?.jornada && typeof d.jornada==='object') ? d.jornada : d;
            panel.append(el('h3',`Jornada ${field(actual,'numero','id','id_jornada','IdJornada') ? '#'+field(actual,'numero','id','id_jornada','IdJornada') : 'activa'}`));
            for (const [nombre,valor] of [
                ['Estado',field(actual,'estado','Estado') ?? (d.activa?'Abierta':'Sin confirmar')],
                ['Apertura',formatoFechaHora(field(actual,'fecha_hora_apertura','fecha_apertura','inicio','fecha_inicio','FechaHoraApertura'))],
                ['Turno',turnoNombre(pTurno(turnoId(actual)) || {})]
            ]) { const p=el('p',`${nombre}: ${valor}`);panel.append(p);}
        }
        async function actualizarJornada(){
            avisoJe('je-estado-error','');
            const rs=await Promise.allSettled([llamarApi('/jornada/actual'),llamarApi('/jornadas')]);
            if(rs[0].status==='fulfilled'){datos.actual=rs[0].value; pintarResumen();}
            else {datos.actual=null; q('je-estado').textContent='Estado no disponible.'; avisoJe('je-estado-error',rs[0].reason?.message||'No se pudo consultar la jornada.');}
            if(rs[1].status==='fulfilled'){
                datos.jornadas=array(rs[1].value);
                const panel=q('je-historial');panel.replaceChildren();
                if(!datos.jornadas.length)panel.append(el('p','Todavía no hay jornadas en el historial.','sg-je-note'));
                datos.jornadas.slice().reverse().slice(0,30).forEach(j=>{
                    const card=el('article','','sg-je-card');
                    card.append(el('h3',`Jornada #${field(j,'id','id_jornada','IdJornada') ?? '—'}`));
                    card.append(el('p',`Apertura: ${formatoFechaHora(field(j,'fecha_hora_apertura','fecha_apertura','inicio','fecha_inicio'))}`));
                    card.append(el('p',`Cierre: ${formatoFechaHora(field(j,'fecha_hora_cierre','fecha_cierre','fin','fecha_fin'))}`));
                    panel.append(card);
                });
                avisoJe('je-historial-error','');
            }else{avisoJe('je-historial-error',rs[1].reason?.message||'No se pudo consultar el historial.');}
        }
        // La fecha se conserva como ISO YYYY-MM-DD para mantener intacto el contrato de la API.
        // El calendario visual no utiliza showPicker() ni input[type=date] del navegador.
        const calendarioFecha = (() => {
            let listo=false, popup=null, mesVisible=null;
            const nombresDias=['Lu','Ma','Mi','Ju','Vi','Sa','Do'];
            const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
            const parse=s=>{
                const m=String(s||'').match(/^(\d{4})-(\d{2})-(\d{2})$/);
                if(!m)return null;
                const d=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]));
                return d.getFullYear()===Number(m[1])&&d.getMonth()===Number(m[2])-1&&d.getDate()===Number(m[3])?d:null;
            };
            const fechaLarga=d=>d.toLocaleDateString('es-AR',{day:'numeric',month:'long',year:'numeric'});
            function sincronizar(){
                const date=parse(q('je-fecha').value),button=q('je-fecha-trigger');
                q('je-fecha-visual').textContent=date?fechaLarga(date):'Seleccioná una fecha';
                button.classList.toggle('sin-fecha',!date);
                button.setAttribute('aria-label',date?`Fecha seleccionada: ${fechaLarga(date)}. Cambiar fecha`:'Elegir fecha del especial');
            }
            function cerrar(devolverFoco=false){
                if(!popup||popup.hidden)return;
                popup.hidden=true;
                q('je-fecha-trigger').setAttribute('aria-expanded','false');
                if(devolverFoco)q('je-fecha-trigger').focus();
            }
            function elegir(fechaElegida){
                q('je-fecha').value=iso(fechaElegida);
                q('je-fecha').dispatchEvent(new Event('change',{bubbles:true}));
                sincronizar();cerrar(true);
            }
            function cambiarMes(n){
                mesVisible=new Date(mesVisible.getFullYear(),mesVisible.getMonth()+n,1);
                pintar();
            }
            function pintar(){
                popup.replaceChildren();
                const top=document.createElement('div');top.className='sg-je-calendar-top';
                const izq=document.createElement('button');izq.type='button';izq.className='sg-je-cal-arrow';izq.textContent='‹';izq.setAttribute('aria-label','Mes anterior');izq.addEventListener('click',()=>cambiarMes(-1));
                const titulo=document.createElement('div');titulo.className='sg-je-calendar-title';titulo.id='je-calendario-mes';titulo.setAttribute('aria-live','polite');const nombreMes=mesVisible.toLocaleDateString('es-AR',{month:'long',year:'numeric'});titulo.textContent=nombreMes.charAt(0).toUpperCase()+nombreMes.slice(1);
                const der=document.createElement('button');der.type='button';der.className='sg-je-cal-arrow';der.textContent='›';der.setAttribute('aria-label','Mes siguiente');der.addEventListener('click',()=>cambiarMes(1));
                top.append(izq,titulo,der);popup.append(top);
                const cab=document.createElement('div');cab.className='sg-je-cal-days';
                nombresDias.forEach(d=>{const x=document.createElement('span');x.textContent=d;x.className='sg-je-cal-weekday';cab.append(x)});
                popup.append(cab);
                const grid=document.createElement('div');grid.className='sg-je-cal-grid';grid.setAttribute('role','group');grid.setAttribute('aria-label','Elegí un día');
                const primero=new Date(mesVisible.getFullYear(),mesVisible.getMonth(),1);
                const corrimiento=(primero.getDay()+6)%7;
                const diasMes=new Date(mesVisible.getFullYear(),mesVisible.getMonth()+1,0).getDate();
                const total=Math.ceil((corrimiento+diasMes)/7)*7;
                const actual=parse(q('je-fecha').value);
                const hoy=new Date(),claveHoy=iso(hoy),claveAct=actual?iso(actual):'';
                for(let i=0;i<total;i++){
                    const fechaCelda=new Date(primero.getFullYear(),primero.getMonth(),i-corrimiento+1);
                    const clave=iso(fechaCelda);
                    const b=document.createElement('button');b.type='button';b.className='sg-je-cal-day';
                    b.textContent=String(fechaCelda.getDate());b.dataset.fecha=clave;
                    if(fechaCelda.getMonth()!==mesVisible.getMonth())b.classList.add('otra-mes');
                    if(clave===claveHoy)b.classList.add('hoy');
                    if(clave===claveAct)b.classList.add('elegido');
                    b.setAttribute('aria-label',fechaLarga(fechaCelda));b.setAttribute('aria-pressed',String(clave===claveAct));
                    b.addEventListener('click',()=>elegir(fechaCelda));grid.append(b);
                }
                popup.append(grid);
                const acciones=document.createElement('div');acciones.className='sg-je-cal-actions';
                const borrar=document.createElement('button');borrar.type='button';borrar.textContent='Borrar fecha';borrar.addEventListener('click',()=>{q('je-fecha').value='';sincronizar();cerrar(true)});
                const hoyBtn=document.createElement('button');hoyBtn.type='button';hoyBtn.textContent='Ir a hoy';hoyBtn.addEventListener('click',()=>{const d=new Date();mesVisible=new Date(d.getFullYear(),d.getMonth(),1);pintar();colocar();popup.querySelector(`[data-fecha="${iso(d)}"]`)?.focus();});
                acciones.append(borrar,hoyBtn);popup.append(acciones);
            }
            function colocar(){
                if(!popup||popup.hidden)return;
                const rect=q('je-fecha-trigger').getBoundingClientRect();
                const ancho=popup.getBoundingClientRect().width,alto=popup.getBoundingClientRect().height;
                const izq=Math.max(12,Math.min(rect.left,window.innerWidth-ancho-12));
                const debajo=window.innerHeight-rect.bottom>=Math.min(alto,410)+12;
                const arriba=Math.max(12,rect.top-alto-7),abajo=Math.min(window.innerHeight-alto-12,rect.bottom+7);
                popup.style.left=`${izq}px`;popup.style.top=`${debajo?abajo:arriba}px`;
            }
            function abrir(){
                if(!popup.hidden){cerrar(true);return;}
                const seleccionado=parse(q('je-fecha').value),d=seleccionado||new Date();
                mesVisible=new Date(d.getFullYear(),d.getMonth(),1);
                popup.hidden=false;q('je-fecha-trigger').setAttribute('aria-expanded','true');
                pintar();colocar();
                requestAnimationFrame(()=>popup.querySelector(`[data-fecha="${seleccionado?iso(seleccionado):iso(new Date())}"]`)?.focus());
            }
            function crear(){
                if(listo)return;listo=true;
                popup=document.createElement('div');popup.id='je-calendario';popup.hidden=true;
                popup.setAttribute('role','dialog');popup.setAttribute('aria-modal','false');popup.setAttribute('aria-label','Calendario para fecha especial');
                document.body.append(popup);
                q('je-fecha-trigger').addEventListener('click',abrir);
                document.addEventListener('pointerdown',e=>{if(!popup.hidden&&!popup.contains(e.target)&&!q('je-fecha-trigger').contains(e.target))cerrar();});
                document.addEventListener('keydown',e=>{
                    if(popup.hidden)return;
                    if(e.key==='Escape'){e.preventDefault();cerrar(true);return;}
                    if(!popup.contains(document.activeElement))return;
                    if(e.key==='PageUp'||e.key==='PageDown'){e.preventDefault();cambiarMes(e.key==='PageUp'?-1:1);colocar();popup.querySelector('.sg-je-cal-day')?.focus();return;}
                    const offset={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[e.key];
                    if(offset===undefined)return;
                    const foco=document.activeElement,d=parse(foco.dataset?.fecha);if(!d)return;
                    e.preventDefault();d.setDate(d.getDate()+offset);
                    if(d.getMonth()!==mesVisible.getMonth()||d.getFullYear()!==mesVisible.getFullYear()){
                        mesVisible=new Date(d.getFullYear(),d.getMonth(),1);pintar();colocar();
                    }
                    popup.querySelector(`[data-fecha="${iso(d)}"]`)?.focus();
                });
                window.addEventListener('resize',colocar);
                window.addEventListener('scroll',e=>{if(!popup.hidden&&e.target!==popup&&!popup.contains(e.target))cerrar();},true);
                sincronizar();
            }
            return {crear,sincronizar,cerrar};
        })();
        function cambiarModalidad(){
            const porFecha=q('je-modalidad').value==='fecha';
            marca('je-caja-dia',!porFecha);
            marca('je-caja-fecha',porFecha);
            q('je-dia').required=!porFecha;
            // La fecha ISO se valida en guardarEspecial(), porque el input es oculto.
            calendarioFecha.cerrar();
            calendarioFecha.sincronizar();
        }
        function pintarPrecio(){
            const p=pProducto(q('je-producto').value);
            const n=p?precioLista(p):null;
            q('je-precio-nota').textContent=p ? `Precio de lista: ${n!=null?money(n):'no informado por la API'}. El precio de oferta debe ser inferior al precio de lista cuando se publique como descuento.`:'Elegí un producto para consultar su precio de lista.';
        }
        function nombreEspecial(e){const p=pProducto(productoId(e));return texto(field(e,'producto_nombre','nombre_producto','ProductoNombre')) || (p?nombreProducto(p):`Producto #${productoId(e) ?? '—'}`);}
        function periodoEspecial(e){
            return fecha(e) ? `Fecha: ${formatoFecha(fecha(e))}` : `Día: ${dias[Number(dia(e))] || 'no informado'}`;
        }
        function turnoEspecial(e){const t=turnoId(e);return t?` · ${turnoNombre(pTurno(t) || {id:t})}`:' · Todos los turnos';}
        function cardEspecial(e,detallado=true){
            const card=el('article','','sg-je-card');
            card.append(el('h3',nombreEspecial(e)));
            card.append(el('p',`${periodoEspecial(e)}${turnoEspecial(e)}`));
            card.append(el('p',`Oferta: ${money(precioEspecial(e))}`));
            const p=pProducto(productoId(e));
            if(p && precioLista(p)!=null)card.append(el('p',`Precio habitual: ${money(precioLista(p))}`));
            if(detallado && objId(e)!=null){
                const acciones=el('div','','sg-admin-actions');
                const editar=el('button','Editar','sg-admin-secondary');editar.type='button';editar.addEventListener('click',()=>editarEspecial(e));
                const quitar=el('button','Eliminar','sg-admin-secondary sg-je-danger');quitar.type='button';quitar.addEventListener('click',()=>eliminarEspecial(e));
                acciones.append(editar,quitar);card.append(acciones);
            }
            return card;
        }
        function pintarEspeciales(){
            const lista=q('je-lista'),semana=q('je-semana'),fechas=q('je-fechas');
            lista.replaceChildren();semana.replaceChildren();fechas.replaceChildren();
            if(!datos.especiales.length)lista.append(el('p','Todavía no hay especiales guardados en el servidor.','sg-je-note'));
            datos.especiales.forEach(e=>lista.append(cardEspecial(e)));
            for(let n=1;n<=7;n++){
                const caja=el('section','','sg-je-day');caja.append(el('h3',dias[n]));
                const regs=datos.especiales.filter(e=>!fecha(e)&&Number(dia(e))===n);
                if(!regs.length)caja.append(el('p','Sin ofertas programadas.'));
                regs.forEach(e=>{caja.append(el('p',`${nombreEspecial(e)} · ${money(precioEspecial(e))}`));});
                semana.append(caja);
            }
            const fechasReg=datos.especiales.filter(e=>!!fecha(e)).sort((a,b)=>texto(fecha(a)).localeCompare(texto(fecha(b))));
            if(!fechasReg.length)fechas.append(el('p','No hay fechas puntuales programadas.','sg-je-note'));
            fechasReg.forEach(e=>fechas.append(cardEspecial(e,false)));
        }
        async function cargarCatalogos(){
            const rs=await Promise.allSettled([llamarApi('/productos?incluir_inactivos=true'),llamarApi('/turnos')]);
            if(rs[0].status==='fulfilled'){
                datos.productos=array(rs[0].value).filter(p=>p.activo!==false);
                opcion('je-producto',datos.productos,'Seleccioná un producto',objId,nombreProducto);
            }else{avisoJe('je-form-mensaje',rs[0].reason?.message||'No se pudieron cargar productos.');}
            if(rs[1].status==='fulfilled'){
                datos.turnos=array(rs[1].value);
                opcion('je-turno-especial',datos.turnos,'Todos los turnos',objId,turnoNombre);
                opcion('je-turno-jornada',datos.turnos,'Turno no seleccionado',objId,turnoNombre);
            }else{avisoJe('je-accion-mensaje',rs[1].reason?.message||'No se pudieron consultar los turnos.');}
            pintarPrecio();
        }
        async function actualizarEspeciales(){
            avisoJe('je-lista-error','');
            try{
                datos.especiales=array(await llamarApi('/especiales'));
                pintarEspeciales();
            }catch(e){avisoJe('je-lista-error',e.message||'No se pudieron consultar las ofertas.');}
        }
        function limpiarEspecial(){
            datos.editando=null;q('je-especial-form').reset();
            q('je-form-titulo').textContent='Programar especial del día';
            q('je-guardar').textContent='Guardar especial';q('je-cancelar-edicion').hidden=true;
            cambiarModalidad();calendarioFecha.sincronizar();pintarPrecio();sgSelect.actualizar();
        }
        function editarEspecial(e){
            datos.editando=objId(e);q('je-producto').value=texto(productoId(e));
            q('je-precio').value=texto(precioEspecial(e));q('je-turno-especial').value=texto(turnoId(e));
            q('je-modalidad').value=fecha(e)?'fecha':'semanal';cambiarModalidad();
            q('je-fecha').value=texto(fecha(e)).slice(0,10);q('je-dia').value=texto(dia(e)??'1');
            q('je-form-titulo').textContent=`Editar especial #${datos.editando}`;
            q('je-guardar').textContent='Guardar cambios';q('je-cancelar-edicion').hidden=false;
            q('je-form-mensaje').hidden=true;calendarioFecha.sincronizar();pintarPrecio();sgSelect.actualizar();
            q('je-especial-form').scrollIntoView({behavior:'smooth',block:'start'});
        }
        async function guardarEspecial(event){
            event.preventDefault();if(datos.guardando)return;
            const id=Number(q('je-producto').value),p=pProducto(id),precio=num(q('je-precio').value),base=Number(precioLista(p));
            if(!id||!Number.isFinite(precio)||precio<=0){avisoJe('je-form-mensaje','Seleccioná un producto y un precio especial válido.');return;}
            if(p&&precioLista(p)!=null&&Number.isFinite(base)&&precio>=base){avisoJe('je-form-mensaje','El precio de oferta debe ser menor que el precio de lista del producto.');return;}
            const esFecha=q('je-modalidad').value==='fecha';
            const valorFecha=q('je-fecha').value;
            if(esFecha&&!/^\d{4}-\d{2}-\d{2}$/.test(valorFecha)){avisoJe('je-form-mensaje','Seleccioná una fecha válida.');return;}
            // DRF estándar: relaciones por PK, campos del modelo en snake_case.
            // Si David utiliza otros nombres, el backend debe responder con el error de validación.
            const payload={producto:id,precio_especial:precio,turno:q('je-turno-especial').value?Number(q('je-turno-especial').value):null,
                dia_semana:esFecha?null:Number(q('je-dia').value),fecha:esFecha?valorFecha:null};
            const ok=await pedirConfirmacion({titulo:datos.editando?'Modificar promoción':'Publicar promoción',
                texto:`${p?nombreProducto(p):'Producto'} · ${money(precio)} · ${esFecha?formatoFecha(valorFecha):dias[payload.dia_semana]}. Los cambios quedarán guardados en la API.`,
                aceptar:datos.editando?'Guardar cambios':'Guardar especial',variante:'success',icono:'✓'});
            if(!ok)return;
            datos.guardando=true;q('je-guardar').disabled=true;avisoJe('je-form-mensaje','');
            try{
                const ruta=datos.editando?`/especiales/${encodeURIComponent(datos.editando)}`:'/especiales';
                await llamarApi(ruta,{method:datos.editando?'PATCH':'POST',body:JSON.stringify(payload)});
                limpiarEspecial();await actualizarEspeciales();
                avisoJe('je-form-mensaje','Especial guardado en el servidor. Verificá su vigencia desde el catálogo.',true);
            }catch(err){avisoJe('je-form-mensaje',err.message||'No se pudo guardar. Revisá el contrato de la API.');}
            finally{datos.guardando=false;q('je-guardar').disabled=false;}
        }
        async function eliminarEspecial(e){
            if(datos.guardando)return;
            const id=objId(e);if(id==null)return;
            const ok=await pedirConfirmacion({titulo:'Eliminar especial',texto:`¿Eliminar la programación de «${nombreEspecial(e)}»? Esta acción afecta las ofertas futuras.`,aceptar:'Eliminar',variante:'danger',icono:'!'});
            if(!ok)return;
            datos.guardando=true;
            try{
                await llamarApi(`/especiales/${encodeURIComponent(id)}`,{method:'DELETE'});
                if(String(datos.editando)===String(id))limpiarEspecial();
                await actualizarEspeciales();
            }catch(err){avisoJe('je-lista-error',err.message||'El servidor rechazó la operación.');}
            finally{datos.guardando=false;}
        }
        async function accionJornada(accion){
            if(datos.guardando)return;
            const turno=q('je-turno-jornada').value;
            const abrir=accion==='abrir';
            if(abrir&&datos.turnos.length&&!turno){avisoJe('je-accion-mensaje','Seleccioná un turno antes de abrir la jornada.');return;}
            const ok=await pedirConfirmacion({titulo:abrir?'Abrir jornada':'Cerrar jornada',
                texto:abrir?'¿Confirmás la apertura de una nueva jornada operativa?':
                    '¿Confirmás el cierre de la jornada? Comprobá antes las mesas, cuentas y pedidos pendientes.',
                aceptar:abrir?'Abrir jornada':'Cerrar jornada',variante:abrir?'success':'danger',icono:abrir?'✓':'!'});
            if(!ok)return;
            datos.guardando=true;q('je-abrir-jornada').disabled=true;q('je-cerrar-jornada').disabled=true;
            try{
                await llamarApi(abrir?'/jornada/abrir':'/jornada/cerrar',{method:'POST',...(abrir&&turno?{body:JSON.stringify({turno:Number(turno)})}:{})});
                avisoJe('je-accion-mensaje',abrir?'Jornada abierta correctamente.':'Jornada cerrada correctamente.',true);
                await actualizarJornada();
            }catch(err){avisoJe('je-accion-mensaje',err.message||'La API rechazó la operación.');}
            finally{datos.guardando=false;q('je-abrir-jornada').disabled=false;q('je-cerrar-jornada').disabled=false;}
        }
        function conectar(){
            if(datos.conectado)return;datos.conectado=true;
            calendarioFecha.crear();
            document.querySelectorAll('[data-je-tab]').forEach(b=>b.addEventListener('click',()=>cambiarTab(b.dataset.jeTab)));
            q('je-actualizar-jornada').addEventListener('click',actualizarJornada);
            q('je-actualizar-historial').addEventListener('click',actualizarJornada);
            q('je-actualizar-especiales').addEventListener('click',actualizarEspeciales);
            q('je-modalidad').addEventListener('change',cambiarModalidad);
            q('je-producto').addEventListener('change',pintarPrecio);
            q('je-especial-form').addEventListener('submit',guardarEspecial);
            q('je-cancelar-edicion').addEventListener('click',limpiarEspecial);
            q('je-abrir-jornada').addEventListener('click',()=>accionJornada('abrir'));
            q('je-cerrar-jornada').addEventListener('click',()=>accionJornada('cerrar'));
        }
        let iniciado=false;
        async function iniciar(){
            conectar();
            if(!iniciado){iniciado=true;await cargarCatalogos();}
            cambiarTab(sessionStorage.getItem('sg-admin-je-tab')||'jornada');
        }
        return {iniciar,conectar};
    })();

    async function verificarAcceso() {
        try {
            const perfil = await llamarApi('/me');
            if (!['Admin', 'Gerente'].includes(perfil?.rol)) {
                $('admin-acceso-error').hidden = false;
                aviso('admin-acceso-error', 'No tiene permisos para acceder a Administración.');
                $('admin-contenido').querySelectorAll('.sg-admin-view').forEach(v => v.hidden = true);
                document.querySelectorAll('[data-admin-tab]').forEach(b => { b.disabled = true; });
                return;
            }
            estado.autorizado = true;
            // Restaurar la sección abierta antes de actualizar la página.
            activarVista(sessionStorage.getItem(CLAVE_VISTA_ADMIN) || 'menu');
            $('admin-perfil-nombre').textContent = `${perfil.nombre || ''} ${perfil.apellido || ''} (${perfil.rol})`.trim();
            $('admin-ir-gerente').hidden = perfil.rol !== 'Gerente';
        } catch (error) {
            aviso('admin-acceso-error', error.message);
            $('admin-perfil-nombre').textContent = 'Sesión sin verificar';
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        sgSelect.iniciar();
        moduloRecetas.conectar();
        document.addEventListener('click', () => queueMicrotask(sgSelect.actualizar), true);
        for (const boton of document.querySelectorAll('[data-admin-tab]')) {
            boton.addEventListener('click', () => activarVista(boton.dataset.adminTab));
        }
        // El botón del tema queda en la barra inferior, como en Gerencia.
        const botonTema = $('admin-tema');
        const nombreTema = $('admin-tema-texto');
        const mostrarTema = () => {
            nombreTema.textContent = document.body.classList.contains('light-mode') ? 'Modo: Claro' : 'Modo: Oscuro';
        };
        if (localStorage.getItem('savage-tema') === 'light') document.body.classList.add('light-mode');
        mostrarTema();
        botonTema.addEventListener('click', () => {
            document.body.classList.toggle('light-mode');
            localStorage.setItem('savage-tema', document.body.classList.contains('light-mode') ? 'light' : 'dark');
            mostrarTema();
        });
        $('admin-ir-gerente').addEventListener('click', () => { window.location.href = 'gerente.html'; });
        $('admin-salir').addEventListener('click', () => {
            sessionStorage.removeItem('savage_token');
            sessionStorage.removeItem('savage_usuario');
            sessionStorage.removeItem(CLAVE_VISTA_ADMIN);
            window.location.href = 'login.html';
        });
        $('proveedor-form').addEventListener('submit', guardarProveedor);
        $('proveedor-cancelar').addEventListener('click', limpiarFormulario);
        $('proveedor-buscar').addEventListener('input', pintarProveedores);
        $('proveedor-inactivos').addEventListener('change', pintarProveedores);
        $('proveedor-recargar').addEventListener('click', cargarProveedores);
        $('insumo-form').addEventListener('submit', guardarInsumo);
        $('insumo-tipo-medida').addEventListener('change', actualizarUnidadInsumo);
        $('insumo-cancelar').addEventListener('click', limpiarFormularioInsumo);
        $('insumo-buscar').addEventListener('input', pintarInsumos);
        $('insumo-filtrar-tipo').addEventListener('change', pintarInsumos);
        $('insumo-inactivos').addEventListener('change', pintarInsumos);
        $('insumo-recargar').addEventListener('click', cargarInsumos);
        $('insumo-asociacion-form').addEventListener('submit', guardarProveedoresInsumo);
        $('insumo-proveedores-cancelar').addEventListener('click', cerrarProveedoresInsumo);
        $('compra-form').addEventListener('submit', registrarCompra);
        $('compra-agregar-linea').addEventListener('click', agregarLineaCompra);
        $('compra-limpiar').addEventListener('click', limpiarCompra);
        $('compra-actualizar-historial').addEventListener('click', cargarHistorialCompras);
        $('compra-filtrar-proveedor').addEventListener('change', cargarHistorialCompras);
        $('lote-actualizar').addEventListener('click', cargarLotes);
        $('lote-filtrar-estado').addEventListener('change', cargarLotes);
        $('lote-filtrar-insumo').addEventListener('change', cargarLotes);
        $('lote-baja-form').addEventListener('submit', registrarBajaLote);
        $('lote-baja-cancelar').addEventListener('click', cerrarBajaLote);
        $('mov-form').addEventListener('submit', cargarMovimientos);
        $('mov-limpiar').addEventListener('click', limpiarFiltrosMovimientos);
        $('ajuste-form').addEventListener('submit', registrarAjuste);
        $('ajuste-insumo').addEventListener('change', actualizarPreviaAjuste);
        $('ajuste-cantidad').addEventListener('input', actualizarPreviaAjuste);
        $('ajuste-actualizar').addEventListener('click', cargarInsumosAjuste);
        $('verificacion-ejecutar').addEventListener('click', verificarLibroAjustes);
        actualizarUnidadInsumo();
        verificarAcceso();
    });
})();
