
const API_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IkkyMzExNTYxQENPTlRJTkVOVEFMLkVEVS5QRSJ9.j1hIU4cRaCSzCNHlfWWZrWIf0zfqQAur7QV1AZab6cI';

// ============================================
// FUNCIÓN PARA OBTENER HORA DE PERÚ (CORREGIDA)
// ============================================
function obtenerHoraPeru() {
    const ahora = new Date();
    
    // Opción 1: USAR LA HORA LOCAL DEL NAVEGADOR (recomendado)
    // Si el usuario está en Perú, esto ya es hora Perú
    const dia = String(ahora.getDate()).padStart(2, '0');
    const mes = String(ahora.getMonth() + 1).padStart(2, '0');
    const anio = ahora.getFullYear();
    const horas = String(ahora.getHours()).padStart(2, '0');
    const minutos = String(ahora.getMinutes()).padStart(2, '0');
    const segundos = String(ahora.getSeconds()).padStart(2, '0');
    
    return `${dia}/${mes}/${anio} ${horas}:${minutos}:${segundos}`;
}

// ============================================
// ACTUALIZAR FECHA Y HORA EN TIEMPO REAL
// ============================================
function actualizarFechaHora() {
    const fechaHoraDisplay = document.getElementById('fecha_hora_display');
    if (fechaHoraDisplay) {
        fechaHoraDisplay.value = obtenerHoraPeru();
    }
}

// ============================================
// FUNCIONES DE VALIDACIÓN DE STOCK
// ============================================
let stockDisponible = 0;
let productoNombre = '';

function validarStockEnTiempoReal() {
    const cantidadInput = document.getElementById('cantidad_input');
    const cantidad = parseInt(cantidadInput.value) || 0;
    const errorDiv = document.getElementById('cantidad_error');
    const errorText = document.getElementById('cantidad_error_text');
    const submitBtn = document.getElementById('submitBtn');
    
    if (cantidad <= 0) {
        errorDiv.style.display = 'block';
        errorText.textContent = 'La cantidad debe ser al menos 1';
        submitBtn.disabled = true;
        return false;
    }
    
    if (cantidad > stockDisponible) {
        errorDiv.style.display = 'block';
        errorText.textContent = `La cantidad (${cantidad}) excede el stock disponible (${stockDisponible} unidades de "${productoNombre}")`;
        submitBtn.disabled = true;
        return false;
    }
    
    errorDiv.style.display = 'none';
    submitBtn.disabled = false;
    return true;
}

// ============================================
// ACTUALIZAR TOTAL, STOCK Y VISTA PREVIA
// ============================================
function actualizarTotalYStock() {
    const productoSelect = document.getElementById('producto_select');
    const cantidadInput = document.getElementById('cantidad_input');
    const totalDisplay = document.getElementById('total_display');
    const stockInfo = document.getElementById('stock_info');
    const previewContainer = document.getElementById('producto-preview');
    const infoContainer = document.getElementById('producto-info');
    
    const option = productoSelect.options[productoSelect.selectedIndex];
    const precio = parseFloat(option?.dataset.precio) || 0;
    const stock = parseInt(option?.dataset.stock) || 0;
    const nombre = option?.dataset.nombre || '';
    const imagen = option?.dataset.imagen || '';
    
    stockDisponible = stock;
    productoNombre = nombre;
    
    const cantidad = parseInt(cantidadInput.value) || 1;
    const total = precio * cantidad;
    totalDisplay.value = total.toFixed(2);
    
    // ============================================
    // ACTUALIZAR VISTA PREVIA CON IMAGEN
    // ============================================
    if (option && option.value) {
        let imagenUrl = '';
        if (imagen) {
            imagenUrl = `/static/img/productos/${imagen}`;
        }
        
        let previewHtml = '';
        if (imagen) {
            previewHtml = `
                <div class="bg-light rounded-3 p-2">
                    <img src="${imagenUrl}" 
                         alt="${nombre}" 
                         class="img-fluid rounded-3" 
                         style="max-height: 180px; width: auto; object-fit: contain;"
                         onerror="this.style.display='none'; this.parentElement.innerHTML='<div class=\\'text-center p-3\\'><i class=\\'fas fa-image fa-3x text-muted mb-2\\'></i><br><small class=\\'text-muted\\'>Imagen no disponible</small></div>'">
                    <h6 class="fw-bold mt-2 mb-1">${nombre}</h6>
                    <p class="mb-0 small">Precio: S/. ${precio.toFixed(2)}</p>
                    <p class="mb-0 small text-muted">Stock: ${stock} unidades</p>
                </div>
            `;
        } else {
            previewHtml = `
                <div class="bg-light rounded-3 p-3 text-center">
                    <i class="fas fa-box fa-3x text-primary mb-2"></i>
                    <h6 class="fw-bold">${nombre}</h6>
                    <p class="mb-0">Precio: S/. ${precio.toFixed(2)}</p>
                    <p class="mb-0 small text-muted">Stock: ${stock} unidades</p>
                    <small class="text-muted"><i class="fas fa-info-circle me-1"></i>Sin imagen disponible</small>
                </div>
            `;
        }
        previewContainer.innerHTML = previewHtml;
        infoContainer.innerHTML = `<i class="fas fa-check-circle text-success me-1"></i> Producto seleccionado: ${nombre}`;
    } else {
        previewContainer.innerHTML = `
            <div class="bg-light rounded-3 p-3 text-center">
                <i class="fas fa-box fa-3x text-muted mb-2"></i>
                <small class="text-muted d-block">Selecciona un producto</small>
            </div>
        `;
        infoContainer.innerHTML = `<i class="fas fa-info-circle me-2"></i>Información del producto aparecerá aquí`;
    }
    
    // Mostrar información de stock
    let stockHtml = '';
    if (stock <= 0) {
        stockHtml = '<div class="alert alert-danger mb-0">❌ Producto sin stock disponible</div>';
        document.getElementById('submitBtn').disabled = true;
    } else if (stock <= 5) {
        stockHtml = `<div class="alert alert-warning mb-0">⚠️ Stock bajo: solo ${stock} unidades disponibles</div>`;
        document.getElementById('submitBtn').disabled = false;
    } else {
        stockHtml = `<div class="alert alert-success mb-0">✅ Stock disponible: ${stock} unidades</div>`;
        document.getElementById('submitBtn').disabled = false;
    }
    stockInfo.innerHTML = stockHtml;
    
    // Validar cantidad en tiempo real
    validarStockEnTiempoReal();
}

