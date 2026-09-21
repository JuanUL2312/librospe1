// ============================================================
// Reporte de Ventas por Vendedor - filtros AJAX (sin recargar)
// ============================================================
(function () {
    const form = document.getElementById('filtroVentasForm');
    if (!form) return;

    const resultados = document.getElementById('ventasResultados');
    const conteo = document.getElementById('ventasConteo');
    const btnPdf = document.getElementById('btnExportPdf');
    const btnExcel = document.getElementById('btnExportExcel');

    // Mantiene los enlaces PDF/Excel alineados con el filtro actual
    function actualizarExport() {
        const params = new URLSearchParams(new FormData(form));
        params.delete('vendedor_id');
        if (form.elements.vendedor_id && form.elements.vendedor_id.value) {
            params.set('vendedor_id', form.elements.vendedor_id.value);
        }
        const q = params.toString();
        if (btnPdf) btnPdf.href = '/reportes/ventas/pdf?' + q;
        if (btnExcel) btnExcel.href = '/reportes/ventas/excel?' + q;
    }

    // Actualiza la URL sin recargar (para mantener los filtros al refrescar)
    function actualizarURL() {
        const params = new URLSearchParams(new FormData(form));
        const q = params.toString();
        const nuevaURL = window.location.pathname + (q ? '?' + q : '');
        if (window.history && window.history.replaceState) {
            window.history.replaceState(null, '', nuevaURL);
        }
    }

    function aplicarFiltro() {
        const btn = form.querySelector('button[type="submit"]');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Cargando...';
        }

        if (resultados) {
            resultados.innerHTML =
                '<div class="text-center py-8"><div class="spinner-border text-primary" style="width:3rem;height:3rem;"></div>' +
                '<p class="mt-3 text-muted fw-bold">Cargando reporte...</p></div>';
        }

        fetch('/ventas/fragmento', {
            method: 'POST',
            credentials: 'same-origin',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (resultados) resultados.innerHTML = data.html;
                if (conteo) conteo.textContent = data.conteo;
                actualizarExport();
                actualizarURL();
            })
            .catch(function () {
                if (resultados) {
                    resultados.innerHTML =
                        '<div class="alert alert-danger text-center py-5 fw-bold">❌ Error al cargar el reporte. Inténtalo de nuevo.</div>';
                }
            })
            .finally(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-filter me-1"></i>Filtrar';
                }
            });
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        aplicarFiltro();
    });
})();