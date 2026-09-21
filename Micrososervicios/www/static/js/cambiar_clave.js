
  // Función para mostrar/ocultar contraseña
  function togglePassword(id) {
    const input = document.getElementById(id);
    const button = input.nextElementSibling;
    const icon = button.querySelector('i');

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

  // Referencias a los elementos
  const nueva = document.getElementById('nueva');
  const confirmar = document.getElementById('confirmar');
  const submitBtn = document.getElementById('submitBtn');
  const matchMsg = document.getElementById('matchMsg');
  const strengthInfo = document.getElementById('strengthInfo');

  // Verificar coincidencia de contraseñas
  function checkMatch() {
    if (confirmar.value === '') {
      matchMsg.innerHTML = '';
      submitBtn.disabled = false;
      return;
    }

    if (nueva.value === confirmar.value) {
      matchMsg.innerHTML = '<div class="text-success small mt-1"><i class="fas fa-check-circle"></i> ✓ Las contraseñas coinciden</div>';
      submitBtn.disabled = false;
    } else {
      matchMsg.innerHTML = '<div class="text-danger small mt-1"><i class="fas fa-times-circle"></i> ✗ Las contraseñas no coinciden</div>';
      submitBtn.disabled = true;
    }
  }

  // Verificar fuerza de la contraseña
  function checkStrength() {
    const pass = nueva.value;
    if (pass.length === 0) {
      strengthInfo.innerHTML = '';
      return;
    }

    let strength = 0;
    let requirements = [];
    
    // Criterios de seguridad
    if (pass.length >= 8) {
      strength += 1;
      requirements.push('✓ Mínimo 8 caracteres');
    } else {
      requirements.push('✗ Mínimo 8 caracteres');
    }
    
    if (/[A-Z]/.test(pass)) {
      strength += 1;
      requirements.push('✓ Mayúsculas');
    } else {
      requirements.push('✗ Mayúsculas');
    }
    
    if (/[a-z]/.test(pass)) {
      strength += 1;
      requirements.push('✓ Minúsculas');
    } else {
      requirements.push('✗ Minúsculas');
    }
    
    if (/[0-9]/.test(pass)) {
      strength += 1;
      requirements.push('✓ Números');
    } else {
      requirements.push('✗ Números');
    }
    
    if (/[^A-Za-z0-9]/.test(pass)) {
      strength += 1;
      requirements.push('✓ Caracteres especiales');
    } else {
      requirements.push('✗ Caracteres especiales');
    }
    
    // Calcular porcentaje (máximo 5)
    let porcentaje = (strength / 5) * 100;
    let color, texto, mensaje;
    
    if (strength <= 2) {
      color = '#dc3545';
      texto = '🔴 Contraseña Débil';
      mensaje = 'Mejora añadiendo mayúsculas, números o símbolos';
    } else if (strength <= 3) {
      color = '#ffc107';
      texto = '🟡 Contraseña Media';
      mensaje = 'Buena, pero puedes mejorarla';
    } else if (strength <= 4) {
      color = '#0dcaf0';
      texto = '🔵 Contraseña Buena';
      mensaje = 'Muy segura, sigue así';
    } else {
      color = '#198754';
      texto = '🟢 Contraseña Fuerte';
      mensaje = '¡Excelente! Muy segura';
    }
    
    // Mostrar barra de progreso y requisitos
    strengthInfo.innerHTML = `
      <div class="mb-2">
        <div class="progress" style="height: 6px; border-radius: 3px;">
          <div class="progress-bar strength-bar" role="progressbar" 
               style="width: ${porcentaje}%; background-color: ${color};"></div>
        </div>
        <div class="d-flex justify-content-between align-items-center mt-1">
          <small class="fw-semibold" style="color: ${color};">${texto}</small>
          <small class="text-muted">${strength}/5</small>
        </div>
      </div>
      <div class="small text-muted">
        <i class="fas fa-shield-alt me-1"></i> Requisitos:
        <div class="mt-1" style="font-size: 0.7rem;">
          ${requirements.map(req => `<span class="me-2">${req}</span>`).join('')}
        </div>
      </div>
    `;
  }

  // Event listeners con debounce para mejor rendimiento
  let timeoutId;
  nueva.addEventListener('input', function() {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      checkStrength();
      checkMatch();
    }, 100);
  });
  
  confirmar.addEventListener('input', function() {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      checkMatch();
    }, 100);
  });

  // Validación final al enviar
  document.getElementById('passwordForm').addEventListener('submit', function(e) {
    if (nueva.value !== confirmar.value) {
      e.preventDefault();
      // Mostrar alerta personalizada
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-3';
      alertDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle me-2"></i>
        ❌ Las contraseñas no coinciden
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      `;
      document.querySelector('.card-body').insertBefore(alertDiv, document.querySelector('form'));
      
      // Auto cerrar después de 3 segundos
      setTimeout(() => {
        if (alertDiv && alertDiv.remove) alertDiv.remove();
      }, 3000);
      
      return false;
    }
    
    if (nueva.value.length < 8) {
      e.preventDefault();
      alert('❌ La contraseña debe tener al menos 8 caracteres');
      return false;
    }
  });
  
  // Mejorar experiencia táctil
  if ('ontouchstart' in window) {
    document.querySelectorAll('.btn').forEach(btn => {
      btn.addEventListener('touchstart', function() {
        this.style.transform = 'scale(0.97)';
      });
      btn.addEventListener('touchend', function() {
        this.style.transform = '';
      });
    });
  }
