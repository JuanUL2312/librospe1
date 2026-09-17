// ============================================
// POS RÁPIDO - VENTA TÁCTIL
// ============================================
(function () {
    'use strict';

    document.body.classList.add('pos-tactil');

    // ---------- Datos ----------
    var PRODUCTOS = [];
    try {
        PRODUCTOS = JSON.parse(document.getElementById('posProductosJson').textContent || '[]');
    } catch (e) { PRODUCTOS = []; }

    var ticket = [];
    var metodoPago = 'efectivo';
    var cobrando = false;

    // ---------- Referencias ----------
    var busqueda = document.getElementById('posBuscar');
    var grilla = document.getElementById('posProductos');
    var ticketBody = document.getElementById('posTicket');
    var ticketVacio = document.getElementById('posTicketVacio');
    var itemsCount = document.getElementById('posItemsCount');
    var subtotalEl = document.getElementById('posSubtotal');
    var montoRecibido = document.getElementById('posMontoRecibido');
    var vueltoInfo = document.getElementById('posVueltoInfo');
    var efectivoBlock = document.getElementById('posEfectivoBlock');
    var btnCobrar = document.getElementById('posCobrar');
    var btnVaciar = document.getElementById('posVaciar');
    var overlay = document.getElementById('posOverlay');

    // ---------- Útiles ----------
    function fmt(n) {
        return 'S/ ' + Number(n || 0).toFixed(2);
    }
    function escapeHtml(t) {
        if (!t) return '';
        return t.replace(/[&<>]/g, function (m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }
    function norm(s) {
        return (s || '').toLowerCase().trim();
    }
    function totalTicket() {
        return ticket.reduce(function (s, it) { return s + (it.precio * it.cantidad); }, 0);
    }
    function totalItems() {
        return ticket.reduce(function (s, it) { return s + it.cantidad; }, 0);
    }

    // ---------- Grilla de productos ----------
    function renderProductos() {
        var q = norm(busqueda.value);
        var lista = PRODUCTOS.filter(function (p) {
            if (!q) return true;
            if (norm(p.nombre).indexOf(q) !== -1) return true;
            if (p.codigo_barras && norm(p.codigo_barras) === q) return true;
            if (norm(p.codigo_barras) && norm(p.codigo_barras).indexOf(q) !== -1) return true;
            return false;
        });

        if (lista.length === 0) {
            grilla.innerHTML = '';
            return;
        }

        var html = '';
        for (var i = 0; i < lista.length; i++) {
            var p = lista[i];
            var stock = p.cantidad;
            var precioMuestra = p.precio_mostrar || p.precio;
            var tieneOferta = p.precio_oferta && p.precio_oferta < p.precio;

            var claseStock, textoStock;
            if (stock === 0) { claseStock = 'sin'; textoStock = 'Agotado'; }
            else if (stock <= 5) { claseStock = 'bajo'; textoStock = stock + ' uds'; }
            else { claseStock = 'ok'; textoStock = stock + ' uds'; }

            html += '<button type="button" class="pos-prod" data-id="' + p.id + '"' +
                    (stock === 0 ? ' disabled style="opacity:0.55; cursor:not-allowed;"' : '') + '>' +
                '<span class="pos-prod-stock ' + claseStock + '">' + textoStock + '</span>' +
                '<div class="pos-prod-img">' +
                    (p.imagen_url
                        ? '<img src="' + p.imagen_url + '" onerror="this.parentElement.innerHTML=\'📚\'">'
                        : '<i class="fas fa-book"></i>') +
                '</div>' +
                '<div class="pos-prod-nombre">' + escapeHtml(p.nombre) + '</div>' +
                (tieneOferta
                    ? '<div><span class="pos-prod-precio-oferta" style="text-decoration:line-through;margin-right:4px;">' + fmt(p.precio) + '</span><span class="pos-prod-precio">' + fmt(precioMuestra) + '</span></div>'
                    : '<div class="pos-prod-precio">' + fmt(precioMuestra) + '</div>') +
                (p.codigo_barras ? '<small class="text-muted" style="font-size:0.6rem;">' + escapeHtml(p.codigo_barras) + '</small>' : '') +
            '</button>';
        }
        grilla.innerHTML = html;
    }

    grilla.addEventListener('click', function (e) {
        var btn = e.target.closest('.pos-prod');
        if (!btn) return;
        agregar(parseInt(btn.dataset.id, 10));
    });

    // ---------- Ticket ----------
    function agregar(idProducto) {
        var p = PRODUCTOS.find(function (x) { return x.id === idProducto; });
        if (!p) return;
        var linea = ticket.find(function (x) { return x.id === p.id; });
        var enTicket = linea ? linea.cantidad : 0;

        if (enTicket + 1 > p.cantidad) {
            alertStock(p, p.cantidad);
            return;
        }
        if (linea) {
            linea.cantidad += 1;
        } else {
            ticket.push({
                id: p.id,
                nombre: p.nombre,
                precio: p.precio_mostrar || p.precio,
                cantidad: 1,
                stock: p.cantidad,
                imagen_url: p.imagen_url
            });
        }
        renderTicket();
        busqueda.value = '';
        renderProductos();
    }

    function cambiarCantidad(idProducto, delta) {
        var linea = ticket.find(function (x) { return x.id === idProducto; });
        if (!linea) return;
        var nueva = linea.cantidad + delta;
        var p = PRODUCTOS.find(function (x) { return x.id === idProducto; });
        var max = p ? p.cantidad : linea.stock;

        if (nueva < 1) {
            ticket = ticket.filter(function (x) { return x.id !== idProducto; });
        } else if (nueva > max) {
            alertStock(linea, max);
            return;
        } else {
            linea.cantidad = nueva;
        }
        renderTicket();
    }

    function eliminar(idProducto) {
        ticket = ticket.filter(function (x) { return x.id !== idProducto; });
        renderTicket();
    }

    function alertStock(item, disponible) {
        var msg = disponible === 0
            ? '"' + item.nombre + '" está agotado.'
            : 'Solo hay ' + disponible + ' unidades disponibles de "' + item.nombre + '".';
        var aviso = document.createElement('div');
        aviso.className = 'alert alert-warning py-2 position-fixed bottom-0 end-0 m-3 shadow';
        aviso.style.zIndex = '9998';
        aviso.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>' + msg;
        document.body.appendChild(aviso);
        setTimeout(function () { aviso.remove(); }, 2500);
    }

    function renderTicket() {
        if (ticket.length === 0) {
            ticketBody.innerHTML = '';
            ticketBody.appendChild(ticketVacio);
            ticketVacio.style.display = '';
        } else {
            if (ticketVacio.parentNode) ticketVacio.parentNode.removeChild(ticketVacio);
            var html = '';
            for (var i = 0; i < ticket.length; i++) {
                var it = ticket[i];
                html += '<div class="pos-linea">' +
                    '<div class="pos-linea-info">' +
                        '<div class="pos-linea-nombre">' + escapeHtml(it.nombre) + '</div>' +
                        '<div class="pos-linea-precio">' + fmt(it.precio) + ' c/u</div>' +
                    '</div>' +
                    '<div class="pos-qty">' +
                        '<button type="button" onclick="window.POS.cambiarCantidad(' + it.id + ',-1)" aria-label="Quitar"><i class="fas fa-minus"></i></button>' +
                        '<span>' + it.cantidad + '</span>' +
                        '<button type="button" onclick="window.POS.cambiarCantidad(' + it.id + ',1)" aria-label="Agregar"><i class="fas fa-plus"></i></button>' +
                    '</div>' +
                    '<div class="pos-linea-sub">' + fmt(it.precio * it.cantidad) + '</div>' +
                    '<button type="button" class="pos-linea-del" onclick="window.POS.eliminar(' + it.id + ')" title="Quitar"><i class="fas fa-times"></i></button>' +
                '</div>';
            }
            ticketBody.innerHTML = html;
        }

        itemsCount.textContent = totalItems() + ' item' + (totalItems() !== 1 ? 's' : '');
        subtotalEl.textContent = fmt(totalTicket());
        actualizarVuelto();
    }

    // ---------- Método de pago ----------
    var botonesMetodo = document.querySelectorAll('.pos-metodo');
    botonesMetodo.forEach(function (btn) {
        btn.addEventListener('click', function () {
            metodoPago = btn.dataset.metodo;
            botonesMetodo.forEach(function (b) { b.classList.toggle('active', b === btn); });
            efectivoBlock.style.display = metodoPago === 'efectivo' ? 'block' : 'none';
            if (metodoPago === 'efectivo') montoRecibido.focus();
            actualizarVuelto();
        });
    });

    function actualizarVuelto() {
        var total = totalTicket();
        var monto = parseFloat(montoRecibido.value) || 0;
        var valido = ticket.length > 0 && (metodoPago !== 'efectivo' || monto >= total);

        btnCobrar.disabled = !valido || cobrando;

        if (metodoPago === 'efectivo' && ticket.length > 0 && monto > 0) {
            var vuelto = monto - total;
            vueltoInfo.innerHTML = vuelto >= 0
                ? '<div class="alert alert-success py-2 mb-0">Vuelto: <strong>' + fmt(vuelto) + '</strong></div>'
                : '<div class="alert alert-danger py-2 mb-0">Falta: <strong>' + fmt(Math.abs(vuelto)) + '</strong></div>';
        } else {
            vueltoInfo.innerHTML = '';
        }
    }

    montoRecibido.addEventListener('input', actualizarVuelto);

    // ---------- Buscar / Código de barras ----------
    busqueda.addEventListener('input', renderProductos);

    busqueda.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            var q = norm(busqueda.value);
            if (!q) return;
            // 1) Código de barras exacto -> agregar
            var porCodigo = PRODUCTOS.filter(function (p) { return p.codigo_barras && norm(p.codigo_barras) === q; });
            if (porCodigo.length === 1) {
                agregar(porCodigo[0].id);
                return;
            }
            // 2) Un solo resultado por nombre -> agregar
            var coincidencias = PRODUCTOS.filter(function (p) {
                return norm(p.nombre).indexOf(q) !== -1;
            });
            if (coincidencias.length === 1) {
                agregar(coincidencias[0].id);
                return;
            }
            // 3) Múltiples -> esperar a que toquen
            if (coincidencias.length > 1 && grilla.querySelector('.pos-prod')) {
                var primero = grilla.querySelector('.pos-prod');
                primero.classList.add('border');
            }
        }
    });

    document.getElementById('posLimpiarBusqueda').addEventListener('click', function () {
        busqueda.value = '';
        renderProductos();
        busqueda.focus();
    });

    // ---------- Cobrar ----------
    btnCobrar.addEventListener('click', function () {
        if (cobrando) return;
        var items = ticket.map(function (it) {
            return { id: it.id, nombre: it.nombre, cantidad: it.cantidad };
        });
        var monto = metodoPago === 'efectivo' ? (parseFloat(montoRecibido.value) || 0) : null;

        cobrando = true;
        btnCobrar.disabled = true;
        btnCobrar.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';

        fetch('/api/ventas/rapida', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: items,
                metodo_pago: metodoPago,
                monto_recibido: monto
            })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                cobrando = false;
                btnCobrar.innerHTML = '<i class="fas fa-check-circle me-2"></i>COBRAR';
                if (!data.success) {
                    btnCobrar.disabled = false;
                    alertStock({ nombre: data.error || 'Error' }, 0);
                    return;
                }
                // Actualizar stock local
                var ventaTotal = data.total;
                items.forEach(function (it) {
                    var p = PRODUCTOS.find(function (x) { return x.id === it.id; });
                    if (p) p.cantidad = Math.max(0, p.cantidad - it.cantidad);
                });
                ticket = [];
                renderTicket();
                renderProductos();
                mostrarExito(data, ventaTotal);
            })
            .catch(function (err) {
                cobrando = false;
                btnCobrar.innerHTML = '<i class="fas fa-check-circle me-2"></i>COBRAR';
                btnCobrar.disabled = false;
                alertStock({ nombre: 'Error de conexión: ' + err }, 0);
            });
    });

    function mostrarExito(data, total) {
        document.getElementById('posOverlayTotal').textContent = fmt(total);
        document.getElementById('posOverlayComprobante').textContent = data.numero_comprobante || ('#BOLETA ' + (data.venta_id || ''));
        var vueltoEl = document.getElementById('posOverlayVuelto');
        if (data.vuelto !== null && data.vuelto !== undefined) {
            vueltoEl.className = 'alert alert-success mt-2 fs-5';
            vueltoEl.innerHTML = 'Vuelto: <strong>' + fmt(data.vuelto) + '</strong>';
        } else {
            vueltoEl.className = '';
            vueltoEl.innerHTML = '';
        }
        overlay.style.display = 'flex';
    }

    document.getElementById('posOverlayCerrar').addEventListener('click', function () {
        overlay.style.display = 'none';
        montoRecibido.value = '';
        vueltoInfo.innerHTML = '';
        actualizarVuelto();
        busqueda.focus();
    });

    btnVaciar.addEventListener('click', function () {
        if (ticket.length === 0) return;
        if (!window.confirm('¿Vaciar la venta actual?')) return;
        ticket = [];
        montoRecibido.value = '';
        renderTicket();
        busqueda.focus();
    });

    // ---------- Exponer para los onclick inline ----------
    window.POS = {
        cambiarCantidad: cambiarCantidad,
        eliminar: eliminar
    };

    // ---------- Init ----------
    renderProductos();
    renderTicket();
})();