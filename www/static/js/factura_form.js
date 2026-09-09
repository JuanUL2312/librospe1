
function inicializarFactura() {
    const numeroRuc = document.getElementById('numero_ruc_factura');
    const btnConsultar = document.getElementById('btnConsultarRucFactura');
    const resultadoRuc = document.getElementById('resultadoRucFactura');
    const facturaRazonSocial = document.getElementById('factura_razon_social');
    const facturaRuc = document.getElementById('factura_ruc');
    const facturaDireccion = document.getElementById('factura_direccion');
    const API_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IkkyMzExNTYxQENPTlRJTkVOVEFMLkVEVS5QRSJ9.j1hIU4cRaCSzCNHlfWWZrWIf0zfqQAur7QV1AZab6cI';

    if (!numeroRuc) return;

    if (numeroRuc) {
        numeroRuc.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^0-9]/g, '');
            if (this.value.length > 11) {
                this.value = this.value.slice(0, 11);
            }
        });
    }

    async function consultarRuc() {
        const numero = numeroRuc.value.trim();

        if (!numero) {
            resultadoRuc.innerHTML = '<div class="alert alert-warning">⚠️ Ingrese un número de RUC</div>';
            return;
        }
        if (numero.length !== 11) {
            resultadoRuc.innerHTML = '<div class="alert alert-warning">⚠️ El RUC debe tener 11 dígitos</div>';
            return;
        }

        resultadoRuc.innerHTML = '<div class="alert alert-info">🔄 Consultando RUC...</div>';

        try {
            const urlFinal = `https://dniruc.apisperu.com/api/v1/ruc/${numero}?token=${encodeURIComponent(API_TOKEN)}`;
            const response = await fetch(urlFinal);

            if (response.status === 401 || response.status === 403) throw new Error("Token inválido o expirado");
            if (!response.ok) throw new Error("Error en la consulta");

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            if (facturaRazonSocial) facturaRazonSocial.value = data.razonSocial || '';
            if (facturaRuc) facturaRuc.value = data.ruc || '';
            if (facturaDireccion) facturaDireccion.value = data.direccion || '';

            resultadoRuc.innerHTML = `
                <div class="card border-success">
                    <div class="card-body">
                        <h6 class="card-title text-success">✅ Datos encontrados</h6>
                        <hr>
                        <div class="row small">
                            <div class="col-5"><strong>RUC:</strong></div>
                            <div class="col-7">${data.ruc || ''}</div>
                        </div>
                        <div class="row small">
                            <div class="col-5"><strong>Razón Social:</strong></div>
                            <div class="col-7">${data.razonSocial || ''}</div>
                        </div>
                        <div class="row small">
                            <div class="col-5"><strong>Dirección:</strong></div>
                            <div class="col-7">${data.direccion || ''}</div>
                        </div>
                        <div class="row small">
                            <div class="col-5"><strong>Estado:</strong></div>
                            <div class="col-7">${data.estado || ''}</div>
                        </div>
                        <div class="row small">
                            <div class="col-5"><strong>Condición:</strong></div>
                            <div class="col-7">${data.condicion || ''}</div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            resultadoRuc.innerHTML = `<div class="alert alert-danger">❌ Error: ${error.message}</div>`;
        }
    }

    if (btnConsultar) {
        btnConsultar.addEventListener('click', consultarRuc);
    }
    if (numeroRuc) {
        numeroRuc.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') consultarRuc();
        });
    }
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarFactura);
} else {
    inicializarFactura();
}