// ============================================
// ACTUALIZAR CAMPOS OCULTOS
// ============================================
function actualizarCamposOcultos() {
    var tipo = document.querySelector('input[name="tipo_comprobante"]:checked').value;
    var emailOculto = document.getElementById('cliente_email_hidden');
    var documentoOculto = document.getElementById('cliente_documento_hidden');
    
    if (tipo === 'factura') {
        var emailFactura = document.getElementById('factura_email');
        var rucFactura = document.getElementById('factura_ruc');
        emailOculto.value = emailFactura ? emailFactura.value : '';
        documentoOculto.value = rucFactura ? rucFactura.value : '';
    } else {
        var emailBoleta = document.getElementById('cliente_email_boleta');
        var documentoBoleta = document.getElementById('cliente_documento_boleta');
        emailOculto.value = emailBoleta ? emailBoleta.value : '';
        documentoOculto.value = documentoBoleta ? documentoBoleta.value : '';
    }
}

function actualizarEnvioEmail() {
    var checkbox = document.getElementById('checkbox_email');
    var hidden = document.getElementById('enviar_email');
    hidden.value = checkbox.checked ? '1' : '0';
}

// ============================================
// CONSULTA DE DNI
// ============================================
async function consultarDNI() {
    const dni = document.getElementById('numero_documento').value.trim();
    const resultadoDiv = document.getElementById('resultadoCliente');
    
    if (!dni || dni.length !== 8) {
        resultadoDiv.innerHTML = '<div class="alert alert-warning">⚠️ Ingrese un DNI válido de 8 dígitos</div>';
        return;
    }
    
    resultadoDiv.innerHTML = '<div class="alert alert-info">🔄 Consultando DNI...</div>';
    
    try {
        const url = `https://dniruc.apisperu.com/api/v1/dni/${dni}?token=${encodeURIComponent(API_TOKEN)}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        document.getElementById('cliente_nombres').value = data.nombres || '';
        document.getElementById('cliente_apellidos').value = (data.apellidoPaterno || '') + ' ' + (data.apellidoMaterno || '');
        document.getElementById('cliente_documento_boleta').value = dni;
        
        resultadoDiv.innerHTML = '<div class="alert alert-success">✅ Datos encontrados correctamente</div>';
        actualizarCamposOcultos();
        
    } catch (error) {
        console.error('Error:', error);
        resultadoDiv.innerHTML = '<div class="alert alert-danger">❌ Error al consultar DNI. Verifique el número o intente más tarde.</div>';
    }
}

// ============================================
// CONSULTA DE RUC
// ============================================
async function consultarRUC() {
    const ruc = document.getElementById('factura_ruc').value.trim();
    const resultadoDiv = document.getElementById('resultadoRuc');
    
    if (!ruc || ruc.length !== 11) {
        resultadoDiv.innerHTML = '<div class="alert alert-warning">⚠️ Ingrese un RUC válido de 11 dígitos</div>';
        return;
    }
    
    resultadoDiv.innerHTML = '<div class="alert alert-info">🔄 Consultando RUC...</div>';
    
    try {
        const url = `https://dniruc.apisperu.com/api/v1/ruc/${ruc}?token=${encodeURIComponent(API_TOKEN)}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        document.getElementById('factura_razon_social').value = data.razonSocial || '';
        document.getElementById('factura_direccion').value = data.direccion || '';
        document.getElementById('factura_ruc_display').value = ruc;
        
        resultadoDiv.innerHTML = '<div class="alert alert-success">✅ RUC encontrado correctamente</div>';
        actualizarCamposOcultos();
        
    } catch (error) {
        console.error('Error:', error);
        resultadoDiv.innerHTML = '<div class="alert alert-danger">❌ Error al consultar RUC. Verifique el número o intente más tarde.</div>';
    }
}

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    const boletaRadio = document.getElementById('boleta');
    const facturaRadio = document.getElementById('factura');
    const datosBoleta = document.getElementById('datos_boleta');
    const datosFactura = document.getElementById('datos_factura');
    
    function toggleComprobanteSections() {
        if (facturaRadio.checked) {
            datosBoleta.style.display = 'none';
            datosFactura.style.display = 'block';
        } else {
            datosBoleta.style.display = 'block';
            datosFactura.style.display = 'none';
        }
        actualizarCamposOcultos();
    }
    
    boletaRadio.addEventListener('change', toggleComprobanteSections);
    facturaRadio.addEventListener('change', toggleComprobanteSections);
    toggleComprobanteSections();
    
    // Escuchar cambios en emails y documentos
    document.getElementById('factura_email')?.addEventListener('input', actualizarCamposOcultos);
    document.getElementById('cliente_email_boleta')?.addEventListener('input', actualizarCamposOcultos);
    document.getElementById('factura_ruc')?.addEventListener('input', actualizarCamposOcultos);
    document.getElementById('cliente_documento_boleta')?.addEventListener('input', actualizarCamposOcultos);
    
    document.getElementById('checkbox_email')?.addEventListener('change', actualizarEnvioEmail);
    actualizarEnvioEmail();
    
    // Botón consultar DNI
    const btnConsultarDni = document.getElementById('btnConsultarDni');
    if (btnConsultarDni) {
        btnConsultarDni.addEventListener('click', consultarDNI);
    }
    
    // Botón consultar RUC
    const btnConsultarRuc = document.getElementById('btnConsultarRuc');
    if (btnConsultarRuc) {
        btnConsultarRuc.addEventListener('click', consultarRUC);
    }
    
    // Permitir consultar con Enter en los inputs
    const dniInput = document.getElementById('numero_documento');
    if (dniInput) {
        dniInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                consultarDNI();
            }
        });
    }
    
    const rucInput = document.getElementById('factura_ruc');
    if (rucInput) {
        rucInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                consultarRUC();
            }
        });
    }
    
    // ============================================
    // EVENTOS DE VALIDACIÓN DE STOCK EN TIEMPO REAL
    // ============================================
    const productoSelect = document.getElementById('producto_select');
    const cantidadInput = document.getElementById('cantidad_input');
    
    // Cuando cambia el producto
    productoSelect.addEventListener('change', function() {
        actualizarTotalYStock();
    });
    
    // Cuando cambia la cantidad (en tiempo real)
    cantidadInput.addEventListener('input', function() {
        if (parseInt(this.value) < 0) {
            this.value = 1;
        }
        actualizarTotalYStock();
    });
    
    cantidadInput.addEventListener('blur', function() {
        if (parseInt(this.value) < 1 || this.value === '') {
            this.value = 1;
            actualizarTotalYStock();
        }
    });
    
    // ============================================
    // ACTUALIZAR FECHA Y HORA CADA SEGUNDO
    // ============================================
    // Actualizar inmediatamente
    actualizarFechaHora();
    
    // Actualizar cada segundo
    setInterval(actualizarFechaHora, 1000);
    
    // Inicializar
    actualizarTotalYStock();
    
    // ============================================
    // VALIDACIÓN ANTES DE ENVIAR
    // ============================================
    document.getElementById('ventaForm').addEventListener('submit', function(e) {
        actualizarCamposOcultos();
        
        if (!productoSelect.value) {
            e.preventDefault();
            alert('❌ Seleccione un producto');
            return false;
        }
        
        const cantidad = parseInt(cantidadInput.value);
        const option = productoSelect.options[productoSelect.selectedIndex];
        const stock = parseInt(option?.dataset.stock) || 0;
        
        if (cantidad > stock) {
            e.preventDefault();
            alert(`❌ La cantidad (${cantidad}) excede el stock disponible (${stock})`);
            cantidadInput.focus();
            return false;
        }
        
        if (cantidad < 1) {
            e.preventDefault();
            alert('❌ La cantidad debe ser al menos 1');
            cantidadInput.focus();
            return false;
        }
        
        if (document.getElementById('checkbox_email').checked) {
            var email = document.getElementById('cliente_email_hidden').value;
            if (!email) {
                e.preventDefault();
                alert('⚠️ Ingrese un correo electrónico para enviar el comprobante');
                return false;
            }
        }
        
        var tipo = document.querySelector('input[name="tipo_comprobante"]:checked').value;
        if (tipo === 'factura') {
            var razonSocial = document.getElementById('factura_razon_social').value;
            if (!razonSocial) {
                e.preventDefault();
                alert('⚠️ Complete los datos del cliente (Razón Social)');
                return false;
            }
        } else {
            var nombres = document.getElementById('cliente_nombres').value;
            var apellidos = document.getElementById('cliente_apellidos').value;
            if (!nombres || !apellidos) {
                e.preventDefault();
                alert('⚠️ Complete los datos del cliente (Nombres y Apellidos)');
                return false;
            }
        }
        
        return true;
    });
});
