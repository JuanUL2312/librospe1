
    // TOGGLE PASSWORD MEJORADO
    function togglePassword(inputId) {
        const input = document.getElementById(inputId);
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

    // VALIDACIÓN CLIENTE ANTES DE ENVIAR
    (() => {
        'use strict';
        
        const forms = document.querySelectorAll('.needs-validation');
        const submitBtn = document.getElementById('submitBtn');
        
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                const emailInput = document.getElementById('correoInput');
                const passwordInput = document.getElementById('claveInput');
                let isValid = true;
                
                // Validar email
                if (emailInput && emailInput.value.trim() === '') {
                    emailInput.classList.add('is-invalid');
                    isValid = false;
                } else if (emailInput && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailInput.value)) {
                    emailInput.classList.add('is-invalid');
                    isValid = false;
                } else if (emailInput) {
                    emailInput.classList.remove('is-invalid');
                    emailInput.classList.add('is-valid');
                }
                
                // Validar password
                if (passwordInput && passwordInput.value.trim() === '') {
                    passwordInput.classList.add('is-invalid');
                    isValid = false;
                } else if (passwordInput) {
                    passwordInput.classList.remove('is-invalid');
                    passwordInput.classList.add('is-valid');
                }
                
                if (!form.checkValidity() || !isValid) {
                    event.preventDefault();
                    event.stopPropagation();
                } else {
                    // Mostrar estado de carga
                    if (submitBtn) {
                        const originalText = submitBtn.innerHTML;
                        submitBtn.disabled = true;
                        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Ingresando...';
                        
                        // Restaurar después de 3 segundos por si hay error
                        setTimeout(() => {
                            if (submitBtn.disabled) {
                                submitBtn.disabled = false;
                                submitBtn.innerHTML = originalText;
                            }
                        }, 5000);
                    }
                }
                
                form.classList.add('was-validated');
            });
        });
        
        // Validación en tiempo real
        const emailInput = document.getElementById('correoInput');
        const passwordInput = document.getElementById('claveInput');
        
        if (emailInput) {
            emailInput.addEventListener('input', function() {
                if (this.value.trim() !== '' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.value)) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    if (this.value.trim() !== '') {
                        this.classList.add('is-invalid');
                    }
                }
            });
        }
        
        if (passwordInput) {
            passwordInput.addEventListener('input', function() {
                if (this.value.trim() !== '') {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
        }
    })();
    
    // Mejorar experiencia táctil en móviles
    if ('ontouchstart' in window) {
        document.querySelectorAll('.btn, .hover-lift').forEach(btn => {
            btn.addEventListener('touchstart', function() {
                if (this.classList && this.classList.contains('btn') && !this.disabled) {
                    this.style.transform = 'scale(0.97)';
                }
            });
            btn.addEventListener('touchend', function() {
                this.style.transform = '';
            });
        });
    }
    
    // Prevenir envío duplicado con tecla Enter
    document.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const submitBtn = document.getElementById('submitBtn');
            if (submitBtn && !submitBtn.disabled) {
                // Prevenir múltiples envíos
                setTimeout(() => {
                    if (submitBtn.disabled) {
                        // Ya está procesando
                    }
                }, 100);
            }
        }
    });
