
// ===============================
// VARIABLES GLOBALES
// ===============================
var productosOriginal = [];
var productosFiltrados = [];

// ===============================
// CARGAR PRODUCTOS
// ===============================
function cargarProductos() {
    fetch('/api/productos/catalogo')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            productosOriginal = data;
            productosFiltrados = data;
            mostrarProductos(productosFiltrados);
        })
        .catch(function(error) {
            document.getElementById('productosGrid').innerHTML = '<div class="col-12 text-center"><div class="alert alert-danger">❌ Error al cargar productos</div></div>';
        });
}

// ===============================
// MOSTRAR PRODUCTOS
// ===============================
function mostrarProductos(productos) {
    var grid = document.getElementById('productosGrid');
    var contador = document.getElementById('contadorProductos');
    
    if (!productos || productos.length === 0) {
        grid.innerHTML = '<div class="col-12 text-center py-5"><i class="fas fa-box-open fa-5x text-muted mb-4 opacity-50"></i><h5 class="text-muted">No hay productos que coincidan</h5><p class="text-muted small">Prueba con otros filtros</p></div>';
        contador.innerHTML = '<i class="fas fa-box me-1"></i> 0 productos';
        return;
    }
    
    contador.innerHTML = '<i class="fas fa-box me-1"></i> ' + productos.length + ' producto' + (productos.length !== 1 ? 's' : '');
    
    var html = '';
    for (var i = 0; i < productos.length; i++) {
        var p = productos[i];
        var precioOferta = p.precio_oferta ? parseFloat(p.precio_oferta) : null;
        var tieneOferta = precioOferta && precioOferta < p.precio;
        var precioMostrar = tieneOferta ? precioOferta : p.precio;
        
        var stockBadge = '';
        var stockColor = '';
        if (p.cantidad === 0) {
            stockBadge = '<span class="badge bg-danger rounded-pill">❌ Agotado</span>';
            stockColor = 'opacity-50';
        } else if (p.cantidad <= 5) {
            stockBadge = '<span class="badge bg-warning text-dark rounded-pill">⚠️ ¡Últimas unidades!</span>';
        } else {
            stockBadge = '<span class="badge bg-success rounded-pill">✅ En stock</span>';
        }
        
        html += `
            <div class="col-12 col-sm-6 col-md-6 col-lg-4 ${stockColor}">
                <div class="card h-100 shadow-sm producto-card border-0 rounded-4 overflow-hidden">
                    ${tieneOferta ? `<div class="position-absolute top-0 start-0 bg-danger text-white px-2 px-md-3 py-1 m-2 m-md-3 rounded-pill" style="z-index:2; font-size:0.65rem;">-${Math.round((1 - precioOferta/p.precio)*100)}%</div>` : ''}
                    <div class="position-relative overflow-hidden" style="height: 180px; background: #f8f9fa;">
                        <img src="${p.imagen_url || '/static/img/default-product.png'}" 
                                class="img-fluid w-100 h-100" style="object-fit: cover; transition: transform 0.3s;"
                                onerror="this.style.display='none'; this.parentElement.innerHTML='<div class=\\'d-flex align-items-center justify-content-center h-100 text-muted\\' style=\\'font-size:3rem;\\'>📚</div>'"
                                onmouseover="this.style.transform='scale(1.05)'"
                                onmouseout="this.style.transform='scale(1)'">
                    </div>
                    <div class="card-body p-2 p-md-3">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h6 class="card-title fw-bold mb-0 text-dark" style="font-size: 0.85rem;">${escapeHtml(p.nombre.substring(0, 35))}</h6>
                            ${p.destacado ? '<i class="fas fa-star text-warning" title="Producto destacado"></i>' : ''}
                        </div>
                        <p class="card-text small text-muted mb-2" style="min-height: 35px;">${p.descripcion ? escapeHtml(p.descripcion.substring(0, 55)) + (p.descripcion.length > 55 ? '...' : '') : 'Sin descripción'}</p>
                        <div class="mb-2">
                            ${tieneOferta ? 
                                `<div class="d-flex align-items-baseline gap-2 flex-wrap">
                                    <span class="text-decoration-line-through text-muted small">S/. ${p.precio.toFixed(2)}</span>
                                    <span class="h6 text-danger fw-bold mb-0">S/. ${precioOferta.toFixed(2)}</span>
                                </div>` : 
                                `<span class="h6 text-primary fw-bold mb-0">S/. ${p.precio.toFixed(2)}</span>`
                            }
                        </div>
                        <div class="small text-muted mb-3 d-flex justify-content-between align-items-center flex-wrap gap-1">
                            <span><i class="fas fa-box me-1"></i> ${p.cantidad} uds</span>
                            ${stockBadge}
                        </div>
                        ${p.cantidad > 0 ? 
                            `<button class="btn btn-success w-100 rounded-pill py-1 py-md-2" style="font-size:0.75rem;" onclick="agregarAlCarrito(${p.id}, '${escapeHtml(p.nombre)}', ${precioMostrar}, ${p.cantidad})">
                                <i class="fas fa-cart-plus me-2"></i>Agregar
                            </button>` :
                            `<button class="btn btn-secondary w-100 rounded-pill py-1 py-md-2" style="font-size:0.75rem;" disabled>
                                <i class="fas fa-times-circle me-2"></i>Agotado
                            </button>`
                        }
                    </div>
                </div>
            </div>
        `;
    }
    grid.innerHTML = html;
}

