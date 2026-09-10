
// ============================================
// VARIABLES GLOBALES
// ============================================
var carrito = [];
var tipoComprobante = 'boleta';
var tipoDocumento = 'DNI'; // DNI | CE (Carnet de Extranjería)
var tipoEntrega = 'recojo';
var costoEnvio = 0;
var ubigeoCliente = null;
var datosDni = null; // nombre real desde RENIEC (APIPERU) al ingresar DNI

// ============================================
// SELECCIONAR TIPO DE COMPROBANTE
// ============================================
function seleccionarComprobante(tipo) {
    tipoComprobante = tipo;
    
    // Actualizar clases activas
    document.getElementById('cardBoleta').classList.toggle('active', tipo === 'boleta');
    document.getElementById('cardFactura').classList.toggle('active', tipo === 'factura');
    
    // Actualizar radios
    document.querySelectorAll('input[name="tipoComprobante"]').forEach(el => {
        el.checked = el.value === tipo;
    });
    
    // Actualizar labels y placeholders
    var input = document.getElementById('documentoInput');
    var label = document.getElementById('documentoLabel');
    var info = document.getElementById('documentoInfo');
    var error = document.getElementById('documentoError');
    var confirmBlock = document.getElementById('confirmacionBlock');
    var confirmNombre = document.getElementById('confirmNombreBlock');
    var confirmRazon = document.getElementById('confirmRazonBlock');
    var tipoDocRow = document.getElementById('tipoDocumentoRow');
    
    // Ocultar confirmación
    confirmBlock.classList.remove('show');
    confirmNombre.style.display = 'none';
    confirmRazon.style.display = 'none';
    
    if (tipo === 'boleta') {
        if (tipoDocRow) tipoDocRow.style.display = 'block';
        tipoDocumento = 'DNI';
        if (document.getElementById('tipoDocumentoSelect')) {
            document.getElementById('tipoDocumentoSelect').value = 'DNI';
        }
        label.innerHTML = 'DNI <span class="text-muted small">(opcional)</span>';
        input.placeholder = '8 dígitos numéricos';
        input.maxLength = 8;
        input.value = '';
        info.textContent = 'Opcional: ingresa tu DNI para que la boleta salga con tu nombre real (RENIEC)';
        info.style.display = 'block';
        info.style.color = '#6b7280';
        error.style.display = 'none';
        input.classList.remove('is-invalid');
        document.getElementById('documentoSection').style.display = 'block';
        datosDni = null;
    } else {
        if (tipoDocRow) tipoDocRow.style.display = 'none';
        label.innerHTML = 'RUC <span class="text-danger">*</span>';
        input.placeholder = '11 dígitos numéricos';
        input.maxLength = 11;
        input.value = '';
        info.textContent = 'Ingresa tu número de RUC (11 dígitos)';
        info.style.display = 'block';
        info.style.color = '#6b7280';
        error.style.display = 'none';
        input.classList.remove('is-invalid');
        document.getElementById('documentoSection').style.display = 'block';
        datosDni = null;
    }
}

// ============================================
// CAMBIAR TIPO DE DOCUMENTO (DNI / Carnet de Extranjería)
// ============================================
function cambiarTipoDocumento() {
    var select = document.getElementById('tipoDocumentoSelect');
    if (!select) return;
    tipoDocumento = select.value === 'CE' ? 'CE' : 'DNI';

    var input = document.getElementById('documentoInput');
    var label = document.getElementById('documentoLabel');
    var info = document.getElementById('documentoInfo');
    var error = document.getElementById('documentoError');

    input.value = '';
    datosDni = null;
    input.classList.remove('is-invalid');
    error.classList.remove('show');
    error.style.display = 'none';
    document.getElementById('confirmacionBlock').classList.remove('show');

    if (tipoDocumento === 'CE') {
        label.innerHTML = 'Carnet de Extranjería <span class="text-muted small">(opcional)</span>';
        input.placeholder = '9 caracteres (letras y números)';
        input.maxLength = 9;
        error.textContent = '❌ El Carnet de Extranjería debe tener 9 caracteres (letras y números)';
        info.textContent = 'Opcional: ingresa tu Carnet de Extranjería (CE) para la boleta.';
        info.style.display = 'block';
        info.style.color = '#6b7280';
    } else {
        label.innerHTML = 'DNI <span class="text-muted small">(opcional)</span>';
        input.placeholder = '8 dígitos numéricos';
        input.maxLength = 8;
        error.textContent = '❌ El DNI debe tener exactamente 8 dígitos numéricos';
        info.textContent = 'Opcional: ingresa tu DNI para que la boleta salga con tu nombre real (RENIEC)';
        info.style.display = 'block';
        info.style.color = '#6b7280';
    }
}

