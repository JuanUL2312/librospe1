function togglePassword(idInput) {
        const input = document.getElementById(idInput);
        const icon = document.getElementById('toggleIcon');

        if (!input || !icon) return;

        if (input.type === "password") {
            input.type = "text";
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        } else {
            input.type = "password";
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
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

    document.addEventListener('DOMContentLoaded', function() {
        const sel = document.getElementById('tipoDocumentoUsuario');
        if (sel) {
            sel.addEventListener('change', cambiarTipoDocumentoUsuario);
        }
        const input = document.getElementById('documentoUsuario');
        if (input) {
            input.addEventListener('input', function() {
                const esCE = sel && sel.value === 'CE';
                this.value = esCE
                    ? this.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 9)
                    : this.value.replace(/\D/g, '').slice(0, 8);
            });
        }
    });