// ===============================
// AUTOCOMPLETADO DE BÚSQUEDA - CATÁLOGO
// Sugiere productos conforme escribes (junto a /api/productos/catalogo)
// ===============================
document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('filtroBuscar');
    var contenedor = document.getElementById('autocompleteResultados');
    if (!input || !contenedor) return;

    var timer = null;
    var indiceActual = -1;

    function ocultar() {
        contenedor.classList.add('d-none');
        contenedor.innerHTML = '';
        indiceActual = -1;
    }

    function seleccionarSugerencia(producto) {
        input.value = producto.nombre;
        ocultar();
        if (typeof aplicarFiltros === 'function') {
            aplicarFiltros();
            input.focus();
            input.select();
        } else {
            // No estamos en la página del catálogo: llevar la búsqueda allí.
            window.location.href = '/catalogo?q=' + encodeURIComponent(producto.nombre);
        }
    }

    input.addEventListener('input', function () {
        clearTimeout(timer);
        var q = input.value.trim();
        if (q.length < 2) {
            ocultar();
            return;
        }
        timer = setTimeout(function () {
            fetch('/api/productos/catalogo?q=' + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!Array.isArray(data) || data.length === 0) {
                        contenedor.innerHTML = '<div class="autocomplete-item disabled">Sin resultados para "' + q + '"</div>';
                        contenedor.classList.remove('d-none');
                        indiceActual = -1;
                        return;
                    }
                    var html = '';
                    for (var i = 0; i < data.slice(0, 8).length; i++) {
                        var p = data[i];
                        var oferta = p.precio_oferta && p.precio_oferta < p.precio ? p.precio_oferta : p.precio;
                        html += '<div class="autocomplete-item" data-index="' + i + '" data-id="' + p.id + '">' +
                            '<div class="autocomplete-nombre">' + escapeAc(p.nombre) + '</div>' +
                            '<div class="autocomplete-precio">S/. ' + Number(oferta).toFixed(2) + ' · ' + p.cantidad + ' uds</div>' +
                            '</div>';
                    }
                    contenedor.innerHTML = html;
                    contenedor.classList.remove('d-none');

                    var items = contenedor.querySelectorAll('.autocomplete-item');
                    items.forEach(function (el) {
                        el.addEventListener('click', function () {
                            seleccionarSugerencia(data[parseInt(el.dataset.index, 10)]);
                        });
                    });
                })
                .catch(function () { ocultar(); });
        }, 250);
    });

    input.addEventListener('keydown', function (e) {
        var items = contenedor.querySelectorAll('.autocomplete-item');
        if (contenedor.classList.contains('d-none') || items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            indiceActual = (indiceActual + 1) % items.length;
            resaltar(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            indiceActual = (indiceActual - 1 + items.length) % items.length;
            resaltar(items);
        } else if (e.key === 'Enter') {
            if (indiceActual >= 0 && items[indiceActual]) {
                e.preventDefault();
                items[indiceActual].click();
            }
        } else if (e.key === 'Escape') {
            ocultar();
        }
    });

    function resaltar(items) {
        items.forEach(function (el, i) {
            el.classList.toggle('activo', i === indiceActual);
        });
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest('.autocomplete-wrap')) ocultar();
    });

    function escapeAc(t) {
        if (!t) return '';
        return t.replace(/[&<>]/g, function (m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    // Estilos del dropdown
    var style = document.createElement('style');
    style.textContent = `
        .autocomplete-results {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            z-index: 1050;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            margin-top: 4px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2);
            max-height: 320px;
            overflow-y: auto;
        }
        .autocomplete-item {
            padding: 8px 12px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #f3f4f6;
            font-size: 0.8rem;
        }
        .autocomplete-item:last-child { border-bottom: none; }
        .autocomplete-item:hover, .autocomplete-item.activo { background: #eef2ff; }
        .autocomplete-item.disabled { color: #9ca3af; cursor: default; }
        .autocomplete-nombre { font-weight: 600; color: #111827; }
        .autocomplete-precio { color: #1e3a8a; font-weight: 600; white-space: nowrap; }
    `;
    document.head.appendChild(style);
});