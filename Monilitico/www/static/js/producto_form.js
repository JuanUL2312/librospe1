
  document.addEventListener('DOMContentLoaded', function () {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('imagenInput');
    const preview = document.querySelector('.dropzone-preview');
    const imgActual = document.getElementById('imagenActualContainer');
    const form = document.getElementById('productoForm');
    const submitBtn = document.getElementById('submitBtn');

    if (!dropZone || !fileInput) return;

    // Drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
      dropZone.addEventListener(evt, e => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    ['dragenter', 'dragover'].forEach(evt =>
      dropZone.addEventListener(evt, () => dropZone.classList.add('drag-over'))
    );

    ['dragleave', 'drop'].forEach(evt =>
      dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'))
    );

    dropZone.addEventListener('drop', e => {
      const files = e.dataTransfer.files;
      if (files.length > 0) handleFile(files[0]);
    });

    fileInput.addEventListener('change', e => {
      if (e.target.files.length > 0) handleFile(e.target.files[0]);
    });

    function handleFile(file) {
      if (!file) return;

      if (!file.type.startsWith('image/')) {
        alert('❌ Solo imágenes JPG, PNG, GIF');
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        alert('❌ Máximo 5MB');
        return;
      }

      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;

      if (imgActual) imgActual.style.display = 'none';

      const reader = new FileReader();
      reader.onload = function (e) {
        preview.innerHTML = `
          <div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:8px;padding:15px;text-align:center;">
            <img src="${e.target.result}" style="max-height:150px;max-width:100%;border-radius:8px;margin-bottom:8px;">
            <div>
              <strong style="color:#155724;display:block;">${escapeHtml(file.name)}</strong>
              <small style="color:#155724;">${(file.size / 1024 / 1024).toFixed(1)} MB ✅ Listo</small>
            </div>
            <button
              type="button"
              onclick="limpiarImagen()"
              style="background:#dc3545;color:white;border:none;border-radius:4px;padding:5px 12px;margin-top:8px;cursor:pointer;font-size:12px;">
              🗑️ Limpiar
            </button>
          </div>
        `;
      };
      reader.readAsDataURL(file);
    }

    window.limpiarImagen = function () {
      preview.innerHTML = '';
      fileInput.value = '';
      if (imgActual) imgActual.style.display = '';
    };
    
    // Escape HTML para prevenir XSS
    function escapeHtml(text) {
      if (!text) return '';
      return text.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
      });
    }
    
    // Validación del formulario
    if (form) {
      form.addEventListener('submit', function(e) {
        if (!form.checkValidity()) {
          e.preventDefault();
          e.stopPropagation();
        } else {
          // Mostrar estado de carga
          if (submitBtn) {
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Guardando...';
            
            // Restaurar después de 10 segundos por si hay error
            setTimeout(() => {
              if (submitBtn.disabled) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
              }
            }, 10000);
          }
        }
        form.classList.add('was-validated');
      });
    }
  });
  
  // Mejorar experiencia táctil en móviles
  if ('ontouchstart' in window) {
    document.querySelectorAll('.btn, .dropzone').forEach(element => {
      element.addEventListener('touchstart', function() {
        if (this.classList && this.classList.contains('btn')) {
          this.style.transform = 'scale(0.97)';
        }
      });
      element.addEventListener('touchend', function() {
        if (this.classList && this.classList.contains('btn')) {
          this.style.transform = '';
        }
      });
    });
  }
