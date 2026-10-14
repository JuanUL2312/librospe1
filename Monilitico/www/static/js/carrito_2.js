
    // ===============================
    // VARIABLES GLOBALES
    // ===============================
    let carrito = [];
    let cuponAplicado = null;
    let descuento = 0;
    let tipoEntregaSeleccionado = 'recojo';
    let direccionEntrega = '';
    let mapaCarrito = null;
    let marcadorCarrito = null;

    // ===============================
    // FUNCIÓN PARA VALIDAR STOCK CON EL SERVIDOR
    // ===============================
    async function validarStockProducto(productoId, cantidadDeseada) {
        try {
            const response = await fetch(`/api/productos/${productoId}/stock`);
            const data = await response.json();
            
            if (!response.ok) {
                console.error("Error al consultar stock:", data.error);
                return { valido: true, stockDisponible: 999, nombre: "Producto" };
            }
            
            const stockDisponible = data.stock;
            return { 
                valido: cantidadDeseada <= stockDisponible, 
                stockDisponible: stockDisponible,
                nombre: data.nombre
            };
        } catch (error) {
            console.error("Error validando stock:", error);
            return { valido: true, stockDisponible: 999, nombre: "Producto" };
        }
    }

    // ===============================
    // CARGAR DIRECCIÓN DEL CLIENTE DESDE BASE DE DATOS
    // ===============================
    async function cargarDireccionCliente() {
        const usuarioLogueado = document.getElementById('usuarioLogueado')?.value === 'true';
        if (!usuarioLogueado) {
            console.log("Usuario no logueado, no se carga dirección");
            return;
        }

        try {
            console.log("Solicitando dirección a /api/cliente/direccion");
            const response = await fetch('/api/cliente/direccion');

            if (!response.ok) {
                console.error("Error HTTP:", response.status);
                return;
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.error("La respuesta no es JSON:", contentType);
                return;
            }

            const data = await response.json();
            console.log("Respuesta de dirección:", data);

            if (data.success && data.direccion) {
                const direccionInput = document.getElementById('direccion');
                const direccionAyuda = document.getElementById('direccionAyuda');
                if (direccionInput) {
                    direccionInput.value = data.direccion;
                    if (direccionAyuda) {
                        direccionAyuda.innerHTML = '<i class="fas fa-check-circle text-success"></i> Dirección cargada desde tu perfil. Puedes modificarla si lo deseas.';
                        setTimeout(() => {
                            if (direccionAyuda) direccionAyuda.innerHTML = '';
                        }, 5000);
                    }
                    console.log("📍 Dirección cargada desde perfil:", data.direccion);
                }
            } else {
                console.log("No hay dirección guardada en el perfil");
            }
        } catch (error) {
            console.error("Error cargando dirección:", error);
        }
    }

    // ===============================
    // INICIALIZAR MAPA DE CARRITO
    // ===============================
    function inicializarMapaCarrito() {
        console.log('🗺️ inicializarMapaCarrito llamado');
        
        const mapaDiv = document.getElementById('mapaCarrito');
        if (!mapaDiv) {
            console.error('❌ No se encontró el div #mapaCarrito');
            return;
        }

        // Verificar que el contenedor sea visible
        const rect = mapaDiv.getBoundingClientRect();
        console.log('📐 Dimensiones del contenedor:', rect.width, 'x', rect.height);
        
        if (rect.width === 0 || rect.height === 0) {
            console.warn('⚠️ Contenedor tiene dimensiones 0, reintentando...');
            setTimeout(() => inicializarMapaCarrito(), 500);
            return;
        }

        // Si el mapa ya existe, solo redimensionar
        if (mapaCarrito) {
            mapaCarrito.invalidateSize();
            mapaCarrito.setView([-12.0464, -77.0428], 13);
            console.log('✅ Mapa redimensionado');
            return;
        }

        // Mostrar indicador de carga
        const cargando = document.getElementById('mapaCargando');
        if (cargando) cargando.style.display = 'block';

        // Centro inicial por defecto: Lima, Perú
        mapaCarrito = L.map('mapaCarrito').setView([-12.0464, -77.0428], 13);

        // Usar solo OpenStreetMap (no requiere API key)
        const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            updateWhenIdle: true,
            keepBuffer: 2
        });

        osmLayer.addTo(mapaCarrito);

        // Ocultar indicador de carga cuando el mapa esté listo
        mapaCarrito.whenReady(() => {
            if (cargando) {
                setTimeout(() => {
                    cargando.style.display = 'none';
                }, 500);
            }
        });

        // Icono personalizado para el marcador
        const iconoMarcador = L.icon({
            iconUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-icon.png',
            iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-icon-2x.png',
            shadowUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });

        // Evento clic en el mapa
        mapaCarrito.on('click', function(e) {
            const lat = e.latlng.lat.toFixed(6);
            const lng = e.latlng.lng.toFixed(6);

            if (marcadorCarrito) {
                marcadorCarrito.setLatLng(e.latlng);
            } else {
                marcadorCarrito = L.marker(e.latlng, { icon: iconoMarcador }).addTo(mapaCarrito);
            }

            marcadorCarrito.bindPopup('<b>Tu ubicación de entrega</b><br>Lat: ' + lat + '<br>Lng: ' + lng).openPopup();

            document.getElementById('latitud').value = lat;
            document.getElementById('longitud').value = lng;

            const mapaAviso = document.getElementById('mapaAviso');
            if (mapaAviso) {
                mapaAviso.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i> Ubicación marcada correctamente';
                mapaAviso.classList.remove('text-muted');
                mapaAviso.classList.add('text-success', 'fw-bold');
            }
        });
    }

    // ===============================
    // SELECCIONAR TIPO DE ENTREGA
    // ===============================
    function seleccionarEntrega(tipo) {
        tipoEntregaSeleccionado = tipo;

        document.querySelectorAll('.delivery-option').forEach(opt => {
            opt.classList.remove('selected');
        });
        document.querySelector(`.delivery-option[data-tipo="${tipo}"]`).classList.add('selected');

        const direccionDiv = document.getElementById('direccionEntrega');
        const envioTexto = document.getElementById('envioTexto');
        const direccionInput = document.getElementById('direccion');

        if (tipo === 'delivery') {
            direccionDiv.style.display = 'block';
            envioTexto.innerHTML = 'S/. 5.00';
            cargarDireccionCliente();
            // Inicializar mapa después de que el contenedor sea visible
            // Usar requestAnimationFrame para asegurar que el DOM se renderizó
            requestAnimationFrame(() => {
                setTimeout(() => {
                    inicializarMapaCarrito();
                    // Forzar redimensionado del mapa después de que sea visible
                    if (mapaCarrito) {
                        setTimeout(() => {
                            mapaCarrito.invalidateSize();
                            mapaCarrito.setView([-12.0464, -77.0428], 13);
                        }, 100);
                    }
                }, 150);
            });
        } else {
            direccionDiv.style.display = 'none';
            envioTexto.innerHTML = 'Gratis';
            if (direccionInput) direccionInput.value = '';
            // Limpiar coordenadas si cambia a recojo
            const lat = document.getElementById('latitud');
            const lng = document.getElementById('longitud');
            if (lat) lat.value = '';
            if (lng) lng.value = '';
            if (marcadorCarrito) {
                mapaCarrito.removeLayer(marcadorCarrito);
                marcadorCarrito = null;
            }
        }

        actualizarTotales();
    }

    // ===============================
    // IR A CHECKOUT
    // ===============================
    function irACheckout() {
        let usuarioLogueado = document.getElementById('usuarioLogueado')?.value === 'true';

        if (!usuarioLogueado) {
            Swal.fire({
                icon: 'warning',
                title: 'Inicia sesión',
                text: 'Debes iniciar sesión para comprar',
                confirmButtonText: 'Iniciar',
                showCancelButton: true
            }).then((result) => {
                if (result.isConfirmed) window.location.href = '/login-cliente';
            });
            return;
        }

        if (carrito.length === 0) {
            Swal.fire({
                icon: 'error',
                title: 'Carrito vacío',
                text: 'Agrega productos'
            });
            return;
        }

        if (tipoEntregaSeleccionado === 'delivery') {
            let direccion = document.getElementById('direccion')?.value.trim();
            if (!direccion) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Dirección requerida',
                    text: 'Ingresa tu dirección de entrega'
                });
                return;
            }
            let lat = document.getElementById('latitud')?.value;
            let lng = document.getElementById('longitud')?.value;
            if (!lat || !lng) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Ubicación en el mapa requerida',
                    text: 'Marca tu ubicación exacta en el mapa haciendo clic'
                });
                return;
            }
            direccionEntrega = direccion;
        } else {
            direccionEntrega = '';
        }

        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        if (cuponAplicado) {
            localStorage.setItem('cuponAplicado', JSON.stringify(cuponAplicado));
            localStorage.setItem('descuento', descuento);
        }
        localStorage.setItem('tipoEntrega', tipoEntregaSeleccionado);
        localStorage.setItem('direccionEntrega', direccionEntrega);

        // Guardar coordenadas del mapa
        if (tipoEntregaSeleccionado === 'delivery') {
            let lat = document.getElementById('latitud')?.value || '';
            let lng = document.getElementById('longitud')?.value || '';
            localStorage.setItem('latitudEntrega', lat);
            localStorage.setItem('longitudEntrega', lng);
        }

        window.location.href = '/checkout';
    }

    // ===============================
    // APLICAR CUPÓN
    // ===============================
    function aplicarCupon() {
        let codigo = document.getElementById('cuponInput')?.value.toUpperCase();
        let mensajeDiv = document.getElementById('mensajeCupon');
        let descuentoRow = document.getElementById('descuentoRow');

        const cupones = {
            'LIBROS10': { descuento: 10, tipo: 'porcentaje', nombre: '10% off' },
            'BIENVENIDO5': { descuento: 5, tipo: 'fijo', nombre: 'S/5 off' },
            'FREESHIP': { descuento: 5, tipo: 'envio', nombre: 'Envío gratis' }
        };

        if (cupones[codigo]) {
            cuponAplicado = cupones[codigo];
            let subtotal = calcularSubtotal();

            if (cuponAplicado.tipo === 'envio') {
                descuento = 5;
                mensajeDiv.innerHTML = '<span class="text-success">✅ Envío gratis</span>';
            } else if (cuponAplicado.tipo === 'porcentaje') {
                descuento = subtotal * 0.1;
                mensajeDiv.innerHTML = '<span class="text-success">✅ 10% descuento</span>';
            } else {
                descuento = 5;
                mensajeDiv.innerHTML = '<span class="text-success">✅ S/5 descuento</span>';
            }
            descuentoRow.style.display = 'flex';
            actualizarTotales();
            Swal.fire({ icon: 'success', title: '¡Cupón aplicado!', timer: 1500, showConfirmButton: false });
        } else {
            mensajeDiv.innerHTML = '<span class="text-danger">❌ Inválido</span>';
        }
    }

    // ===============================
    // CALCULAR SUBTOTAL
    // ===============================
    function calcularSubtotal() {
        return carrito.reduce((s, i) => s + (i.precio * i.cantidad), 0);
    }

    // ===============================
    // ACTUALIZAR TOTALES
    // ===============================
    function actualizarTotales() {
        let subtotal = calcularSubtotal();
        let costoEnvio = 0;

        if (tipoEntregaSeleccionado === 'delivery' && cuponAplicado?.tipo !== 'envio') {
            costoEnvio = 5;
            document.getElementById('envioTexto').innerHTML = 'S/. 5.00';
        } else if (tipoEntregaSeleccionado === 'delivery' && cuponAplicado?.tipo === 'envio') {
            document.getElementById('envioTexto').innerHTML = 'Gratis (Cupón)';
        } else {
            document.getElementById('envioTexto').innerHTML = 'Gratis';
        }

        let descuentoAplicado = (cuponAplicado?.tipo === 'envio' && tipoEntregaSeleccionado === 'delivery') ? 0 : Math.min(descuento, subtotal);
        let total = subtotal - descuentoAplicado + costoEnvio;

        document.getElementById('subtotalCarrito').innerHTML = 'S/. ' + subtotal.toFixed(2);
        document.getElementById('totalFinal').innerHTML = 'S/. ' + total.toFixed(2);
        document.getElementById('descuentoMonto').innerHTML = '-S/. ' + descuentoAplicado.toFixed(2);
        document.getElementById('itemCount').innerHTML = carrito.reduce((sum, item) => sum + parseInt(item.cantidad || 1), 0);
    }

    // ===============================
    // VACIAR CARRITO
    // ===============================
    function vaciarCarrito() {
        Swal.fire({
            title: '¿Vaciar carrito?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            confirmButtonText: 'Sí'
        }).then((r) => {
            if (r.isConfirmed) {
                carrito = [];
                localStorage.removeItem('carritoCliente');
                localStorage.removeItem('cuponAplicado');
                localStorage.removeItem('descuento');
                localStorage.removeItem('tipoEntrega');
                localStorage.removeItem('direccionEntrega');
                cuponAplicado = null;
                descuento = 0;
                tipoEntregaSeleccionado = 'recojo';
                renderizarCarrito();
                Swal.fire('¡Vaciado!', '', 'success');
            }
        });
    }

    // ===============================
    // CAMBIAR CANTIDAD (CON VALIDACIÓN DE STOCK)
    // ===============================
    async function cambiarCantidad(idx, delta) {
        let nueva = carrito[idx].cantidad + delta;
        if (nueva < 1) return;
        
        let producto = carrito[idx];
        
        // Validar stock SOLO si estamos aumentando la cantidad
        if (delta > 0) {
            const stockInfo = await validarStockProducto(producto.id, nueva);
            
            if (!stockInfo.valido) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Stock insuficiente',
                    text: `Solo hay ${stockInfo.stockDisponible} unidades disponibles de "${producto.nombre}"`,
                    confirmButtonColor: '#3085d6'
                });
                return;
            }
            
            // Actualizar el stock guardado en el carrito
            carrito[idx].stock = stockInfo.stockDisponible;
        }
        
        carrito[idx].cantidad = nueva;
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        
        // Si hay cupón aplicado, eliminarlo al cambiar cantidades
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
            document.getElementById('descuentoRow').style.display = 'none';
            document.getElementById('mensajeCupon').innerHTML = '';
        }
        
        renderizarCarrito();
    }

    // ===============================
    // CAMBIAR CANTIDAD DESDE TECLADO (INPUT)
    // ===============================
    async function cambiarCantidadInput(idx, input) {
        let valor = parseInt(input.value, 10);
        if (isNaN(valor) || valor < 1) {
            valor = 1;
            input.value = 1;
        }

        let producto = carrito[idx];
        if (!producto) return;

        // Limitar al stock conocido
        if (producto.stock && valor > producto.stock) {
            valor = producto.stock;
        }

        if (valor === producto.cantidad) return;

        // Validar contra el stock real del servidor
        const stockInfo = await validarStockProducto(producto.id, valor);
        if (!stockInfo.valido) {
            Swal.fire({
                icon: 'warning',
                title: 'Stock insuficiente',
                text: `Solo hay ${stockInfo.stockDisponible} unidades disponibles de "${producto.nombre}"`,
                confirmButtonColor: '#3085d6'
            });
            input.value = producto.cantidad;
            return;
        }

        carrito[idx].stock = stockInfo.stockDisponible;
        carrito[idx].cantidad = valor;
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));

        // Si hay cupón aplicado, eliminarlo al cambiar cantidades
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
            document.getElementById('descuentoRow').style.display = 'none';
            document.getElementById('mensajeCupon').innerHTML = '';
        }

        renderizarCarrito();
    }

    // ===============================
    // ELIMINAR PRODUCTO
    // ===============================
    function eliminarProducto(idx) {
        carrito.splice(idx, 1);
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
        }
        
        renderizarCarrito();
    }

    // ===============================
    // RENDERIZAR CARRITO
    // ===============================
    function renderizarCarrito() {
        let vacio = document.getElementById('carritoVacio');
        let lleno = document.getElementById('carritoLleno');
        let body = document.getElementById('carritoBody');
        let badge = document.getElementById('cartCountBadge');

        if (carrito.length === 0) {
            if (vacio) vacio.style.display = 'block';
            if (lleno) lleno.style.display = 'none';
            if (badge) badge.textContent = '0';
            return;
        }

        if (vacio) vacio.style.display = 'none';
        if (lleno) lleno.style.display = 'block';
        if (body) body.innerHTML = '';

        let totalItems = 0;
        
        for (let i = 0; i < carrito.length; i++) {
            let item = carrito[i];
            let cant = item.cantidad;
            let precio = item.precio;
            totalItems += cant;
            
            // Determinar advertencia de stock
            let stockWarning = '';
            if (item.stock && cant >= item.stock) {
                stockWarning = '<small class="text-danger stock-warning"><i class="fas fa-exclamation-triangle"></i> Stock máximo alcanzado</small>';
            } else if (item.stock && cant >= item.stock - 2) {
                stockWarning = '<small class="text-warning stock-warning"><i class="fas fa-info-circle"></i> Quedan pocas unidades</small>';
            }

            body.innerHTML += `
            <div class="cart-item p-3 border-bottom">
                <div class="row align-items-center">
                    <div class="col-12 col-sm-6 mb-3 mb-sm-0">
                        <div class="d-flex align-items-center flex-column flex-sm-row text-center text-sm-start">
                            <div class="bg-light rounded me-sm-3 p-2 d-flex align-items-center justify-content-center mb-2 mb-sm-0" style="width: 70px; height: 70px;">
                                ${item.imagen_url ? `<img src="${item.imagen_url}" style="max-width:60px; max-height:60px; object-fit:contain;">` : '<i class="fas fa-book fa-2x text-primary"></i>'}
                            </div>
                            <div>
                                <h6 class="mb-1 fw-bold">${escapeHtml(item.nombre)}</h6>
                                <small>S/. ${precio.toFixed(2)}</small>
                                ${stockWarning}
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-3 mb-2 mb-sm-0">
                        <div class="d-flex justify-content-center gap-2">
                            <button class="btn btn-sm btn-outline-secondary quantity-btn" onclick="cambiarCantidad(${i}, -1)">
                                <i class="fas fa-minus"></i>
                            </button>
                            <input type="number" class="form-control form-control-sm quantity-input" 
                                   value="${cant}" min="1" step="1" style="width:70px; text-align:center;"
                                   ${item.stock ? `max="${item.stock}"` : ''}
                                   inputmode="numeric"
                                   onchange="cambiarCantidadInput(${i}, this)"
                                   onkeypress="if(event.key==='Enter') this.blur()">
                            <button class="btn btn-sm btn-outline-secondary quantity-btn" onclick="cambiarCantidad(${i}, 1)">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                    <div class="col-4 col-sm-2 text-start text-sm-end">
                        <span class="fw-bold text-primary">S/. ${(precio * cant).toFixed(2)}</span>
                    </div>
                    <div class="col-2 col-sm-1 text-end">
                        <button class="btn btn-sm btn-link text-danger" onclick="eliminarProducto(${i})">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </div>
            </div>`;
        }
        
        if (badge) badge.textContent = totalItems;
        actualizarTotales();
    }

    // ===============================
    // CARGAR CARRITO (CON VALIDACIÓN DE STOCK)
    // ===============================
    async function cargarCarrito() {
        // Cargar datos guardados
        let g = localStorage.getItem('carritoCliente');
        carrito = g ? JSON.parse(g) : [];
        
        // Cargar cupón guardado
        let cuponGuardado = localStorage.getItem('cuponAplicado');
        if (cuponGuardado) {
            cuponAplicado = JSON.parse(cuponGuardado);
            descuento = parseFloat(localStorage.getItem('descuento') || 0);
            let descuentoRow = document.getElementById('descuentoRow');
            let mensajeCupon = document.getElementById('mensajeCupon');
            if (descuentoRow) descuentoRow.style.display = 'flex';
            if (mensajeCupon) mensajeCupon.innerHTML = '<span class="text-success">✅ Cupón aplicado</span>';
        }
        
        // Cargar tipo de entrega guardado
        let tipoGuardado = localStorage.getItem('tipoEntrega');
        if (tipoGuardado) {
            tipoEntregaSeleccionado = tipoGuardado;
            seleccionarEntrega(tipoEntregaSeleccionado);
        }
        
        // Cargar dirección guardada
        let direccionGuardada = localStorage.getItem('direccionEntrega');
        let direccionInput = document.getElementById('direccion');
        if (direccionGuardada && direccionInput) {
            direccionInput.value = direccionGuardada;
        }

        // Cargar coordenadas guardadas
        let latGuardada = localStorage.getItem('latitudEntrega');
        let lngGuardada = localStorage.getItem('longitudEntrega');
        if (latGuardada && lngGuardada) {
            document.getElementById('latitud').value = latGuardada;
            document.getElementById('longitud').value = lngGuardada;
        }
        
        // VALIDAR STOCK DE CADA PRODUCTO
        let carritoActualizado = [];
        let huboCambios = false;
        
        for (let item of carrito) {
            const stockInfo = await validarStockProducto(item.id, item.cantidad);
            
            if (!stockInfo.valido) {
                huboCambios = true;
                
                if (stockInfo.stockDisponible === 0) {
                    // Producto agotado - eliminarlo
                    await Swal.fire({
                        icon: 'warning',
                        title: 'Producto agotado',
                        text: `"${item.nombre}" ya no tiene stock. Se eliminó de tu carrito.`,
                        timer: 2000,
                        showConfirmButton: false
                    });
                    continue; // No agregar al carrito actualizado
                } else {
                    // Ajustar cantidad al stock disponible
                    item.cantidad = stockInfo.stockDisponible;
                    item.stock = stockInfo.stockDisponible;
                    carritoActualizado.push(item);
                    await Swal.fire({
                        icon: 'warning',
                        title: 'Stock reducido',
                        text: `"${item.nombre}" ahora solo tiene ${stockInfo.stockDisponible} unidades. Se ajustó tu carrito.`,
                        timer: 2000,
                        showConfirmButton: false
                    });
                }
            } else {
                // Stock suficiente, mantener el item
                item.stock = stockInfo.stockDisponible;
                carritoActualizado.push(item);
            }
        }
        
        // Si hubo cambios, actualizar localStorage y carrito
        if (huboCambios) {
            carrito = carritoActualizado;
            localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        }
        
        // Renderizar el carrito
        renderizarCarrito();

        // Si hay delivery con coordenadas, restaurar el marcador
        if (tipoEntregaSeleccionado === 'delivery' && latGuardada && lngGuardada) {
            setTimeout(() => {
                inicializarMapaCarrito();
                if (mapaCarrito) {
                    const lat = parseFloat(latGuardada);
                    const lng = parseFloat(lngGuardada);
                    mapaCarrito.setView([lat, lng], 16);
                    
                    const iconoMarcador = L.icon({
                        iconUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-icon.png',
                        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-icon-2x.png',
                        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/images/marker-shadow.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    });
                    
                    marcadorCarrito = L.marker([lat, lng], { icon: iconoMarcador }).addTo(mapaCarrito);
                    marcadorCarrito.bindPopup('<b>Tu ubicación de entrega</b><br>Lat: ' + latGuardada + '<br>Lng: ' + lngGuardada).openPopup();
                    
                    const mapaAviso = document.getElementById('mapaAviso');
                    if (mapaAviso) {
                        mapaAviso.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i> Ubicación marcada correctamente';
                        mapaAviso.classList.remove('text-muted');
                        mapaAviso.classList.add('text-success', 'fw-bold');
                    }
                }
            }, 300);
        }
    }

    // ===============================
    // ESCAPE HTML
    // ===============================
    function escapeHtml(t) {
        if (!t) return '';
        return t.replace(/[&<>]/g, function (m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    // ===============================
    // INICIALIZACIÓN
    // ===============================
    document.addEventListener('DOMContentLoaded', function () {
        // Cargar carrito con validación
        cargarCarrito();
        
        // Configurar eventos
        const btnCupon = document.getElementById('btnAplicarCupon');
        const cuponInput = document.getElementById('cuponInput');
        
        if (btnCupon) btnCupon.addEventListener('click', aplicarCupon);
        if (cuponInput) {
            cuponInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') aplicarCupon();
            });
        }
    });
