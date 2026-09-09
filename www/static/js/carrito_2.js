
    // ===============================
    // VARIABLES GLOBALES
    // ===============================
    let carrito = [];
    let cuponAplicado = null;
    let descuento = 0;
    let tipoEntregaSeleccionado = 'recojo';
    let direccionEntrega = '';

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
        } else {
            direccionDiv.style.display = 'none';
            envioTexto.innerHTML = 'Gratis';
            if (direccionInput) direccionInput.value = '';
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
                            <span class="fw-bold" style="min-width: 30px; text-align: center;">${cant}</span>
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