function escapeHtml(texto) {
    if (!texto) return '';
    return texto.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// ===============================
// VERIFICAR STOCK
// ===============================
async function verificarStock(productoId, cantidadDeseada) {
    try {
        const response = await fetch(`/api/productos/${productoId}/stock`);
        const data = await response.json();
        if (!response.ok) return { disponible: true, stock: 999 };
        return { disponible: cantidadDeseada <= data.stock, stock: data.stock, nombre: data.nombre };
    } catch (error) {
        console.error("Error verificando stock:", error);
        return { disponible: true, stock: 999 };
    }
}

// ===============================
// AGREGAR AL CARRITO
// ===============================
async function agregarAlCarrito(id, nombre, precio, stockDisponible) {
    const stockInfo = await verificarStock(id, 1);
    
    if (!stockInfo.disponible) {
        Swal.fire({
            icon: 'error',
            title: 'Stock insuficiente',
            text: stockInfo.stock === 0 ? `"${nombre}" ya no tiene stock disponible.` : `Solo hay ${stockInfo.stock} unidades disponibles.`,
            confirmButtonColor: '#d33'
        });
        return;
    }
    
    var productoCompleto = productosOriginal.find(p => p.id === id);
    var imagenUrl = productoCompleto ? productoCompleto.imagen_url : null;
    
    var carrito = JSON.parse(localStorage.getItem('carritoCliente') || '[]');
    var existente = carrito.find(p => p.id === id);
    var nuevaCantidad = existente ? existente.cantidad + 1 : 1;
    
    if (nuevaCantidad > stockInfo.stock) {
        Swal.fire({
            icon: 'warning',
            title: 'Stock insuficiente',
            text: `Ya tienes ${existente.cantidad} en tu carrito. Solo puedes agregar ${stockInfo.stock - existente.cantidad} más.`,
            confirmButtonColor: '#ffc107'
        });
        return;
    }
    
    if (existente) {
        existente.cantidad = nuevaCantidad;
        existente.stock = stockInfo.stock;
        if (imagenUrl && !existente.imagen_url) existente.imagen_url = imagenUrl;
    } else {
        carrito.push({ 
            id: id, 
            nombre: nombre, 
            precio: precio, 
            cantidad: 1, 
            stock: stockInfo.stock, 
            imagen_url: imagenUrl
        });
    }
    
    localStorage.setItem('carritoCliente', JSON.stringify(carrito));
    actualizarContadorCarrito();
    
    var toast = document.createElement('div');
    toast.className = 'position-fixed bottom-0 end-0 bg-success text-white p-2 p-md-3 m-2 m-md-3 rounded-4 shadow-lg';
    toast.innerHTML = '<i class="fas fa-check-circle me-2"></i>' + nombre + ' agregado al carrito';
    toast.style.zIndex = '9999';
    toast.style.fontSize = '0.8rem';
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2000);
}

function actualizarContadorCarrito() {
    var carrito = JSON.parse(localStorage.getItem('carritoCliente') || '[]');
    var total = 0;
    for (var i = 0; i < carrito.length; i++) {
        total = total + carrito[i].cantidad;
    }
    var contador = document.getElementById('carritoContador');
    if (contador) {
        contador.textContent = total;
        contador.style.display = total > 0 ? 'flex' : 'none';
    }
}

