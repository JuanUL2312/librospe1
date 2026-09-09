
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
document.getElementById('btnFinalizarVenta').onclick = function() {
    if(carrito.length === 0) {
        alert('Agrega productos al carrito');
        return;
    }
    
    let clienteDNI = document.getElementById('dniCliente').value;
    
    fetch('/api/ventas/rapida', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            items: carrito,
            cliente_dni: clienteDNI || null,
            tipo_comprobante: 'boleta'
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            alert(`✅ Venta registrada! Total: S/. ${data.total}`);
            carrito = [];
            actualizarCarrito();
            // Redirigir a comprobante
            window.location.href = `/comprobante/${data.venta_id}`;
        } else {
            alert('Error: ' + data.error);
        }
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
