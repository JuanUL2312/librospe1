
  const API_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IkkyMzExNTYxQENPTlRJTkVOVEFMLkVEVS5QRSJ9.j1hIU4cRaCSzCNHlfWWZrWIf0zfqQAur7QV1AZab6cI';

  document.addEventListener('DOMContentLoaded', function () {
    const tipoDocumento = document.getElementById('tipo_documento');
    const numeroDocumento = document.getElementById('numero_documento');
    const btnConsultar = document.getElementById('btnConsultar');
    const resultadoCliente = document.getElementById('resultadoCliente');
    const nombreInput = document.getElementById('nombre');
    const empresaInput = document.getElementById('empresa');

    function configurarCampos() {
      numeroDocumento.value = '';
      resultadoCliente.innerHTML = '';

      if (tipoDocumento.value === 'DNI') {
        numeroDocumento.placeholder = 'Ingrese DNI (8 dígitos)';
        numeroDocumento.maxLength = 8;
      } else {
        numeroDocumento.placeholder = 'Ingrese RUC (11 dígitos)';
        numeroDocumento.maxLength = 11;
      }
    }

    numeroDocumento.addEventListener('input', function (e) {
      this.value = this.value.replace(/[^0-9]/g, '');
      const tipo = tipoDocumento.value;
      if (tipo === 'DNI' && this.value.length > 8) {
        this.value = this.value.slice(0, 8);
      } else if (tipo === 'RUC' && this.value.length > 11) {
        this.value = this.value.slice(0, 11);
      }
    });

    tipoDocumento.addEventListener('change', configurarCampos);

    async function consultarDocumento() {
      const tipo = tipoDocumento.value;
      const numero = numeroDocumento.value.trim();

      if (!numero) {
        resultadoCliente.innerHTML = '<div class="alert alert-warning">⚠️ Ingrese un número de documento</div>';
        return;
      }
      if (tipo === "DNI" && numero.length !== 8) {
        resultadoCliente.innerHTML = '<div class="alert alert-warning">⚠️ El DNI debe tener 8 dígitos</div>';
        return;
      }
      if (tipo === "RUC" && numero.length !== 11) {
        resultadoCliente.innerHTML = '<div class="alert alert-warning">⚠️ El RUC debe tener 11 dígitos</div>';
        return;
      }

      resultadoCliente.innerHTML = '<div class="alert alert-info">🔄 Consultando...</div>';

      try {
        const baseurl = tipo === "DNI" ? "https://dniruc.apisperu.com/api/v1/dni/" : "https://dniruc.apisperu.com/api/v1/ruc/";
        const urlFinal = baseurl + numero + "?token=" + encodeURIComponent(API_TOKEN);
        const response = await fetch(urlFinal);

        if (response.status === 401 || response.status === 403) throw new Error("Token inválido o expirado");
        if (response.status === 429) throw new Error("Demasiadas consultas. Espera un momento");
        if (!response.ok) throw new Error("Error en la consulta: " + response.status);

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        if (tipo === "DNI") {
          const nombreCompleto = `${data.nombres || ''} ${data.apellidoPaterno || ''} ${data.apellidoMaterno || ''}`.trim();
          if (nombreCompleto) nombreInput.value = nombreCompleto;

          resultadoCliente.innerHTML = `
            <div class="card border-success">
              <div class="card-body">
                <h6 class="card-title text-success"><i class="fas fa-check-circle"></i> ✅ Datos encontrados</h6>
                <hr>
                <div class="row small">
                  <div class="col-5"><strong>DNI:</strong></div>
                  <div class="col-7">${data.dni || ''}</div>
                </div>
                <div class="row small">
                  <div class="col-5"><strong>Nombres:</strong></div>
                  <div class="col-7">${data.nombres || ''}</div>
                </div>
                <div class="row small">
                  <div class="col-5"><strong>Apellido Paterno:</strong></div>
                  <div class="col-7">${data.apellidoPaterno || ''}</div>
                </div>
                <div class="row small">
                  <div class="col-5"><strong>Apellido Materno:</strong></div>
                  <div class="col-7">${data.apellidoMaterno || ''}</div>
                </div>
              </div>
            </div>
          `;
        } else {
          if (data.razonSocial) {
            nombreInput.value = data.razonSocial;
            empresaInput.value = data.razonSocial;
          }

          resultadoCliente.innerHTML = `
            <div class="card border-success">
              <div class="card-body">
                <h6 class="card-title text-success"><i class="fas fa-check-circle"></i> ✅ Datos encontrados</h6>
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
                  <div class="col-5"><strong>Estado:</strong></div>
                  <div class="col-7">${data.estado || ''}</div>
                </div>
                <div class="row small">
                  <div class="col-5"><strong>Condición:</strong></div>
                  <div class="col-7">${data.condicion || ''}</div>
                </div>
                <div class="row small">
                  <div class="col-5"><strong>Domicilio Fiscal:</strong></div>
                  <div class="col-7"><small>${data.domicilioFiscal || ''}</small></div>
                </div>
              </div>
            </div>
          `;
        }
      } catch (error) {
        resultadoCliente.innerHTML = `<div class="alert alert-danger">❌ Error: ${error.message}</div>`;
      }
    }

    btnConsultar.addEventListener('click', consultarDocumento);
    numeroDocumento.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') consultarDocumento();
    });

    configurarCampos();
  });
