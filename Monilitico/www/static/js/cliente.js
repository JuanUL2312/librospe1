
        // ============================================
        // EFECTO DE SOMBRA AL HACER SCROLL
        // ============================================
        document.addEventListener('DOMContentLoaded', function() {
            const navbar = document.getElementById('mainNavbar');
            if (navbar) {
                window.addEventListener('scroll', function() {
                    if (window.scrollY > 50) {
                        navbar.classList.add('scrolled');
                    } else {
                        navbar.classList.remove('scrolled');
                    }
                });
            }

            // ============================================
            // ACTUALIZAR CONTADOR DEL CARRITO
            // ============================================
            function actualizarContadorCarrito() {
                let carrito = JSON.parse(localStorage.getItem('carritoCliente') || '[]');
                let total = carrito.reduce((sum, item) => sum + item.cantidad, 0);
                let contador = document.getElementById('carritoContador');
                if (contador) {
                    if (total > 0) {
                        contador.textContent = total;
                        contador.style.display = 'flex';
                    } else {
                        contador.style.display = 'none';
                    }
                }
            }
            actualizarContadorCarrito();
        });

        // ============================================
        // FILTRAR POR CATEGORÍA DESDE EL MENÚ
        // ============================================
        function filtrarPorCategoria(categoriaId) {
            // Buscar el select de categorías en la página
            var select = document.getElementById('filtroCategoria');
            if (select) {
                // Actualizar el valor del select
                select.value = categoriaId || '';
                // Disparar evento change para que se apliquen los filtros
                var event = new Event('change');
                select.dispatchEvent(event);
            }
            
            // Si existe la función aplicarFiltros en la página, ejecutarla
            if (typeof aplicarFiltros === 'function') {
                aplicarFiltros();
            }
            
            // Cerrar el dropdown automáticamente
            var dropdownMenu = document.querySelector('.dropdown-categorias .dropdown-menu');
            if (dropdownMenu) {
                var dropdown = dropdownMenu.closest('.dropdown-categorias');
                if (dropdown) {
                    var toggle = dropdown.querySelector('.dropdown-toggle');
                    if (toggle) {
                        toggle.click();
                    }
                }
            }
            
            // Scroll suave al inicio de los productos
            var grid = document.getElementById('productosGrid');
            if (grid) {
                grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    