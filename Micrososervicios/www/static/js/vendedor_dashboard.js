
// Sistema de carrito en JavaScript
let carrito = [];

// Buscador en tiempo real
document.getElementById('buscadorProducto').addEventListener('keyup', function(e) {
    if(e.key === 'Enter') {
        buscarYAgregarProducto(this.value);
        this.value = '';
    }
});

function buscarYAgregarProducto(termino) {
    fetch(`/api/buscar_producto?q=${termino}`)
        .then(res => res.json())
        .then(producto => {
            if(producto && producto.id) {
                agregarAlCarrito(producto);
            } else {
                alert('❌ Producto no encontrado');
            }
        });
}

function agregarAlCarrito(producto) {
    let existente = carrito.find(p => p.id === producto.id);
    if(existente) {
        existente.cantidad++;
    } else {
        carrito.push({
            id: producto.id,
            nombre: producto.nombre,
            precio: producto.precio,
            cantidad: 1,
            stock: producto.stock
        });
    }
    actualizarCarrito();
}

function actualizarCarrito() {
    let tbody = document.getElementById('carritoBody');
    tbody.innerHTML = '';
    let total = 0;
    carrito.forEach((item, index) => {
        let subtotal = item.precio * item.cantidad;
        total += subtotal;
        tbody.innerHTML += `
            <tr>
                <td>${item.nombre}</td>
                <td><input type="number" value="${item.cantidad}" min="1" max="${item.stock}" 
                       class="form-control form-control-sm" style="width:70px" 
                       onchange="actualizarCantidad(${index}, this.value)"></td>
                <td>S/. ${item.precio.toFixed(2)}</td>
                <td>S/. ${subtotal.toFixed(2)}</td>
                <td><button class="btn btn-sm btn-danger" onclick="eliminarDelCarrito(${index})">🗑️</button></td>
            </tr>
        `;
    });
    document.getElementById('totalCarrito').innerText = `S/. ${total.toFixed(2)}`;
}

// Finalizar venta
let ventaRapidaEnCurso = false;
const CLAVE_VENTA_RAPIDA_PENDIENTE = 'venta_rapida_clave_pendiente';
const DATOS_VENTA_RAPIDA_PENDIENTE = 'venta_rapida_datos_pendientes';

document.getElementById('btnFinalizarVenta').onclick = function() {
    if (ventaRapidaEnCurso) return;
    if(carrito.length === 0) {
        alert('Agrega productos al carrito');
        return;
    }
    ventaRapidaEnCurso = true;
    const botonVenta = document.getElementById('btnFinalizarVenta');
    botonVenta.disabled = true;
    let claveIdempotencia = sessionStorage.getItem(CLAVE_VENTA_RAPIDA_PENDIENTE);
    let datosVenta;
    try {
        datosVenta = JSON.parse(sessionStorage.getItem(DATOS_VENTA_RAPIDA_PENDIENTE) || 'null');
    } catch (e) {
        datosVenta = null;
    }
    if (!claveIdempotencia) {
        claveIdempotencia = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : (Date.now() + '-' + Math.random().toString(16).slice(2));
        sessionStorage.setItem(CLAVE_VENTA_RAPIDA_PENDIENTE, claveIdempotencia);
        datosVenta = null;
    }
    if (!datosVenta) {
        datosVenta = {
            items: carrito.map(item => ({id: item.id, cantidad: item.cantidad})),
            cliente_dni: document.getElementById('dniCliente').value || null,
            cliente_tipo_documento: document.getElementById('tipoDocumentoCliente').value,
            tipo_comprobante: 'boleta',
            clave_idempotencia: claveIdempotencia
        };
        sessionStorage.setItem(DATOS_VENTA_RAPIDA_PENDIENTE, JSON.stringify(datosVenta));
    }
    
    fetch('/api/ventas/rapida', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Idempotency-Key': claveIdempotencia},
        body: JSON.stringify(datosVenta)
    })
    .then(res => res.json().then(data => ({res, data})))
    .then(({res, data}) => {
        if(data.success) {
            sessionStorage.removeItem(DATOS_VENTA_RAPIDA_PENDIENTE);
            sessionStorage.removeItem(CLAVE_VENTA_RAPIDA_PENDIENTE);
            alert(`✅ Venta registrada! Total: S/. ${data.total}`);
            carrito = [];
            actualizarCarrito();
            // Redirigir a comprobante
            window.location.href = `/comprobante/${data.venta_id}`;
        } else {
            alert('Error: ' + data.error);
            if (res.status < 500) {
                sessionStorage.removeItem(DATOS_VENTA_RAPIDA_PENDIENTE);
                sessionStorage.removeItem(CLAVE_VENTA_RAPIDA_PENDIENTE);
            }
        }
    })
    .catch(() => {
        alert('No se pudo confirmar la respuesta. Reintenta para consultar la misma venta.');
    })
    .finally(() => {
        ventaRapidaEnCurso = false;
        botonVenta.disabled = false;
    });
};

// Atajos de teclado
document.addEventListener('keydown', function(e) {
    if(e.key === 'F12') {
        e.preventDefault();
        document.getElementById('btnFinalizarVenta').click();
    }
    if(e.key === 'F2') {
        carrito = [];
        actualizarCarrito();
        document.getElementById('buscadorProducto').focus();
    }
});
