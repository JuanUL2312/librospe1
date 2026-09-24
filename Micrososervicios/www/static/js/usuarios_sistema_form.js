function togglePassword(idInput, iconId) {
        const input = document.getElementById(idInput);
        const icon = document.getElementById(iconId || 'toggleIcon');
        // Fallback: busca el icono hermano del input
        let targetIcon = icon;
        if (!targetIcon && input) {
            const btn = input.nextElementSibling;
            if (btn) targetIcon = btn.querySelector('i');
        }
        if (!input || !targetIcon) return;
        if (input.type === "password") {
            input.type = "text";
            targetIcon.classList.remove('fa-eye');
            targetIcon.classList.add('fa-eye-slash');
        } else {
            input.type = "password";
            targetIcon.classList.remove('fa-eye-slash');
            targetIcon.classList.add('fa-eye');
        }
    }

    // Tipo de documento: DNI (8 dígitos) / Carnet de Extranjería (9 caracteres)
    function cambiarTipoDocumentoUsuario() {
        const sel = document.getElementById('tipoDocumentoUsuario');
        const input = document.getElementById('documentoUsuario');
        const hint = document.getElementById('docUsuarioHint');
        if (!sel || !input) return;
        const esCE = sel.value === 'CE';
        input.maxLength = esCE ? 9 : 8;
        input.value = '';
        if (esCE) {
            input.placeholder = 'Ej. A12345678';
            hint.innerHTML = '<i class="fas fa-info-circle me-1 text-info"></i>Carnet de Extranjería: exactamente 9 caracteres (letras y números).';
        } else {
            input.placeholder = 'Ej. 12345678';
            hint.innerHTML = '<i class="fas fa-info-circle me-1 text-info"></i>DNI: exactamente 8 dígitos numéricos.';
        }
    }

    async function consultarDocumentoUsuario() {
        const sel = document.getElementById('tipoDocumentoUsuario');
        const input = document.getElementById('documentoUsuario');
        const nombresInput = document.getElementById('nombresUsuario');
        const apellidosInput = document.getElementById('apellidosUsuario');
        const loading = document.getElementById('docUsuarioLoading');
        const errorDiv = document.getElementById('docUsuarioError');
        const nombresHint = document.getElementById('nombresHint');
        if (!sel || !input || !nombresInput || !apellidosInput) return;
        const tipo = sel.value;
        const val = input.value.trim();
        // Solo DNI via ApiPeru, CE es manual
        if (tipo === 'CE') {
            nombresInput.readOnly = false;
            apellidosInput.readOnly = false;
            nombresInput.placeholder = 'Ingrese nombres';
            apellidosInput.placeholder = 'Ingrese apellidos';
            if (nombresHint) nombresHint.textContent = 'Carnet de Extranjería: ingrese nombres manualmente.';
            if (loading) loading.style.display = 'none';
            if (errorDiv) errorDiv.style.display = 'none';
            return;
        }
        // DNI: debe tener 8 dígitos
        if (val.length !== 8 || !/^\d{8}$/.test(val)) {
            nombresInput.readOnly = true;
            apellidosInput.readOnly = true;
            nombresInput.value = '';
            apellidosInput.value = '';
            if (nombresHint) nombresHint.textContent = 'Se llenará automáticamente al ingresar DNI.';
            return;
        }
        // Consulta ApiPeru
        if (loading) loading.style.display = 'block';
        if (errorDiv) errorDiv.style.display = 'none';
        try {
            const res = await fetch('/api/admin/consultar-dni/' + val);
            const data = await res.json();
            if (loading) loading.style.display = 'none';
            if (data.success && data.nombres) {
                nombresInput.value = data.nombres;
                apellidosInput.value = data.apellidos || '';
                nombresInput.readOnly = true;
                apellidosInput.readOnly = true;
                if (nombresHint) nombresHint.textContent = 'Nombre cargado automáticamente desde RENIEC (no editable).';
                if (errorDiv) errorDiv.style.display = 'none';
            } else {
                // No encontrado en ApiPeru -> permitir edición manual
                nombresInput.readOnly = false;
                apellidosInput.readOnly = false;
                nombresInput.placeholder = 'No encontrado en RENIEC, ingrese manualmente';
                apellidosInput.placeholder = 'No encontrado en RENIEC, ingrese manualmente';
                if (nombresHint) nombresHint.textContent = 'No se encontró en RENIEC, puedes editar manualmente.';
                if (errorDiv) {
                    errorDiv.style.display = 'block';
                    errorDiv.querySelector('small').textContent = '⚠️ DNI no encontrado en RENIEC, ingrese nombres manualmente.';
                }
            }
        } catch (e) {
            if (loading) loading.style.display = 'none';
            nombresInput.readOnly = false;
            apellidosInput.readOnly = false;
            if (nombresHint) nombresHint.textContent = 'Error al consultar RENIEC, ingrese manualmente.';
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        const sel = document.getElementById('tipoDocumentoUsuario');
        if (sel) {
            sel.addEventListener('change', function() {
                cambiarTipoDocumentoUsuario();
                // Al cambiar tipo, resetea nombres y consulta si corresponde
                const nombresInput = document.getElementById('nombresUsuario');
                const apellidosInput = document.getElementById('apellidosUsuario');
                if (nombresInput) { nombresInput.value = ''; nombresInput.readOnly = sel.value === 'DNI'; }
                if (apellidosInput) { apellidosInput.value = ''; apellidosInput.readOnly = sel.value === 'DNI'; }
                consultarDocumentoUsuario();
            });
        }
        const input = document.getElementById('documentoUsuario');
        if (input) {
            input.addEventListener('input', function() {
                const esCE = sel && sel.value === 'CE';
                this.value = esCE
                    ? this.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 9)
                    : this.value.replace(/\D/g, '').slice(0, 8);
                // Auto-consulta cuando completa longitud
                if ((esCE && this.value.length === 9) || (!esCE && this.value.length === 8)) {
                    consultarDocumentoUsuario();
                } else if (!esCE && this.value.length < 8) {
                    const nombresInput = document.getElementById('nombresUsuario');
                    const apellidosInput = document.getElementById('apellidosUsuario');
                    if (nombresInput) { nombresInput.value = ''; nombresInput.readOnly = true; }
                    if (apellidosInput) { apellidosInput.value = ''; apellidosInput.readOnly = true; }
                }
            });
            // También consulta al perder foco
            input.addEventListener('blur', consultarDocumentoUsuario);
        }
        // Inicializa como readonly DNI
        const nombresInput = document.getElementById('nombresUsuario');
        const apellidosInput = document.getElementById('apellidosUsuario');
        if (nombresInput) nombresInput.readOnly = true;
        if (apellidosInput) apellidosInput.readOnly = true;

        // Validación confirmar contraseña
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                const clave = document.getElementById('claveInput');
                const confirmar = document.getElementById('confirmarClaveInput');
                if (clave && confirmar && clave.value !== confirmar.value) {
                    e.preventDefault();
                    const hint = document.getElementById('confirmarHint');
                    if (hint) {
                        hint.style.display = 'block';
                        hint.innerHTML = '<span class=\"text-danger\"><i class=\"fas fa-exclamation-circle me-1\"></i>Las contraseñas no coinciden</span>';
                    }
                    confirmar.focus();
                    // Usa SweetAlert si está disponible
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({ icon: 'error', title: 'Error', text: 'Las contraseñas no coinciden' });
                    } else {
                        alert('Las contraseñas no coinciden');
                    }
                }
            });
            // Limpia hint al escribir
            const confirmar = document.getElementById('confirmarClaveInput');
            if (confirmar) {
                confirmar.addEventListener('input', function() {
                    const hint = document.getElementById('confirmarHint');
                    if (hint) hint.style.display = 'none';
                });
            }
        }
    });