// ============================================
// VALIDAR DOCUMENTO Y MOSTRAR CONFIRMACIÓN
// ============================================
function validarDocumento(input) {
    var esCE = tipoComprobante === 'boleta' && tipoDocumento === 'CE';
    var maxLength = tipoComprobante === 'boleta' ? (esCE ? 9 : 8) : 11;
    
    // Limitar a los caracteres permitidos según el tipo
    var value = esCE
        ? input.value.replace(/[^A-Za-z0-9]/g, '')
        : input.value.replace(/\D/g, '');
    input.value = value.slice(0, maxLength);
    
    var error = document.getElementById('documentoError');
    var info = document.getElementById('documentoInfo');
    var confirmBlock = document.getElementById('confirmacionBlock');
    var confirmNombre = document.getElementById('confirmNombreBlock');
    var confirmRazon = document.getElementById('confirmRazonBlock');
    
    // Ocultar confirmación mientras escribe
    confirmBlock.classList.remove('show');
    confirmNombre.style.display = 'none';
    confirmRazon.style.display = 'none';
    
    if (value.length === 0) {
        input.classList.remove('is-invalid');
        error.classList.remove('show');
        info.style.display = 'block';
        datosDni = null;
        if (tipoComprobante === 'boleta') {
            if (esCE) {
                info.textContent = 'Opcional: ingresa tu Carnet de Extranjería (CE) para la boleta.';
            } else {
                info.textContent = 'Opcional: ingresa tu DNI para que la boleta salga con tu nombre real (RENIEC)';
            }
        } else {
            info.textContent = 'Ingresa tu número de RUC (11 dígitos)';
        }
        info.style.color = '#6b7280';
        return;
    }
    
    if (value.length === maxLength) {
        input.classList.remove('is-invalid');
        error.classList.remove('show');
        info.style.display = 'block';
        info.textContent = '✅ Documento válido';
        info.style.color = '#16a34a';
        
        // Mostrar confirmación
        mostrarConfirmacion(value);
    } else {
        input.classList.add('is-invalid');
        error.classList.add('show');
        info.style.display = 'none';
        info.style.color = '#6b7280';
    }
}

