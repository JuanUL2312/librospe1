/* ============================================================
   Selector de código de país para teléfonos (compartido)
   ------------------------------------------------------------
   Uso en el HTML:
     <select class="form-select" data-tel-prefijo data-tel-input="telefonoInput">
       <option value="">…</option>          <- option oculto opcional
       <option value="+51" selected>🇵🇪 +51</option>
       ...
     </select>
     <input type="tel" id="telefonoInput" name="telefono" ...>
     <form data-telefono-pais> ... </form>  <- combina al enviar

   Al cargar separa el código guardado (+51987654321 -> 987654321 + +51)
   y al enviar escribe el número completo en el input del teléfono.
   ============================================================ */
(function () {
    'use strict';

    function digitos(s) { return String(s || '').replace(/\D/g, ''); }

    function opcionesOrdenadas(sel) {
        var arr = [];
        for (var i = 0; i < sel.options.length; i++) {
            var d = digitos(sel.options[i].value);
            if (d) arr.push(d);
        }
        arr.sort(function (a, b) { return b.length - a.length; });
        return arr;
    }

    // Quita el código del país y el 0 inicial del celular peruano
    function limpiar(inp, prefijo) {
        var d = digitos(inp.value);
        var cod = digitos(prefijo);
        if (cod && d.length > cod.length + 5 && d.indexOf(cod) === 0) {
            d = d.slice(cod.length);
        }
        if (cod === '51' && d.length === 10 && d.charAt(0) === '0') {
            d = d.slice(1);
        }
        return d;
    }

    // Número completo para guardar: "+51987654321"
    window.telPaisCompleto = function (sel, inp) {
        if (inp.dataset.telCrudo === '1') return inp.value.trim(); // código fuera de la lista
        var cod = digitos(sel.value);
        return cod ? '+' + limpiar(inp, sel.value) : limpiar(inp, sel.value);
    };

    function init(sel) {
        var inp = document.getElementById(sel.getAttribute('data-tel-input'));
        if (!inp || !inp.value) return;

        var d = digitos(inp.value);
        var codigos = opcionesOrdenadas(sel);
        for (var i = 0; i < codigos.length; i++) {
            if (d.length > codigos[i].length + 5 && d.indexOf(codigos[i]) === 0) {
                sel.value = '+' + codigos[i];
                inp.value = limpiar(inp, codigos[i]);
                return;
            }
        }
        // Sin código reconocible: se conserva tal cual y no se concatena al enviar
        if (d.length > 9) {
            inp.dataset.telCrudo = '1';
            inp.value = inp.value.trim();
        } else {
            inp.value = limpiar(inp, sel.value);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var sels = document.querySelectorAll('select[data-tel-prefijo]');

        Array.prototype.forEach.call(sels, function (sel) {
            init(sel);

            var inp = document.getElementById(sel.getAttribute('data-tel-input'));
            if (inp) {
                inp.addEventListener('input', function () {
                    delete inp.dataset.telCrudo;
                });
            }

            var form = sel.closest('form');
            if (form && !form.dataset.telPaisOn) {
                form.dataset.telPaisOn = '1';
                form.addEventListener('submit', function () {
                    Array.prototype.forEach.call(
                        form.querySelectorAll('select[data-tel-prefijo]'),
                        function (s) {
                            var i = document.getElementById(s.getAttribute('data-tel-input'));
                            if (!i) return;
                            if (i.dataset.telCrudo === '1') {
                                // Código no listado: se envía sin prefijo para no duplicarlo
                                var vacio = s.querySelector('option[value=""]');
                                s.value = vacio ? '' : s.value;
                                return;
                            }
                            i.value = window.telPaisCompleto(s, i);
                        }
                    );
                });
            }
        });
    });
})();
