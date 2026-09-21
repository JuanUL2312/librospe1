
    // TOGGLE PASSWORD MEJORADO
    function togglePassword(inputId) {
        const input = document.getElementById(inputId);
        const eye = document.getElementById('eye-' + inputId);

        if (!input || !eye) return;

        if (input.type === "password") {
            input.type = "text";
            eye.classList.remove('fa-eye');
            eye.classList.add('fa-eye-slash');
        } else {
            input.type = "password";
            eye.classList.remove('fa-eye-slash');
            eye.classList.add('fa-eye');
        }
    }

    // VALIDACIÓN DE COINCIDENCIA Y REQUISITOS
    const nuevaInput = document.getElementById('nueva_contrasena');
    const confirmarInput = document.getElementById('confirmar_contrasena');
    const matchMessage = document.getElementById('matchMessage');
    const submitBtn = document.getElementById('submitBtn');

    function validarRequisitos(password) {
        const reqLongitud = document.getElementById('reqLongitud');
        const reqMayuscula = document.getElementById('reqMayuscula');
        const reqNumero = document.getElementById('reqNumero');

        // Longitud mínima 6
        if (password.length >= 6) {
            reqLongitud.innerHTML = '✅ Mínimo 6 caracteres';
            reqLongitud.className = 'mb-1 text-success';
        } else {
            reqLongitud.innerHTML = '❌ Mínimo 6 caracteres';
            reqLongitud.className = 'mb-1 text-danger';
        }

        // Al menos una mayúscula
        if (/[A-Z]/.test(password)) {
            reqMayuscula.innerHTML = '✅ Al menos una mayúscula';
            reqMayuscula.className = 'mb-1 text-success';
        } else {
            reqMayuscula.innerHTML = '❌ Al menos una mayúscula';
            reqMayuscula.className = 'mb-1 text-danger';
        }

        // Al menos un número
        if (/[0-9]/.test(password)) {
            reqNumero.innerHTML = '✅ Al menos un número';
            reqNumero.className = 'mb-1 text-success';
        } else {
            reqNumero.innerHTML = '❌ Al menos un número';
            reqNumero.className = 'mb-1 text-danger';
        }
    }

    function validarCoincidencia() {
        const nueva = nuevaInput.value;
        const confirmar = confirmarInput.value;

        const reqCoincidencia = document.getElementById('reqCoincidencia');

        if (confirmar === '') {
            matchMessage.innerHTML = '';
            reqCoincidencia.innerHTML = '⏳ Las contraseñas coinciden';
            reqCoincidencia.className = 'text-muted';
            submitBtn.disabled = false;
            return;
        }

        if (nueva === confirmar) {
            matchMessage.innerHTML = '<i class="fas fa-check-circle text-success"></i> <span class="text-success">✓ Las contraseñas coinciden</span>';
            reqCoincidencia.innerHTML = '✅ Las contraseñas coinciden';
            reqCoincidencia.className = 'text-success';
            submitBtn.disabled = false;
        } else {
            matchMessage.innerHTML = '<i class="fas fa-times-circle text-danger"></i> <span class="text-danger">✗ Las contraseñas no coinciden</span>';
            reqCoincidencia.innerHTML = '❌ Las contraseñas no coinciden';
            reqCoincidencia.className = 'text-danger';
            submitBtn.disabled = true;
        }
    }

    // BARRA DE FUERZA DE CONTRASEÑA (CON DEBOUNCE PARA MEJOR PERFORMANCE)
    let debounceTimer;
    
    if (nuevaInput) {
        nuevaInput.addEventListener('input', function (e) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const password = e.target.value;
                const strengthBar = document.getElementById('strengthBar');
                const strengthText = document.getElementById('strengthText');
                const progress = document.getElementById('strengthProgress');

                if (!strengthBar || !strengthText || !progress) return;

                strengthBar.style.display = password.length > 0 ? 'block' : 'none';

                if (password.length === 0) return;

                // Validar requisitos
                validarRequisitos(password);
                validarCoincidencia();

                // CÁLCULO DE FUERZA MEJORADO
                let strength = 0;

                if (password.length >= 6) strength += 10;
                if (password.length >= 8) strength += 10;
                if (password.length >= 12) strength += 10;
                if (/[a-z]/.test(password)) strength += 10;
                if (/[A-Z]/.test(password)) strength += 15;
                if (/\d/.test(password)) strength += 15;
                if (/[^A-Za-z0-9]/.test(password)) strength += 20;

                strength = Math.min(strength, 100);
                progress.style.width = strength + '%';

                if (strength < 40) {
                    progress.className = 'progress-bar bg-danger';
                    progress.style.borderRadius = '10px';
                    strengthText.innerHTML = '🔴 Muy débil - Mejora tu contraseña';
                    strengthText.className = 'text-danger fw-semibold small';
                } else if (strength < 70) {
                    progress.className = 'progress-bar bg-warning';
                    progress.style.borderRadius = '10px';
                    strengthText.innerHTML = '🟡 Media - Puede mejorar';
                    strengthText.className = 'text-warning fw-semibold small';
                } else {
                    progress.className = 'progress-bar bg-success';
                    progress.style.borderRadius = '10px';
                    strengthText.innerHTML = '🟢 ¡Muy fuerte! ✅';
                    strengthText.className = 'text-success fw-bolder small';
                }
            }, 150);
        });
    }

    if (confirmarInput) {
        confirmarInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                validarCoincidencia();
            }, 100);
        });
    }

    // VALIDACIÓN CLIENTE ANTES DE ENVIAR
    (() => {
        'use strict';
        const forms = document.querySelectorAll('.needs-validation');
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                const nueva = document.getElementById('nueva_contrasena');
                const confirmar = document.getElementById('confirmar_contrasena');

                if (nueva && confirmar && nueva.value !== confirmar.value) {
                    event.preventDefault();
                    event.stopPropagation();
                    
                    // SweetAlert opcional si está disponible
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Contraseñas no coinciden',
                            text: 'Las contraseñas nuevas no coinciden. Por favor, verifica.',
                            confirmButtonColor: '#d33'
                        });
                    } else {
                        alert('❌ Las contraseñas nuevas no coinciden');
                    }
                    return;
                }

                if (nueva && nueva.value.length < 6) {
                    event.preventDefault();
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Contraseña muy corta',
                            text: 'La contraseña debe tener al menos 6 caracteres.',
                            confirmButtonColor: '#d33'
                        });
                    } else {
                        alert('❌ La contraseña debe tener al menos 6 caracteres');
                    }
                    return;
                }

                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            });
        });
    })();
    
    // Mejorar experiencia táctil en móviles
    if ('ontouchstart' in window) {
        document.querySelectorAll('.btn, .hover-lift').forEach(btn => {
            btn.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.97)';
            });
            btn.addEventListener('touchend', function() {
                this.style.transform = '';
            });
        });
    }