// ============================================
// MOSTRAR BLOQUE DE CONFIRMACIÓN
// ============================================
function mostrarConfirmacion(documento) {
    var confirmBlock = document.getElementById('confirmacionBlock');
    var confirmNombre = document.getElementById('confirmNombreBlock');
    var confirmRazon = document.getElementById('confirmRazonBlock');
    var confirmNombreCompleto = document.getElementById('confirmNombreCompleto');
    var confirmRazonSocial = document.getElementById('confirmRazonSocial');
    var confirmDocumento = document.getElementById('confirmDocumento');
    var badge = document.getElementById('badgeEstado');
    
    // Mostrar bloque
    confirmBlock.classList.add('show');
    
    // Actualizar documento
    confirmDocumento.textContent = documento;
    
    if (tipoComprobante === 'boleta') {
        // Mostrar nombre completo
        confirmNombre.style.display = 'block';
        confirmRazon.style.display = 'none';
        
        if (tipoDocumento === 'CE') {
            // El CE no se consulta en RENIEC: la boleta usa el nombre registrado del cliente
            var nombreReg = (document.getElementById('nombresDisplay') ? document.getElementById('nombresDisplay').textContent : '') + ' ' +
                            (document.getElementById('apellidosDisplay') ? document.getElementById('apellidosDisplay').textContent : '');
            confirmNombreCompleto.textContent = nombreReg.trim() || 'Cliente registrado';
            badge.textContent = '✅ Carnet de Extranjería registrado';
            badge.className = 'badge-verified';
            datosDni = null;
            return;
        }
        
        badge.textContent = '✅ DNI Verificado';
        badge.className = 'badge-verified';
        
        // Buscar nombre del cliente por DNI
        fetch('/api/consultar-dni/' + documento)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.nombres) {
                    var nombreCompleto = (data.nombres || '') + ' ' + (data.apellidos || '');
                    confirmNombreCompleto.textContent = nombreCompleto.trim() || 'No encontrado';
                    datosDni = { nombres: data.nombres, apellidos: data.apellidos };
                    badge.textContent = '✅ DNI Verificado';
                    badge.className = 'badge-verified';
                } else {
                    confirmNombreCompleto.textContent = '⚠️ DNI no encontrado en RENIEC. La boleta usará tu nombre registrado.';
                    badge.textContent = '⚠️ No encontrado en RENIEC';
                    badge.className = 'badge-error';
                }
            })
            .catch(() => {
                confirmNombreCompleto.textContent = '⚠️ Error al consultar RENIEC';
                badge.textContent = '⚠️ Error de consulta';
                badge.className = 'badge-error';
            });
    } else {
        // Mostrar razón social
        confirmNombre.style.display = 'none';
        confirmRazon.style.display = 'block';
        badge.textContent = '✅ RUC Verificado';
        badge.className = 'badge-verified';
        
        // Buscar razón social por RUC
        fetch('/api/consultar-ruc/' + documento)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.razon_social) {
                    confirmRazonSocial.textContent = data.razon_social;
                    badge.textContent = '✅ RUC Verificado';
                    badge.className = 'badge-verified';
                } else {
                    confirmRazonSocial.textContent = '⚠️ RUC no encontrado en el sistema';
                    badge.textContent = '⚠️ No verificado';
                    badge.className = 'badge-error';
                }
            })
            .catch(() => {
                confirmRazonSocial.textContent = '⚠️ Error al consultar RUC';
                badge.textContent = '⚠️ Error';
                badge.className = 'badge-error';
            });
    }
}

// ============================================
// CARGAR CARRITO
// ============================================
function cargarCarrito() {
    var carritoData = localStorage.getItem('carritoCliente');
    if (!carritoData) {
        document.getElementById('productosCarrito').innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-shopping-cart fa-3x text-muted mb-3"></i>
                <p class="text-muted">Tu carrito está vacío</p>
                <a href="/catalogo" class="btn btn-gold">Ir a la tienda</a>
            </div>
        `;
        document.getElementById('btnPagar').disabled = true;
        return;
    }
    
    try {
        carrito = JSON.parse(carritoData);
        if (!carrito || carrito.length === 0) {
            document.getElementById('productosCarrito').innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-shopping-cart fa-3x text-muted mb-3"></i>
                    <p class="text-muted">Tu carrito está vacío</p>
                    <a href="/catalogo" class="btn btn-gold">Ir a la tienda</a>
                </div>
            `;
            document.getElementById('btnPagar').disabled = true;
            return;
        }
        
        renderizarCarrito();
    } catch (e) {
        document.getElementById('productosCarrito').innerHTML = `
            <div class="text-center py-4 text-danger">Error al cargar el carrito</div>
        `;
    }
}

