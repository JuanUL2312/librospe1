
    let filterTimeout;
    
    function filtrarProductos() {
        const categoriaId = document.getElementById('filtroCategoria').value;
        const busqueda = document.getElementById('buscarProducto').value.toLowerCase().trim();
        
        const rows = document.querySelectorAll('#tablaProductos tbody tr:not(.no-data)');
        let contador = 0;
        
        rows.forEach(row => {
            const rowCategoria = row.getAttribute('data-categoria') || '';
            const rowNombre = row.getAttribute('data-nombre') || '';
            
            let mostrar = true;
            
            if (categoriaId && rowCategoria !== categoriaId) mostrar = false;
            if (busqueda && !rowNombre.includes(busqueda)) mostrar = false;
            
            if (mostrar) {
                row.style.display = '';
                contador++;
            } else {
                row.style.display = 'none';
            }
        });
        
        const contadorSpan = document.getElementById('contadorProductos');
        if (contadorSpan) {
            contadorSpan.innerHTML = contador + ' producto' + (contador !== 1 ? 's' : '') + ' encontrado' + (contador !== 1 ? 's' : '');
        }
    }
    
    function filtrarProductosDebounced() {
        clearTimeout(filterTimeout);
        filterTimeout = setTimeout(filtrarProductos, 250);
    }
    
    function limpiarFiltros() {
        document.getElementById('filtroCategoria').value = '';
        document.getElementById('buscarProducto').value = '';
        filtrarProductos();
    }
    
    document.addEventListener('DOMContentLoaded', function() {
        const filtroCategoria = document.getElementById('filtroCategoria');
        const buscarProducto = document.getElementById('buscarProducto');
        const btnLimpiar = document.getElementById('btnLimpiar');
        
        if (filtroCategoria) filtroCategoria.addEventListener('change', filtrarProductos);
        if (buscarProducto) buscarProducto.addEventListener('keyup', filtrarProductosDebounced);
        if (btnLimpiar) btnLimpiar.addEventListener('click', limpiarFiltros);
    });
    
    if ('ontouchstart' in window) {
        document.querySelectorAll('.btn-card, .btn').forEach(element => {
            element.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.95)';
            });
            element.addEventListener('touchend', function() {
                this.style.transform = '';
            });
        });
    }