// ===============================
// FILTRAR POR CATEGORÍA DESDE EL MENÚ
// ===============================
function filtrarPorCategoria(categoriaId) {
    // Actualizar el select de categorías
    var select = document.getElementById('filtroCategoria');
    if (select) {
        select.value = categoriaId || '';
        // Disparar evento change para que se apliquen los filtros
        var event = new Event('change');
        select.dispatchEvent(event);
    }
    
    // También aplicar filtros directamente
    if (typeof aplicarFiltros === 'function') {
        aplicarFiltros();
    }
    
    // Cerrar el dropdown
    var dropdown = document.querySelector('.dropdown-categorias .dropdown-menu');
    if (dropdown) {
        var parent = dropdown.closest('.dropdown');
        if (parent) {
            var toggle = parent.querySelector('.dropdown-toggle');
            if (toggle) {
                toggle.click();
            }
        }
    }
    
    // Scroll al inicio de los productos
    var grid = document.getElementById('productosGrid');
    if (grid) {
        grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// ===============================
// APLICAR FILTROS
// ===============================
function aplicarFiltros() {
    var buscar = document.getElementById('filtroBuscar').value.toLowerCase();
    var categoriaId = document.getElementById('filtroCategoria').value;
    var precioMin = parseFloat(document.getElementById('precioMin').value) || 0;
    var precioMax = parseFloat(document.getElementById('precioMax').value) || 999999;
    var stock = document.querySelector('input[name="filtroStock"]:checked').value;
    var orden = document.getElementById('filtroOrden').value;
    
    // Actualizar la URL sin recargar la página
    if (categoriaId) {
        var newUrl = window.location.pathname + '?categoria=' + categoriaId;
        window.history.pushState({ categoria: categoriaId }, '', newUrl);
        // Mostrar categoría seleccionada
        var label = document.getElementById('categoriaSeleccionadaLabel');
        if (label) {
            var select = document.getElementById('filtroCategoria');
            var text = select.options[select.selectedIndex]?.text || '';
            label.textContent = '📌 ' + text.replace('📂', '').trim();
            label.style.display = 'inline';
        }
    } else {
        window.history.pushState({ categoria: null }, '', window.location.pathname);
        var label = document.getElementById('categoriaSeleccionadaLabel');
        if (label) label.style.display = 'none';
    }
    
    productosFiltrados = productosOriginal.filter(function(p) {
        var precioActual = p.precio_oferta || p.precio;
        
        if (buscar && p.nombre.toLowerCase().indexOf(buscar) === -1) return false;
        if (categoriaId && p.categoria_id != categoriaId) return false;
        if (precioActual < precioMin || precioActual > precioMax) return false;
        if (stock === 'stock' && p.cantidad === 0) return false;
        if (stock === 'bajo' && p.cantidad > 5) return false;
        
        return true;
    });
    
    productosFiltrados.sort(function(a, b) {
        var aPrecio = a.precio_oferta || a.precio;
        var bPrecio = b.precio_oferta || b.precio;
        
        if (orden === 'nombre_asc') return a.nombre.localeCompare(b.nombre);
        if (orden === 'nombre_desc') return b.nombre.localeCompare(a.nombre);
        if (orden === 'precio_asc') return aPrecio - bPrecio;
        if (orden === 'precio_desc') return bPrecio - aPrecio;
        if (orden === 'stock_desc') return b.cantidad - a.cantidad;
        if (orden === 'destacado_desc') return (b.destacado || 0) - (a.destacado || 0);
        return 0;
    });
    
    mostrarProductos(productosFiltrados);
}

function limpiarFiltros() {
    document.getElementById('filtroBuscar').value = '';
    document.getElementById('filtroCategoria').value = '';
    document.getElementById('precioMin').value = 0;
    document.getElementById('precioMax').value = 100;
    document.getElementById('stockTodos').checked = true;
    document.getElementById('filtroOrden').value = 'nombre_asc';
    document.getElementById('categoriaSeleccionadaLabel').style.display = 'none';
    window.history.pushState({ categoria: null }, '', window.location.pathname);
    aplicarFiltros();
}

// ===============================
// EVENT LISTENERS
// ===============================
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('btnAplicarFiltros').addEventListener('click', aplicarFiltros);
    document.getElementById('btnLimpiarFiltros').addEventListener('click', limpiarFiltros);
    
    cargarProductos();
    actualizarContadorCarrito();
});

window.addEventListener('storage', function(e) {
    if (e.key === 'carritoCliente') actualizarContadorCarrito();
});

// Estilos adicionales
var style = document.createElement('style');
style.textContent = `
    .bg-gradient-primary { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
    .bg-gradient-warning { background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%); }
    .bg-gold { background: #D4AF37; color: #1E3A8A; }
    .producto-card { transition: all 0.3s ease; }
    .producto-card:hover { transform: translateY(-5px); box-shadow: 0 20px 30px -12px rgba(0,0,0,0.2) !important; }
    .rounded-4 { border-radius: 1rem !important; }
    
    @media (max-width: 576px) {
        .producto-card .card-body { padding: 0.75rem !important; }
        .producto-card .card-title { font-size: 0.8rem !important; }
        .btn-success { font-size: 0.7rem !important; padding: 0.35rem 0.5rem !important; }
        .badge { font-size: 0.6rem !important; }
        .small.text-muted { font-size: 0.65rem !important; }
    }
`;
document.head.appendChild(style);