// ============================================
// RENDERIZAR CARRITO
// ============================================
function renderizarCarrito() {
    var container = document.getElementById('productosCarrito');
    var html = '';
    var subtotal = 0;
    
    carrito.forEach(function(item) {
        var totalItem = item.precio * item.cantidad;
        subtotal += totalItem;
        html += `
            <div class="producto-item">
                <div>
                    <div class="producto-nombre">${item.nombre}</div>
                    <div class="producto-cantidad">x${item.cantidad}</div>
                </div>
                <div class="producto-precio">S/. ${totalItem.toFixed(2)}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    // Actualizar totales (incluye costo de envío si es delivery)
    actualizarTotales();
    
    document.getElementById('btnPagar').disabled = false;
}

// ============================================
// SELECCIONAR TIPO DE ENTREGA
// ============================================
function seleccionarEntrega(tipo) {
    tipoEntrega = tipo;
    
    cargarUbigeoCliente();

    var dirSection = document.getElementById('direccionSection');
    if (tipo === 'delivery') {
        dirSection.style.display = 'block';
        costoEnvio = 5;
        actualizarDireccionEntrega();
    } else {
        dirSection.style.display = 'none';
        costoEnvio = 0;
    }
    actualizarTotales();
}

// ============================================
// UBIGEO DE RESIDENCIA (desde el perfil del cliente)
// ============================================
function cargarUbigeoCliente() {
    var section = document.getElementById('direccionSection');
    if (section) {
        var d = section.dataset;
        ubigeoCliente = (d.dep && d.prov && d.dist) ? {
            departamento: d.dep,
            provincia: d.prov,
            distrito: d.dist
        } : null;
    }
}

// ============================================
// VALIDAR UBIGEO PARA DELIVERY Y MOSTRAR DESTINO
// ============================================
function actualizarDireccionEntrega() {
    var faltante = document.getElementById('ubicacionFaltante');
    var destino = document.getElementById('destinoEntrega');
    var btn = document.getElementById('btnPagar');
    var completo = ubigeoCliente !== null;

    if (faltante) faltante.classList.toggle('d-none', completo);
    if (destino) {
        if (completo) {
            document.getElementById('destinoDistrito').textContent =
                ubigeoCliente.distrito + ' (' + ubigeoCliente.departamento + ' - ' + ubigeoCliente.provincia + ')';
            destino.style.display = 'block';
        } else {
            destino.style.display = 'none';
        }
    }
    if (btn) btn.disabled = !completo;
    return completo;
}

// ============================================
// ACTUALIZAR TOTALES (con envío)
// ============================================
function actualizarTotales() {
    var subtotal = carrito.reduce(function(s, i) { return s + (i.precio * i.cantidad); }, 0);
    document.getElementById('subtotal').textContent = 'S/. ' + subtotal.toFixed(2);
    document.getElementById('descuento').textContent = '-S/. 0.00';
    document.getElementById('envio').textContent = 'S/. ' + costoEnvio.toFixed(2);
    document.getElementById('total').textContent = 'S/. ' + (subtotal + costoEnvio).toFixed(2);
}

// ============================================
// PROCESAR PAGO
// ============================================
function procesarPago() {
    var btn = document.getElementById('btnPagar');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
    
    // Validar campos
    var email = document.getElementById('clienteEmail').value.trim();
    var telefono = document.getElementById('clienteTelefono').value.trim();
    var documento = document.getElementById('documentoInput').value.trim();
    var direccion = document.getElementById('direccionEntrega').value.trim();
    
    if (!email || !telefono) {
        Swal.fire({
            icon: 'warning',
            title: 'Campos incompletos',
            text: 'Por favor completa todos los campos obligatorios.',
            confirmButtonColor: '#D4AF37'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
        return;
    }
    
    // Si es delivery, la dirección es obligatoria
    if (tipoEntrega === 'delivery' && !direccion) {
        Swal.fire({
            icon: 'warning',
            title: 'Dirección requerida',
            text: 'Para entrega a domicilio, ingresa tu dirección.',
            confirmButtonColor: '#D4AF37'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
        return;
    }

    // Si es delivery, el cliente debe tener distrito de residencia
    if (tipoEntrega === 'delivery' && !actualizarDireccionEntrega()) {
        Swal.fire({
            icon: 'warning',
            title: 'Distrito de residencia requerido',
            text: 'Completa tu lugar de residencia (departamento, provincia y distrito) en Mi Perfil para poder entregarte el pedido.',
            confirmButtonColor: '#D4AF37'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
        return;
    }
    
    // Documento: obligatorio SOLO en factura (RUC). En boleta es opcional
    if (tipoComprobante === 'boleta' && documento) {
        var docValido = (tipoDocumento === 'CE')
            ? /^[A-Za-z0-9]{9}$/.test(documento)
            : /^\d{8}$/.test(documento);
        if (!docValido) {
            Swal.fire({
                icon: 'warning',
                title: tipoDocumento === 'CE' ? 'Carnet de Extranjería inválido' : 'DNI inválido',
                text: tipoDocumento === 'CE'
                    ? 'El Carnet de Extranjería debe tener exactamente 9 caracteres (letras y números).'
                    : 'El DNI debe tener exactamente 8 dígitos.',
                confirmButtonColor: '#D4AF37'
            });
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
            return;
        }
    }
    
    if (tipoComprobante === 'factura' && documento.length !== 11) {
        Swal.fire({
            icon: 'warning',
            title: 'RUC inválido',
            text: 'El RUC debe tener exactamente 11 dígitos.',
            confirmButtonColor: '#D4AF37'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
        return;
    }
    
    // La verificación del documento aplica si se ingresó uno en la boleta, o siempre en factura
    var requiereVerificacion = (tipoComprobante === 'factura') || (tipoComprobante === 'boleta' && documento.length > 0);
    var confirmBlock = document.getElementById('confirmacionBlock');
    if (requiereVerificacion && !confirmBlock.classList.contains('show')) {
        Swal.fire({
            icon: 'warning',
            title: 'Documento no verificado',
            text: 'Por favor ingresa un documento válido para continuar.',
            confirmButtonColor: '#D4AF37'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-credit-card me-2"></i>Continuar con el pago';
        return;
    }
    
    // Guardar datos del checkout en localStorage para la página de pago
    // Si se verificó el DNI con RENIEC, la boleta lleva el nombre real de esa persona
    var compNombres = (datosDni && datosDni.nombres)
        ? datosDni.nombres
        : (document.getElementById('nombresDisplay').textContent || '');

    var compApellidos = (datosDni && datosDni.apellidos)
        ? datosDni.apellidos
        : (document.getElementById('apellidosDisplay').textContent || '');

    var checkoutData = {
        nombres: compNombres,
        apellidos: compApellidos,
        email: email,
        telefono: telefono,
        documento: documento,
        tipo_documento: tipoComprobante === 'factura'
            ? 'RUC'
            : (documento ? (tipoDocumento === 'CE' ? 'Carnet de Extranjería' : 'DNI') : ''),
        direccion: direccion,
        tipo_comprobante: tipoComprobante,
        razon_social: tipoComprobante === 'factura' ? (document.getElementById('confirmRazonSocial').textContent || '') : '',
        direccion_fiscal: direccion
    };
    localStorage.setItem('checkoutData', JSON.stringify(checkoutData));
    localStorage.setItem('tipoEntrega', tipoEntrega);
    localStorage.setItem('direccionEntrega', direccion);

    // Ir a la página de pago para elegir el método de pago
    window.location.href = '/pago';
}

// ============================================
// INICIALIZAR
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Cargar tipo de entrega guardado en el carrito (localStorage)
    var tipoGuardado = localStorage.getItem('tipoEntrega');
    if (tipoGuardado) {
        seleccionarEntrega(tipoGuardado);
    }

    cargarCarrito();

    // Cargar dirección de entrega guardada en el carrito (localStorage)
    var direccionGuardada = localStorage.getItem('direccionEntrega');
    var direccionInput = document.getElementById('direccionEntrega');
    if (direccionGuardada && direccionInput) {
        direccionInput.value = direccionGuardada;
    }
    
    // Actualizar contador del carrito
    var contador = document.getElementById('carritoContador');
    if (contador) {
        var carritoData = JSON.parse(localStorage.getItem('carritoCliente') || '[]');
        var total = carritoData.reduce((sum, item) => sum + item.cantidad, 0);
        if (total > 0) {
            contador.textContent = total;
            contador.style.display = 'flex';
        } else {
            contador.style.display = 'none';
        }
    }

    // Revalidar el botón de pago (carrito pudo habilitarlo pero falta ubigeo para delivery)
    if (tipoEntrega === 'delivery') {
        actualizarDireccionEntrega();
    }
});
