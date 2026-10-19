
    // ===============================
    // VARIABLES GLOBALES
    // ===============================
    let carrito = [];
    let cuponAplicado = null;
    let descuento = 0;
    let tipoEntregaSeleccionado = 'recojo';
    let direccionEntrega = '';
    let mapaCarrito = null;
    let marcadorCarrito = null;
    let circuloPrecision = null;  // margen de error del último geolocalizado

    // ===============================
    // ZONAS DE DELIVERY (distrito -> costo de envío)
    // Edita aquí los distritos y tarifas si la tienda cambia la política.
    // ===============================
    var ZONAS_DELIVERY = {
        1: { costo: 5,  nombre: 'Zona 1 · Entrega rápida',
             distritos: ['Huancayo (Cercado)', 'El Tambo', 'Chilca', 'Pilcomayo'] },
        2: { costo: 12, nombre: 'Zona 2 · Entrega programada',
             distritos: ['San Jerónimo de Tunán', 'San Agustín (Cajas)', 'Hualhuas', 'Saño',
                         'Huancán', 'Huayucachi', 'Viques', 'Sapallanga', 'Sicaya'] },
        3: { costo: 20, nombre: 'Zona 3 · Envío especial',
             distritos: ['Chupuro', 'Colca', 'Chacapampa', 'Chicche', 'Carhuacallanga',
                         'Chongos Alto', 'Huasicancha', 'Ingenio', 'Quichuay', 'Quilcas',
                         'San Pedro de Saño', 'Santo Domingo de Acobamba', 'Pucará', 'Cullhuas',
                         'Pariahuanca'] }
    };
    var distritoEntrega = '';
    var costoEntrega = 0;

    // ===============================
    // CENTROS DE LOS DISTRITOS DE ENTREGA
    // Coordenadas del centro de cada distrito de la provincia de Huancayo
    // (Junín). Se usan para centrar el mapa en el distrito elegido sin
    // depender de internet: si algún día se agrega un distrito nuevo, se
    // resuelve con Nominatim (ver geocodificarDistrito).
    // ===============================
    var CENTROS_DISTRITO = {
        'Huancayo (Cercado)':        { lat: -12.068098, lng: -75.210095 },
        'El Tambo':                   { lat: -12.056906, lng: -75.216436 },
        'Chilca':                     { lat: -12.086334, lng: -75.208289 },
        'Pilcomayo':                  { lat: -12.049373, lng: -75.250404 },
        'San Jerónimo de Tunán':      { lat: -11.949024, lng: -75.282712 },
        'San Agustín (Cajas)':        { lat: -11.990063, lng: -75.244004 },
        'Hualhuas':                   { lat: -11.971609, lng: -75.251050 },
        'Saño':                       { lat: -11.957327, lng: -75.257295 },
        'Huancán':                    { lat: -12.106278, lng: -75.216796 },
        'Huayucachi':                 { lat: -12.137816, lng: -75.222934 },
        'Viques':                     { lat: -12.159667, lng: -75.232318 },
        'Sapallanga':                 { lat: -12.141190, lng: -75.157824 },
        'Sicaya':                     { lat: -12.014454, lng: -75.280519 },
        'Chupuro':                    { lat: -12.155252, lng: -75.245458 },
        'Colca':                      { lat: -12.317826, lng: -75.223131 },
        'Chacapampa':                 { lat: -12.272300, lng: -75.120086 },
        'Chicche':                    { lat: -12.295962, lng: -75.297748 },
        'Carhuacallanga':             { lat: -12.354751, lng: -75.200512 },
        'Chongos Alto':               { lat: -12.311269, lng: -75.289033 },
        'Huasicancha':                { lat: -12.332013, lng: -75.282125 },
        'Ingenio':                    { lat: -11.889759, lng: -75.265417 },
        'Quichuay':                   { lat: -11.889812, lng: -75.286375 },
        'Quilcas':                    { lat: -11.937489, lng: -75.259295 },
        'San Pedro de Saño':          { lat: -11.958942, lng: -75.258274 },
        'Santo Domingo de Acobamba': { lat: -11.768890, lng: -74.795196 },
        'Pucará':                     { lat: -12.172779, lng: -75.145997 },
        'Cullhuas':                   { lat: -12.223783, lng: -75.170550 },
        'Pariahuanca':                { lat: -12.028990, lng: -74.852245 }
    };
    // Zoom por zona: la Zona 1 es urbana y se ve mas cerca; la Zona 3 es
    // dispersa y se ve mas amplia para que el distrito entre en la pantalla.
    var ZOOM_POR_ZONA = { 1: 14, 2: 13, 3: 12 };
    // Centro pendiente de aplicar (si se eligio distrito antes de que el mapa existiera).
    var centroDistritoPendiente = null;

    function numeroZonaPorDistrito(d) {
        if (!d) return null;
        for (var z in ZONAS_DELIVERY) {
            if (ZONAS_DELIVERY[z].distritos.indexOf(d) !== -1) return z;
        }
        return null;
    }
    // Normaliza texto (sin acentos y en minusculas) para comparar nombres.
    function normalizarTexto(t) {
        if (!t) return '';
        var s = t.toString().toLowerCase();
        if (s.normalize) s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        return s.trim();
    }
    function buscarCentroDistrito(distrito) {
        var clave = normalizarTexto(distrito);
        for (var nombre in CENTROS_DISTRITO) {
            if (normalizarTexto(nombre) === clave) return CENTROS_DISTRITO[nombre];
        }
        return null;
    }
    // ===============================
    // DETECCION DEL DISTRITO A PARTIR DEL PIN
    // Cuando el cliente marca su punto se hace geocodificacion inversa y el
    // distrito detectado se escribe solo en el selector (asi el costo de
    // envio se recalcula sin que el cliente tenga que elegirlo a mano).
    // ===============================
    // Nombres que devuelve el geocodificador -> opcion del selector.
    var ALIAS_DISTRITO = {
        'huancayo': 'Huancayo (Cercado)',
        'huan cayo': 'Huancayo (Cercado)',
        'san agustin de cajas': 'San Agustín (Cajas)',
        'san agustin': 'San Agustín (Cajas)',
        'cajas': 'San Agustín (Cajas)',
        'san pedro de sano': 'San Pedro de Saño',
        'san pedro': 'San Pedro de Saño',
        'santo domingo de acrobamba': 'Santo Domingo de Acobamba',
        'acobamba': 'Santo Domingo de Acobamba',
        'san jeronimo de tunan': 'San Jerónimo de Tunán',
        'tunan': 'San Jerónimo de Tunán',
        'qhichuay': 'Quichuay',
        'chongos altos': 'Chongos Alto'
    };
    // Devuelve la opcion del selector que corresponde a un nombre de distrito
    // (o null si no es un distrito de reparto).
    function opcionDistritoPorNombre(nombre) {
        if (!nombre) return null;
        var clave = normalizarTexto(nombre);
        if (!clave) return null;
        for (var z in ZONAS_DELIVERY) {
            var lista = ZONAS_DELIVERY[z].distritos;
            for (var i = 0; i < lista.length; i++) {
                if (normalizarTexto(lista[i]) === clave) return lista[i];
                // "Huancayo (Cercado)" -> "huancayo"
                var sinParen = normalizarTexto(lista[i].replace(/\(.*\)/, ''));
                if (sinParen && sinParen === clave) return lista[i];
            }
        }
        if (ALIAS_DISTRITO[clave]) return ALIAS_DISTRITO[clave];
        return null;
    }
    // Detecta el distrito a partir de la respuesta de geocodificacion inversa.
    function detectarDistritoEnRespuesta(data) {
        if (!data) return null;
        var addr = data.address || {};
        var partes = String(data.display_name || '').split(',').map(function(s) { return s.trim(); });
        // 1) campos administrativos (los mas fiables)
        var campos = [addr.city_district, addr.city, addr.town, addr.municipality, addr.county];
        for (var i = 0; i < campos.length; i++) {
            var opcion = opcionDistritoPorNombre(campos[i]);
            if (opcion) return { distrito: opcion, texto: campos[i], fueraDeZona: false };
        }
        // 2) partes de la direccion (p.ej. "Chicche, Huancayo, Junin, Peru")
        var region = normalizarTexto(addr.region || '');
        var estado = normalizarTexto(addr.state || '');
        var ignorar = [region, estado, normalizarTexto(addr.country || ''), 'peru'];
        // En Junin, "Huancayo" en la direccion es la provincia: se deja para
        // el final por si el distrito real no se pudo leer.
        var postponed = null;
        for (var j = 0; j < partes.length; j++) {
            var n = normalizarTexto(partes[j]);
            if (!n || ignorar.indexOf(n) !== -1) continue;
            var op = opcionDistritoPorNombre(partes[j]);
            if (op) {
                if (n === 'huancayo' && (estado === 'junin' || region === 'huancayo')) {
                    postponed = { distrito: op, texto: partes[j], fueraDeZona: false };
                    continue;
                }
                return { distrito: op, texto: partes[j], fueraDeZona: false };
            }
        }
        if (postponed) return postponed;
        // No se pudo identificar: se informa si esta fuera de nuestra provincia.
        var fuera = !!(region && region !== 'huancayo' && estado !== 'junin');
        return { distrito: null, texto: partes[0] || '', fueraDeZona: fuera };
    }
    // Detecta el distrito a partir de un texto de direccion (sugerencias).
    function detectarDistritoEnTexto(texto) {
        if (!texto) return null;
        var partes = String(texto).split(',').map(function(s) { return s.trim(); });
        var postponed = null;
        for (var i = 0; i < partes.length; i++) {
            var op = opcionDistritoPorNombre(partes[i]);
            if (!op) continue;
            // "Huancayo" puede ser la provincia: solo se usa si no hay otro distrito.
            if (normalizarTexto(partes[i]) === 'huancayo') {
                if (!postponed) postponed = { distrito: op, texto: partes[i], fueraDeZona: false };
                continue;
            }
            return { distrito: op, texto: partes[i], fueraDeZona: false };
        }
        if (postponed) return postponed;
        return { distrito: null, texto: partes[0] || '', fueraDeZona: true };
    }
    // Escribe el distrito detectado en el selector y recalcula el envio.
    function aplicarDistritoDetectado(info, pintarMensaje) {
        if (!info) return info;
        var sel = document.getElementById('distritoEntregaSel');
        if (info.distrito) {
            if (sel) {
                var existe = Array.prototype.some.call(sel.options, function(o) { return o.value === info.distrito; });
                if (existe) sel.value = info.distrito;
            }
            aplicarDistrito(info.distrito);
            if (pintarMensaje === false) return info;
            var zona = zonaPorDistrito(info.distrito);
            avisarMapa('<i class="fas fa-check-circle text-success me-1"></i> Ubicación marcada correctamente · ' +
                       'Distrito <b>' + info.distrito + '</b>' +
                       (zona ? ' · envío S/ ' + costoEntrega.toFixed(2) : ''), false, 'text-success');
        } else {
            if (pintarMensaje === false) return info;
            avisarMapa('<i class="fas fa-exclamation-triangle text-warning me-1"></i> ' +
                       'El punto marcado está en <b>' + (info.texto || 'otra zona') + '</b>, ' +
                       'fuera de nuestras zonas de reparto.', true);
        }
        return info;
    }
    // Mensaje del mapa (debajo del mapa).
    function avisarMapa(html, esAviso, clase) {
        const mapaAviso = document.getElementById('mapaAviso');
        if (!mapaAviso) return;
        mapaAviso.innerHTML = html;
        mapaAviso.classList.remove('text-muted', 'text-success', 'text-warning', 'text-primary', 'fw-bold');
        mapaAviso.classList.add(clase || (esAviso ? 'text-warning' : 'text-primary'));
    }
    // Vista por defecto: la libreria (El Tambo, Huancayo).
    function vistaPorDefecto() {
        const div = document.getElementById('mapaCarrito');
        const lat = parseFloat(div && div.dataset ? div.dataset.lat : NaN);
        const lng = parseFloat(div && div.dataset ? div.dataset.lng : NaN);
        if (!isNaN(lat) && !isNaN(lng)) return [lat, lng];
        return [-12.065863, -75.215397];
    }
    // Limpia la direccion, el pin y las coordenadas de entrega.
    // Se usa cuando el cliente cambia de distrito a mano: la direccion y el
    // pin anteriores son de otro distrito, asi que dejarlos seria entregar
    // en el sitio equivocado.
    function limpiarPuntoEntrega() {
        const latEl = document.getElementById('latitud');
        const lngEl = document.getElementById('longitud');
        // Si habia un punto marcado, la direccion autocompletada tambien es
        // de ese punto (o de la sugerencia elegida): se limpia. Si el cliente
        // solo escribio el texto a mano, se respeta.
        const habiaPunto = !!marcadorCarrito || (latEl && latEl.value);
        const direccionInput = document.getElementById('direccion');
        if (habiaPunto && direccionInput) direccionInput.value = '';
        if (latEl) latEl.value = '';
        if (lngEl) lngEl.value = '';
        localStorage.removeItem('latitudEntrega');
        localStorage.removeItem('longitudEntrega');
        if (mapaCarrito) {
            if (marcadorCarrito) {
                mapaCarrito.removeLayer(marcadorCarrito);
                marcadorCarrito = null;
            }
            if (circuloPrecision) {
                mapaCarrito.removeLayer(circuloPrecision);
                circuloPrecision = null;
            }
        }
    }
    // Centra el mapa en el distrito elegido. NO fija el punto de entrega:
    // el cliente sigue teniendo que marcar su direccion exacta.
    function centrarMapaEnDistrito(distrito, recienCambiado) {
        if (!distrito) return;
        var centro = buscarCentroDistrito(distrito);
        if (centro) {
            aplicarVistaDistrito(centro, distrito, false, recienCambiado);
        } else if (!mapaCarrito) {
            // El mapa todavia no existe: se resuelve cuando se cree.
            centroDistritoPendiente = { distrito: distrito };
        } else {
            geocodificarDistrito(distrito, recienCambiado);
        }
    }
    function aplicarVistaDistrito(centro, distrito, sinAnimacion, recienCambiado) {
        const zona = numeroZonaPorDistrito(distrito);
        const zoom = ZOOM_POR_ZONA[zona] || 13;
        if (!mapaCarrito) {
            centroDistritoPendiente = { lat: centro.lat, lng: centro.lng, zoom: zoom, distrito: distrito };
            return;
        }
        centroDistritoPendiente = null;
        mapaCarrito.invalidateSize();
        if (!sinAnimacion && typeof mapaCarrito.flyTo === 'function') {
            mapaCarrito.flyTo([centro.lat, centro.lng], zoom, { duration: 0.8 });
        } else {
            mapaCarrito.setView([centro.lat, centro.lng], zoom);
        }
        avisarMapa(recienCambiado
            ? '<i class="fas fa-map-marker-alt me-1"></i> Distrito actualizado a <b>' + distrito +
              '</b>. Vuelve a marcar tu punto en el mapa.'
            : '<i class="fas fa-map-marker-alt me-1"></i> Mostrando <b>' + distrito +
              '</b>. Marca tu punto exacto de entrega.');
    }
    // Respaldo para distritos que no estan en la tabla: se geocodifican con
    // Nominatim (mismo servicio que usa el buscador de direcciones).
    function geocodificarDistrito(distrito, recienCambiado) {
        const base = String(distrito).split('(')[0].trim();
        const url = 'https://nominatim.openstreetmap.org/search?format=json&q=' +
            encodeURIComponent(base + ', Provincia de Huancayo, Junín, Perú') +
            '&countrycodes=pe&limit=1&accept-language=es';
        avisarMapa('<i class="fas fa-spinner fa-spin me-1"></i> Buscando el distrito ' + distrito + '...');
        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (!data || !data.length) {
                    avisarMapa('<i class="fas fa-exclamation-triangle text-warning me-1"></i> ' +
                               'No se pudo ubicar el distrito ' + distrito + '.', true);
                    return;
                }
                aplicarVistaDistrito({ lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) }, distrito, false, recienCambiado);
            })
            .catch(() => {
                avisarMapa('<i class="fas fa-exclamation-triangle text-warning me-1"></i> ' +
                           'No se pudo centrar el mapa en ' + distrito + '.', true);
            });
    }

    function zonaPorDistrito(d) {
        if (!d) return null;
        for (var z in ZONAS_DELIVERY) {
            if (ZONAS_DELIVERY[z].distritos.indexOf(d) !== -1) return ZONAS_DELIVERY[z];
        }
        return null;
    }
    function costoPorDistrito(d) {
        var z = zonaPorDistrito(d);
        return z ? z.costo : 0;
    }
    function aplicarDistrito(d) {
        distritoEntrega = d || '';
        costoEntrega = costoPorDistrito(distritoEntrega);
        localStorage.setItem('distritoEntrega', distritoEntrega);
        localStorage.setItem('costoEntrega', String(costoEntrega));
        var info = document.getElementById('zonaInfo');
        if (info) {
            if (!distritoEntrega) {
                info.innerHTML = '<span class="text-danger"><i class="fas fa-exclamation-circle me-1"></i>Elige tu distrito para calcular el envío.</span>';
            } else {
                var z = zonaPorDistrito(distritoEntrega);
                info.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i>' +
                    z.nombre + ': envío S/ ' + costoEntrega.toFixed(2) + '</span>';
            }
        }
        actualizarTotales();
    }
    function inicializarDistritos() {
        var sel = document.getElementById('distritoEntregaSel');
        if (!sel) return;
        var html = '<option value="">— Elige tu distrito —</option>';
        for (var z in ZONAS_DELIVERY) {
            var zona = ZONAS_DELIVERY[z];
            html += '<optgroup label="' + zona.nombre + ' (S/ ' + zona.costo.toFixed(2) + ')">';
            zona.distritos.forEach(function(d) {
                html += '<option value="' + d + '">' + d + '</option>';
            });
            html += '</optgroup>';
        }
        sel.innerHTML = html;
        var guardado = localStorage.getItem('distritoEntrega');
        if (guardado) {
            // Dejar el distrito guardado marcado en el selector.
            var existe = Array.prototype.some.call(sel.options, function(o) { return o.value === guardado; });
            if (existe) sel.value = guardado;
            aplicarDistrito(guardado);
            // Si ya habia un distrito elegido, el mapa se abre en ese distrito.
            centrarMapaEnDistrito(guardado);
        }
    }
    function cambiarDistritoEntrega() {
        var sel = document.getElementById('distritoEntregaSel');
        var d = sel ? sel.value : '';
        aplicarDistrito(d);
        // La direccion y el pin anteriores son de otro distrito: se limpian
        // para que el cliente marque su punto en el nuevo distrito.
        limpiarPuntoEntrega();
        // El mapa se centra en el distrito elegido.
        centrarMapaEnDistrito(d, true);
    }

    // Icono del pin de entrega.
    function iconoPin() {
        return L.icon({
            iconUrl: '/static/img/pin.png',
            iconSize: [32, 32],
            iconAnchor: [16, 32],
            popupAnchor: [0, -32]
        });
    }

    // Crea (o mueve) el marcador de entrega. Es ARRASTRABLE para afinar el punto.
    function colocarMarcador(lat, lng) {
        const punto = [parseFloat(lat), parseFloat(lng)];
        if (marcadorCarrito) {
            marcadorCarrito.setLatLng(punto);
        } else {
            marcadorCarrito = L.marker(punto, { icon: iconoPin(), draggable: true }).addTo(mapaCarrito);
            // Al soltar el pin, ese punto pasa a ser la ubicación final.
            marcadorCarrito.on('dragend', function() {
                const p = marcadorCarrito.getLatLng();
                fijarPuntoManual(p.lat, p.lng);
            });
        }
        return marcadorCarrito;
    }

    // Fija un punto elegido a mano (clic, sugerencia o arrastre): es preciso, así
    // que quita el círculo de error del geolocalizado y actualiza la dirección.
    function fijarPuntoManual(lat, lng, direccionForzada) {
        const latStr = parseFloat(lat).toFixed(6);
        const lngStr = parseFloat(lng).toFixed(6);

        document.getElementById('latitud').value = latStr;
        document.getElementById('longitud').value = lngStr;
        localStorage.setItem('latitudEntrega', latStr);
        localStorage.setItem('longitudEntrega', lngStr);

        if (circuloPrecision) {
            mapaCarrito.removeLayer(circuloPrecision);
            circuloPrecision = null;
        }

        colocarMarcador(latStr, lngStr);
        marcadorCarrito.bindPopup('<b>Tu ubicación de entrega</b><br>Lat: ' + latStr + '<br>Lng: ' + lngStr).openPopup();

        const mapaAviso = document.getElementById('mapaAviso');
        const pintarAviso = (html, esOk) => {
            if (!mapaAviso) return;
            mapaAviso.innerHTML = html;
            mapaAviso.classList.remove('text-muted', 'text-success', 'text-warning', 'fw-bold');
            mapaAviso.classList.add(esOk ? 'text-success' : 'text-muted');
            if (esOk) mapaAviso.classList.add('fw-bold');
        };

        // Si la dirección ya se conoce (sugerencia elegida), no se vuelve a consultar.
        if (direccionForzada) {
            // El distrito se deduce del texto de la dirección elegida.
            aplicarDistritoDetectado(detectarDistritoEnTexto(direccionForzada));
            return;
        }

        pintarAviso('<i class="fas fa-spinner fa-spin me-1"></i> Obteniendo dirección...', false);
        fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latStr}&lon=${lngStr}&zoom=18&addressdetails=1&accept-language=es`)
            .then(r => r.json())
            .then(data => {
                if (data && data.display_name) {
                    const direccionInput = document.getElementById('direccion');
                    if (direccionInput) direccionInput.value = data.display_name;
                    marcadorCarrito.setPopupContent(
                        '<b>Tu ubicación de entrega</b><br>' + data.display_name + '<br><small>Lat: ' + latStr + ' Lng: ' + lngStr + '</small>'
                    ).openPopup();
                }
                // El distrito se actualiza solo segun el punto marcado.
                aplicarDistritoDetectado(detectarDistritoEnRespuesta(data));
            })
            .catch(() => {
                pintarAviso('<i class="fas fa-check-circle text-success me-1"></i> Ubicación marcada correctamente', true);
            });
    }

    // ===============================
    // FUNCIÓN PARA VALIDAR STOCK CON EL SERVIDOR
    // ===============================
    async function validarStockProducto(productoId, cantidadDeseada) {
        try {
            const response = await fetch(`/api/productos/${productoId}/stock`);
            const data = await response.json();
            
            if (!response.ok) {
                console.error("Error al consultar stock:", data.error);
                return { valido: true, stockDisponible: 999, nombre: "Producto" };
            }
            
            const stockDisponible = data.stock;
            return { 
                valido: cantidadDeseada <= stockDisponible, 
                stockDisponible: stockDisponible,
                nombre: data.nombre
            };
        } catch (error) {
            console.error("Error validando stock:", error);
            return { valido: true, stockDisponible: 999, nombre: "Producto" };
        }
    }

    // ===============================
    // CARGAR DIRECCIÓN DEL CLIENTE DESDE BASE DE DATOS
    // ===============================
    async function cargarDireccionCliente() {
        const usuarioLogueado = document.getElementById('usuarioLogueado')?.value === 'true';
        if (!usuarioLogueado) {
            console.log("Usuario no logueado, no se carga dirección");
            return;
        }

        try {
            console.log("Solicitando dirección a /api/cliente/direccion");
            const response = await fetch('/api/cliente/direccion');

            if (!response.ok) {
                console.error("Error HTTP:", response.status);
                return;
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.error("La respuesta no es JSON:", contentType);
                return;
            }

            const data = await response.json();
            console.log("Respuesta de dirección:", data);

            if (data.success && data.direccion) {
                const direccionInput = document.getElementById('direccion');
                const direccionAyuda = document.getElementById('direccionAyuda');
                if (direccionInput) {
                    direccionInput.value = data.direccion;
                    if (direccionAyuda) {
                        direccionAyuda.innerHTML = '<i class="fas fa-check-circle text-success"></i> Dirección cargada desde tu perfil. Puedes modificarla si lo deseas.';
                        setTimeout(() => {
                            if (direccionAyuda) direccionAyuda.innerHTML = '';
                        }, 5000);
                    }
                    console.log("📍 Dirección cargada desde perfil:", data.direccion);
                }
            } else {
                console.log("No hay dirección guardada en el perfil");
            }
        } catch (error) {
            console.error("Error cargando dirección:", error);
        }
    }

    // ===============================
    // UBICAR MI POSICIÓN (Geolocalización)
    // ===============================
    function ubicarMiPosicion() {
        const btn = document.getElementById('btnMiUbicacion');
        const mapaAviso = document.getElementById('mapaAviso');

        if (!navigator.geolocation) {
            if (mapaAviso) {
                mapaAviso.innerHTML = '<i class="fas fa-exclamation-triangle text-warning me-1"></i> Tu navegador no soporta geolocalización';
            }
            return;
        }

        // Deshabilitar botón mientras busca
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Buscando...';
        }

        if (mapaAviso) {
            mapaAviso.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Obteniendo tu ubicación...';
            mapaAviso.classList.remove('text-success', 'text-warning', 'fw-bold');
            mapaAviso.classList.add('text-muted');
        }

        // Lectura FRESCA (maximumAge:0) y en alta precisión. Si el equipo no
        // tiene GPS (PC/laptop) y falla o tarda, se reintenta una vez en modo
        // red (más rápido, aunque menos exacto).
        navigator.geolocation.getCurrentPosition(
            pintarUbicacionCliente,
            function(error) {
                const falloRed = error && (error.code === error.TIMEOUT || error.code === error.POSITION_UNAVAILABLE);
                if (falloRed) {
                    if (mapaAviso) {
                        mapaAviso.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Afinando por red...';
                    }
                    navigator.geolocation.getCurrentPosition(
                        pintarUbicacionCliente,
                        mostrarErrorUbicacion,
                        { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 }
                    );
                } else {
                    mostrarErrorUbicacion(error);
                }
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
    }

    // Dibuja el punto del cliente junto con su margen de error real (± metros).
    function pintarUbicacionCliente(position) {
        const btn = document.getElementById('btnMiUbicacion');
        const mapaAviso = document.getElementById('mapaAviso');

        const lat = position.coords.latitude.toFixed(6);
        const lng = position.coords.longitude.toFixed(6);
        const margen = Math.round(position.coords.accuracy || 0); // metros de error

        // Guardar coordenadas (input del formulario + localStorage para el checkout)
        document.getElementById('latitud').value = lat;
        document.getElementById('longitud').value = lng;
        localStorage.setItem('latitudEntrega', lat);
        localStorage.setItem('longitudEntrega', lng);

        if (mapaCarrito) {
            // Si la ubicación es precisa, se acerca más.
            mapaCarrito.setView([lat, lng], margen && margen <= 150 ? 17 : 16);

            colocarMarcador(lat, lng);

            // Círculo con el margen de error real que reporta el navegador.
            if (circuloPrecision) {
                mapaCarrito.removeLayer(circuloPrecision);
                circuloPrecision = null;
            }
            if (margen > 0) {
                circuloPrecision = L.circle([lat, lng], {
                    radius: margen,
                    color: '#2563eb',
                    weight: 1,
                    fillColor: '#2563eb',
                    fillOpacity: 0.12
                }).addTo(mapaCarrito);
            }

            // Reverse geocoding para completar la dirección
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1&accept-language=es`)
                .then(response => response.json())
                .then(data => {
                    if (data && data.display_name) {
                        const direccionInput = document.getElementById('direccion');
                        if (direccionInput) {
                            direccionInput.value = data.display_name;
                        }
                        marcadorCarrito.setPopupContent(
                            '<b>Tu ubicación de entrega</b><br>' + data.display_name + '<br><small>Lat: ' + lat + ' Lng: ' + lng + ' (±' + margen + ' m)</small>'
                        ).openPopup();
                    }
                    // El distrito se actualiza solo con la ubicacion del GPS.
                    const info = aplicarDistritoDetectado(detectarDistritoEnRespuesta(data), false);
                    if (info && mapaAviso) {
                        if (info.distrito) {
                            const zona = zonaPorDistrito(info.distrito);
                            mapaAviso.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i> ¡Ubicación encontrada! (±' +
                                margen + ' m) · Distrito <b>' + info.distrito + '</b>' +
                                (zona ? ' · envío S/ ' + costoEntrega.toFixed(2) : '');
                            mapaAviso.classList.remove('text-muted', 'text-warning', 'fw-bold');
                            mapaAviso.classList.add('text-success', 'fw-bold');
                        } else if (info.fueraDeZona) {
                            mapaAviso.innerHTML = '<i class="fas fa-exclamation-triangle text-warning me-1"></i> Ubicación en <b>' +
                                (info.texto || 'otra zona') + '</b>, fuera de nuestras zonas de reparto (±' + margen + ' m)';
                            mapaAviso.classList.remove('text-muted', 'text-success', 'fw-bold');
                            mapaAviso.classList.add('text-warning');
                        }
                    }
                })
                .catch(() => {
                    marcadorCarrito.setPopupContent(
                        '<b>Tu ubicación de entrega</b><br><small>Lat: ' + lat + ' Lng: ' + lng + ' (±' + margen + ' m)</small>'
                    ).openPopup();
                });
        }

        // Aviso según la precisión: <=150 m se considera fiable.
        const fiable = margen > 0 && margen <= 150;
        if (mapaAviso) {
            if (fiable) {
                mapaAviso.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i> ¡Ubicación encontrada! (±' + margen + ' m)';
                mapaAviso.classList.remove('text-muted', 'text-warning');
                mapaAviso.classList.add('text-success', 'fw-bold');
            } else {
                mapaAviso.innerHTML = '<i class="fas fa-exclamation-triangle text-warning me-1"></i> Ubicación poco precisa (±' + margen +
                    ' m). Si no es exacta, haz clic en el mapa para afinarla.';
                mapaAviso.classList.remove('text-muted', 'text-success', 'fw-bold');
                mapaAviso.classList.add('text-warning');
            }
        }

        // Rehabilitar botón
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-crosshairs me-1"></i> Ubicar mi ubicación';
        }
    }

    function mostrarErrorUbicacion(error) {
        const btn = document.getElementById('btnMiUbicacion');
        const mapaAviso = document.getElementById('mapaAviso');

        let mensaje = 'No se pudo obtener tu ubicación';
        switch (error.code) {
            case error.PERMISSION_DENIED:
                mensaje = 'Permiso de ubicación denegado. Actívalo en tu navegador.';
                break;
            case error.POSITION_UNAVAILABLE:
                mensaje = 'Ubicación no disponible.';
                break;
            case error.TIMEOUT:
                mensaje = 'Tiempo de espera agotado.';
                break;
        }

        if (mapaAviso) {
            mapaAviso.innerHTML = '<i class="fas fa-exclamation-triangle text-warning me-1"></i> ' + mensaje;
            mapaAviso.classList.remove('text-muted', 'text-success', 'fw-bold');
            mapaAviso.classList.add('text-warning');
        }

        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-crosshairs me-1"></i> Ubicar mi ubicación';
        }
    }

    // ===============================
    // BUSCADOR DE DIRECCIONES (Nominatim)
    // ===============================
    let debounceTimer = null;

    function buscarDireccion(query) {
        if (!query || query.length < 3) {
            document.getElementById('sugerencias').style.display = 'none';
            return;
        }

        // Debounce para no hacer muchas peticiones
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&countrycodes=pe&limit=5&addressdetails=1&accept-language=es`)
                .then(response => response.json())
                .then(data => {
                    const sugerenciasDiv = document.getElementById('sugerencias');
                    if (!data || data.length === 0) {
                        sugerenciasDiv.innerHTML = '<div class="p-2 text-muted small">No se encontraron resultados</div>';
                        sugerenciasDiv.style.display = 'block';
                        return;
                    }

                    sugerenciasDiv.innerHTML = '';
                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'p-2 cursor-pointer small border-bottom';
                        div.style.cursor = 'pointer';
                        div.innerHTML = `<i class="fas fa-map-marker-alt text-danger me-1"></i> ${item.display_name.substring(0, 80)}...`;
                        div.addEventListener('click', () => {
                            // Seleccionar sugerencia
                            const direccionInput = document.getElementById('direccion');
                            direccionInput.value = item.display_name;
                            document.getElementById('sugerencias').style.display = 'none';

                            // Punto de la sugerencia = preciso: se fija como ubicación final
                            // (siempre, incluso si el mapa aún no terminó de cargar).
                            const lat = parseFloat(item.lat).toFixed(6);
                            const lng = parseFloat(item.lon).toFixed(6);
                            fijarPuntoManual(lat, lng, item.display_name);
                            if (mapaCarrito) {
                                mapaCarrito.setView([lat, lng], 16);
                            }
                        });
                        div.addEventListener('mouseenter', () => {
                            div.style.backgroundColor = '#f8f9fa';
                        });
                        div.addEventListener('mouseleave', () => {
                            div.style.backgroundColor = 'white';
                        });
                        sugerenciasDiv.appendChild(div);
                    });
                    sugerenciasDiv.style.display = 'block';
                })
                .catch(err => {
                    console.warn('Error buscando dirección:', err);
                });
        }, 400);
    }

    function configurarBuscador() {
        const direccionInput = document.getElementById('direccion');
        const sugerenciasDiv = document.getElementById('sugerencias');

        if (!direccionInput) return;

        // Buscar al escribir
        direccionInput.addEventListener('input', function(e) {
            buscarDireccion(e.target.value);
        });

        // Ocultar sugerencias al hacer clic fuera
        document.addEventListener('click', function(e) {
            if (!direccionInput.contains(e.target) && !sugerenciasDiv.contains(e.target)) {
                sugerenciasDiv.style.display = 'none';
            }
        });

        // Ocultar sugerencias con Escape
        direccionInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                sugerenciasDiv.style.display = 'none';
            }
        });
    }

    // ===============================
    // INICIALIZAR MAPA DE CARRITO
    // ===============================
    function inicializarMapaCarrito() {
        console.log('🗺️ inicializarMapaCarrito llamado');
        
        const mapaDiv = document.getElementById('mapaCarrito');
        if (!mapaDiv) {
            console.error('❌ No se encontró el div #mapaCarrito');
            return;
        }

        // Verificar que el contenedor sea visible
        const rect = mapaDiv.getBoundingClientRect();
        console.log('📐 Dimensiones del contenedor:', rect.width, 'x', rect.height);
        
        if (rect.width === 0 || rect.height === 0) {
            console.warn('⚠️ Contenedor tiene dimensiones 0, reintentando...');
            setTimeout(() => inicializarMapaCarrito(), 500);
            return;
        }

        // Si el mapa ya existe, solo redimensionar
        if (mapaCarrito) {
            mapaCarrito.invalidateSize();
            if (distritoEntrega) {
                centrarMapaEnDistrito(distritoEntrega);
            } else {
                mapaCarrito.setView(vistaPorDefecto(), 13);
            }
            console.log('✅ Mapa redimensionado');
            return;
        }

        // Mostrar indicador de carga
        const cargando = document.getElementById('mapaCargando');
        if (cargando) cargando.style.display = 'block';

        // Centro inicial por defecto: la libreria (El Tambo, Huancayo)
        mapaCarrito = L.map('mapaCarrito').setView(vistaPorDefecto(), 13);

        // Usar solo OpenStreetMap (no requiere API key)
        const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            updateWhenIdle: true,
            keepBuffer: 2
        });

        osmLayer.addTo(mapaCarrito);

        // Si el cliente ya habia elegido distrito (antes de que existiera el
        // mapa), el mapa se abre en ese distrito.
        if (centroDistritoPendiente) {
            const pendiente = centroDistritoPendiente;
            centroDistritoPendiente = null;
            if (pendiente.lat) {
                mapaCarrito.setView([pendiente.lat, pendiente.lng], pendiente.zoom || 13);
                avisarMapa('<i class="fas fa-map-marker-alt me-1"></i> Mostrando <b>' +
                           pendiente.distrito + '</b>. Marca tu punto exacto de entrega.');
            } else if (pendiente.distrito) {
                geocodificarDistrito(pendiente.distrito);
            }
        } else if (distritoEntrega) {
            centrarMapaEnDistrito(distritoEntrega);
        }

        // Ocultar indicador de carga cuando el mapa esté listo
        mapaCarrito.whenReady(() => {
            if (cargando) {
                setTimeout(() => {
                    cargando.style.display = 'none';
                }, 500);
            }
        });

        // Configurar buscador de direcciones
        configurarBuscador();

        // Evento clic en el mapa: fija el punto exacto donde se hace clic.
        mapaCarrito.on('click', function(e) {
            fijarPuntoManual(e.latlng.lat, e.latlng.lng);
        });
    }

    // ===============================
    // SELECCIONAR TIPO DE ENTREGA
    // ===============================
    function seleccionarEntrega(tipo) {
        tipoEntregaSeleccionado = tipo;

        document.querySelectorAll('.delivery-option').forEach(opt => {
            opt.classList.remove('selected');
        });
        document.querySelector(`.delivery-option[data-tipo="${tipo}"]`).classList.add('selected');

        const direccionDiv = document.getElementById('direccionEntrega');
        const infoRecojo = document.getElementById('infoRecojo');
        const envioTexto = document.getElementById('envioTexto');
        const direccionInput = document.getElementById('direccion');

        if (tipo === 'delivery') {
            direccionDiv.style.display = 'block';
            if (infoRecojo) infoRecojo.style.display = 'none';
            aplicarDistrito(distritoEntrega);
            // Inicializar mapa después de que el contenedor sea visible
            // Usar requestAnimationFrame para asegurar que el DOM se renderizó
            requestAnimationFrame(() => {
                setTimeout(() => {
                    inicializarMapaCarrito();
                    // Forzar redimensionado del mapa después de que sea visible
                    if (mapaCarrito) {
                        setTimeout(() => {
                            mapaCarrito.invalidateSize();
                            // Si ya hay un distrito elegido, se mantiene el mapa
                            // sobre ese distrito; si no, se muestra la libreria.
                            if (distritoEntrega) {
                                centrarMapaEnDistrito(distritoEntrega);
                            } else {
                                mapaCarrito.setView(vistaPorDefecto(), 13);
                            }
                        }, 100);
                    }
                }, 150);
            });
        } else {
            direccionDiv.style.display = 'none';
            if (infoRecojo) infoRecojo.style.display = 'block';
            distritoEntrega = '';
            costoEntrega = 0;
            localStorage.setItem('distritoEntrega', '');
            localStorage.setItem('costoEntrega', '0');
            envioTexto.innerHTML = 'Gratis';
            if (direccionInput) direccionInput.value = '';
            // Limpiar coordenadas si cambia a recojo
            const lat = document.getElementById('latitud');
            const lng = document.getElementById('longitud');
            if (lat) lat.value = '';
            if (lng) lng.value = '';
            if (marcadorCarrito) {
                mapaCarrito.removeLayer(marcadorCarrito);
                marcadorCarrito = null;
            }
            if (circuloPrecision) {
                mapaCarrito.removeLayer(circuloPrecision);
                circuloPrecision = null;
            }
        }

        actualizarTotales();
    }

    // ===============================
    // IR A CHECKOUT
    // ===============================
    function irACheckout() {
        let usuarioLogueado = document.getElementById('usuarioLogueado')?.value === 'true';

        if (!usuarioLogueado) {
            Swal.fire({
                icon: 'warning',
                title: 'Inicia sesión',
                text: 'Debes iniciar sesión para comprar',
                confirmButtonText: 'Iniciar',
                showCancelButton: true
            }).then((result) => {
                if (result.isConfirmed) window.location.href = '/login-cliente';
            });
            return;
        }

        if (carrito.length === 0) {
            Swal.fire({
                icon: 'error',
                title: 'Carrito vacío',
                text: 'Agrega productos'
            });
            return;
        }

        if (tipoEntregaSeleccionado === 'delivery') {
            let direccion = document.getElementById('direccion')?.value.trim();
            if (!direccion) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Dirección requerida',
                    text: 'Ingresa tu dirección de entrega'
                });
                return;
            }
            let lat = document.getElementById('latitud')?.value;
            let lng = document.getElementById('longitud')?.value;
            if (!lat || !lng) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Ubicación en el mapa requerida',
                    text: 'Marca tu ubicación exacta en el mapa haciendo clic'
                });
                return;
            }
            direccionEntrega = direccion;
            if (!distritoEntrega) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Distrito requerido',
                    text: 'Elige tu distrito de entrega para calcular el envío.'
                });
                return;
            }
        } else {
            direccionEntrega = '';
        }

        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        if (cuponAplicado) {
            localStorage.setItem('cuponAplicado', JSON.stringify(cuponAplicado));
            localStorage.setItem('descuento', descuento);
        }
        localStorage.setItem('tipoEntrega', tipoEntregaSeleccionado);
        localStorage.setItem('direccionEntrega', direccionEntrega);
        localStorage.setItem('distritoEntrega', distritoEntrega);
        localStorage.setItem('costoEntrega', String(costoEntrega));

        // Guardar coordenadas del mapa
        if (tipoEntregaSeleccionado === 'delivery') {
            let lat = document.getElementById('latitud')?.value || '';
            let lng = document.getElementById('longitud')?.value || '';
            localStorage.setItem('latitudEntrega', lat);
            localStorage.setItem('longitudEntrega', lng);
        }

        window.location.href = '/checkout';
    }

    // ===============================
    // APLICAR CUPÓN
    // ===============================
    function aplicarCupon() {
        let codigo = document.getElementById('cuponInput')?.value.toUpperCase();
        let mensajeDiv = document.getElementById('mensajeCupon');
        let descuentoRow = document.getElementById('descuentoRow');

        const cupones = {
            'LIBROS10': { descuento: 10, tipo: 'porcentaje', nombre: '10% off' },
            'BIENVENIDO5': { descuento: 5, tipo: 'fijo', nombre: 'S/5 off' },
            'FREESHIP': { descuento: 5, tipo: 'envio', nombre: 'Envío gratis' }
        };

        if (cupones[codigo]) {
            cuponAplicado = cupones[codigo];
            let subtotal = calcularSubtotal();

            if (cuponAplicado.tipo === 'envio') {
                descuento = 5;
                mensajeDiv.innerHTML = '<span class="text-success">✅ Envío gratis</span>';
            } else if (cuponAplicado.tipo === 'porcentaje') {
                descuento = subtotal * 0.1;
                mensajeDiv.innerHTML = '<span class="text-success">✅ 10% descuento</span>';
            } else {
                descuento = 5;
                mensajeDiv.innerHTML = '<span class="text-success">✅ S/5 descuento</span>';
            }
            descuentoRow.style.display = 'flex';
            actualizarTotales();
            Swal.fire({ icon: 'success', title: '¡Cupón aplicado!', timer: 1500, showConfirmButton: false });
        } else {
            mensajeDiv.innerHTML = '<span class="text-danger">❌ Inválido</span>';
        }
    }

    // ===============================
    // CALCULAR SUBTOTAL
    // ===============================
    function calcularSubtotal() {
        return carrito.reduce((s, i) => s + (i.precio * i.cantidad), 0);
    }

    // ===============================
    // ACTUALIZAR TOTALES
    // ===============================
    function actualizarTotales() {
        let subtotal = calcularSubtotal();
        let costoEnvio = 0;

        if (tipoEntregaSeleccionado === 'delivery' && cuponAplicado?.tipo !== 'envio') {
            costoEnvio = costoEntrega;
            document.getElementById('envioTexto').innerHTML = 'S/. ' + costoEnvio.toFixed(2);
        } else if (tipoEntregaSeleccionado === 'delivery' && cuponAplicado?.tipo === 'envio') {
            document.getElementById('envioTexto').innerHTML = 'Gratis (Cupón)';
        } else {
            document.getElementById('envioTexto').innerHTML = 'Gratis';
        }

        let descuentoAplicado = (cuponAplicado?.tipo === 'envio' && tipoEntregaSeleccionado === 'delivery') ? 0 : Math.min(descuento, subtotal);
        let total = subtotal - descuentoAplicado + costoEnvio;

        document.getElementById('subtotalCarrito').innerHTML = 'S/. ' + subtotal.toFixed(2);
        document.getElementById('totalFinal').innerHTML = 'S/. ' + total.toFixed(2);
        document.getElementById('descuentoMonto').innerHTML = '-S/. ' + descuentoAplicado.toFixed(2);
        document.getElementById('itemCount').innerHTML = carrito.reduce((sum, item) => sum + parseInt(item.cantidad || 1), 0);
    }

    // ===============================
    // VACIAR CARRITO
    // ===============================
    function vaciarCarrito() {
        Swal.fire({
            title: '¿Vaciar carrito?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            confirmButtonText: 'Sí'
        }).then((r) => {
            if (r.isConfirmed) {
                carrito = [];
                localStorage.removeItem('carritoCliente');
                localStorage.removeItem('cuponAplicado');
                localStorage.removeItem('descuento');
                localStorage.removeItem('tipoEntrega');
                localStorage.removeItem('direccionEntrega');
                cuponAplicado = null;
                descuento = 0;
                tipoEntregaSeleccionado = 'recojo';
                renderizarCarrito();
                Swal.fire('¡Vaciado!', '', 'success');
            }
        });
    }

    // ===============================
    // CAMBIAR CANTIDAD (CON VALIDACIÓN DE STOCK)
    // ===============================
    async function cambiarCantidad(idx, delta) {
        let nueva = carrito[idx].cantidad + delta;
        if (nueva < 1) return;
        
        let producto = carrito[idx];
        
        // Validar stock SOLO si estamos aumentando la cantidad
        if (delta > 0) {
            const stockInfo = await validarStockProducto(producto.id, nueva);
            
            if (!stockInfo.valido) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Stock insuficiente',
                    text: `Solo hay ${stockInfo.stockDisponible} unidades disponibles de "${producto.nombre}"`,
                    confirmButtonColor: '#3085d6'
                });
                return;
            }
            
            // Actualizar el stock guardado en el carrito
            carrito[idx].stock = stockInfo.stockDisponible;
        }
        
        carrito[idx].cantidad = nueva;
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        
        // Si hay cupón aplicado, eliminarlo al cambiar cantidades
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
            document.getElementById('descuentoRow').style.display = 'none';
            document.getElementById('mensajeCupon').innerHTML = '';
        }
        
        renderizarCarrito();
    }

    // ===============================
    // CAMBIAR CANTIDAD DESDE TECLADO (INPUT)
    // ===============================
    async function cambiarCantidadInput(idx, input) {
        let valor = parseInt(input.value, 10);
        if (isNaN(valor) || valor < 1) {
            valor = 1;
            input.value = 1;
        }

        let producto = carrito[idx];
        if (!producto) return;

        // Limitar al stock conocido
        if (producto.stock && valor > producto.stock) {
            valor = producto.stock;
        }

        if (valor === producto.cantidad) return;

        // Validar contra el stock real del servidor
        const stockInfo = await validarStockProducto(producto.id, valor);
        if (!stockInfo.valido) {
            Swal.fire({
                icon: 'warning',
                title: 'Stock insuficiente',
                text: `Solo hay ${stockInfo.stockDisponible} unidades disponibles de "${producto.nombre}"`,
                confirmButtonColor: '#3085d6'
            });
            input.value = producto.cantidad;
            return;
        }

        carrito[idx].stock = stockInfo.stockDisponible;
        carrito[idx].cantidad = valor;
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));

        // Si hay cupón aplicado, eliminarlo al cambiar cantidades
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
            document.getElementById('descuentoRow').style.display = 'none';
            document.getElementById('mensajeCupon').innerHTML = '';
        }

        renderizarCarrito();
    }

    // ===============================
    // ELIMINAR PRODUCTO
    // ===============================
    function eliminarProducto(idx) {
        carrito.splice(idx, 1);
        localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        
        if (cuponAplicado) {
            cuponAplicado = null;
            descuento = 0;
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
        }
        
        renderizarCarrito();
    }

    // ===============================
    // RENDERIZAR CARRITO
    // ===============================
    function renderizarCarrito() {
        let vacio = document.getElementById('carritoVacio');
        let lleno = document.getElementById('carritoLleno');
        let body = document.getElementById('carritoBody');
        let badge = document.getElementById('cartCountBadge');

        if (carrito.length === 0) {
            if (vacio) vacio.style.display = 'block';
            if (lleno) lleno.style.display = 'none';
            if (badge) badge.textContent = '0';
            return;
        }

        if (vacio) vacio.style.display = 'none';
        if (lleno) lleno.style.display = 'block';
        if (body) body.innerHTML = '';

        let totalItems = 0;
        
        for (let i = 0; i < carrito.length; i++) {
            let item = carrito[i];
            let cant = item.cantidad;
            let precio = item.precio;
            totalItems += cant;
            
            // Determinar advertencia de stock
            let stockWarning = '';
            if (item.stock && cant >= item.stock) {
                stockWarning = '<small class="text-danger stock-warning"><i class="fas fa-exclamation-triangle"></i> Stock máximo alcanzado</small>';
            } else if (item.stock && cant >= item.stock - 2) {
                stockWarning = '<small class="text-warning stock-warning"><i class="fas fa-info-circle"></i> Quedan pocas unidades</small>';
            }

            body.innerHTML += `
            <div class="cart-item p-3 border-bottom">
                <div class="row align-items-center">
                    <div class="col-12 col-sm-6 mb-3 mb-sm-0">
                        <div class="d-flex align-items-center flex-column flex-sm-row text-center text-sm-start">
                            <div class="bg-light rounded me-sm-3 p-2 d-flex align-items-center justify-content-center mb-2 mb-sm-0" style="width: 70px; height: 70px;">
                                ${item.imagen_url ? `<img src="${item.imagen_url}" style="max-width:60px; max-height:60px; object-fit:contain;">` : '<i class="fas fa-book fa-2x text-primary"></i>'}
                            </div>
                            <div>
                                <h6 class="mb-1 fw-bold">${escapeHtml(item.nombre)}</h6>
                                <small>S/. ${precio.toFixed(2)}</small>
                                ${stockWarning}
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-3 mb-2 mb-sm-0">
                        <div class="d-flex justify-content-center gap-2">
                            <button class="btn btn-sm btn-outline-secondary quantity-btn" onclick="cambiarCantidad(${i}, -1)">
                                <i class="fas fa-minus"></i>
                            </button>
                            <input type="number" class="form-control form-control-sm quantity-input" 
                                   value="${cant}" min="1" step="1" style="width:70px; text-align:center;"
                                   ${item.stock ? `max="${item.stock}"` : ''}
                                   inputmode="numeric"
                                   onchange="cambiarCantidadInput(${i}, this)"
                                   onkeypress="if(event.key==='Enter') this.blur()">
                            <button class="btn btn-sm btn-outline-secondary quantity-btn" onclick="cambiarCantidad(${i}, 1)">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                    <div class="col-4 col-sm-2 text-start text-sm-end">
                        <span class="fw-bold text-primary">S/. ${(precio * cant).toFixed(2)}</span>
                    </div>
                    <div class="col-2 col-sm-1 text-end">
                        <button class="btn btn-sm btn-link text-danger" onclick="eliminarProducto(${i})">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </div>
            </div>`;
        }
        
        if (badge) badge.textContent = totalItems;
        actualizarTotales();
    }

    // ===============================
    // CARGAR CARRITO (CON VALIDACIÓN DE STOCK)
    // ===============================
    async function cargarCarrito() {
        // Cargar datos guardados
        let g = localStorage.getItem('carritoCliente');
        carrito = g ? JSON.parse(g) : [];
        
        // Cargar cupón guardado
        let cuponGuardado = localStorage.getItem('cuponAplicado');
        if (cuponGuardado) {
            cuponAplicado = JSON.parse(cuponGuardado);
            descuento = parseFloat(localStorage.getItem('descuento') || 0);
            let descuentoRow = document.getElementById('descuentoRow');
            let mensajeCupon = document.getElementById('mensajeCupon');
            if (descuentoRow) descuentoRow.style.display = 'flex';
            if (mensajeCupon) mensajeCupon.innerHTML = '<span class="text-success">✅ Cupón aplicado</span>';
        }
        
        // Cargar tipo de entrega guardado
        let tipoGuardado = localStorage.getItem('tipoEntrega');
        if (tipoGuardado) {
            tipoEntregaSeleccionado = tipoGuardado;
            seleccionarEntrega(tipoEntregaSeleccionado);
        }
        
        // Cargar dirección guardada
        let direccionGuardada = localStorage.getItem('direccionEntrega');
        let direccionInput = document.getElementById('direccion');
        if (direccionGuardada && direccionInput) {
            direccionInput.value = direccionGuardada;
        }

        // Limpiar coordenadas antiguas del localStorage
        localStorage.removeItem('latitudEntrega');
        localStorage.removeItem('longitudEntrega');

        // Cargar coordenadas guardadas
        let latGuardada = localStorage.getItem('latitudEntrega');
        let lngGuardada = localStorage.getItem('longitudEntrega');
        if (latGuardada && lngGuardada) {
            document.getElementById('latitud').value = latGuardada;
            document.getElementById('longitud').value = lngGuardada;
        }
        
        // VALIDAR STOCK DE CADA PRODUCTO
        let carritoActualizado = [];
        let huboCambios = false;
        
        for (let item of carrito) {
            const stockInfo = await validarStockProducto(item.id, item.cantidad);
            
            if (!stockInfo.valido) {
                huboCambios = true;
                
                if (stockInfo.stockDisponible === 0) {
                    // Producto agotado - eliminarlo
                    await Swal.fire({
                        icon: 'warning',
                        title: 'Producto agotado',
                        text: `"${item.nombre}" ya no tiene stock. Se eliminó de tu carrito.`,
                        timer: 2000,
                        showConfirmButton: false
                    });
                    continue; // No agregar al carrito actualizado
                } else {
                    // Ajustar cantidad al stock disponible
                    item.cantidad = stockInfo.stockDisponible;
                    item.stock = stockInfo.stockDisponible;
                    carritoActualizado.push(item);
                    await Swal.fire({
                        icon: 'warning',
                        title: 'Stock reducido',
                        text: `"${item.nombre}" ahora solo tiene ${stockInfo.stockDisponible} unidades. Se ajustó tu carrito.`,
                        timer: 2000,
                        showConfirmButton: false
                    });
                }
            } else {
                // Stock suficiente, mantener el item
                item.stock = stockInfo.stockDisponible;
                carritoActualizado.push(item);
            }
        }
        
        // Si hubo cambios, actualizar localStorage y carrito
        if (huboCambios) {
            carrito = carritoActualizado;
            localStorage.setItem('carritoCliente', JSON.stringify(carrito));
        }
        
        // Renderizar el carrito
        renderizarCarrito();

        // Si hay delivery con coordenadas, restaurar el marcador
        if (tipoEntregaSeleccionado === 'delivery' && latGuardada && lngGuardada) {
            setTimeout(() => {
                inicializarMapaCarrito();
                if (mapaCarrito) {
                    const lat = parseFloat(latGuardada);
                    const lng = parseFloat(lngGuardada);
                    mapaCarrito.setView([lat, lng], 16);

                    colocarMarcador(lat, lng);
                    marcadorCarrito.bindPopup('<b>Tu ubicación de entrega</b><br>Lat: ' + latGuardada + '<br>Lng: ' + lngGuardada).openPopup();
                    
                    const mapaAviso = document.getElementById('mapaAviso');
                    if (mapaAviso) {
                        mapaAviso.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i> Ubicación marcada correctamente';
                        mapaAviso.classList.remove('text-muted');
                        mapaAviso.classList.add('text-success', 'fw-bold');
                    }
                }
            }, 300);
        }
    }

    // ===============================
    // ESCAPE HTML
    // ===============================
    function escapeHtml(t) {
        if (!t) return '';
        return t.replace(/[&<>]/g, function (m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    // ===============================
    // INICIALIZACIÓN
    // ===============================
    document.addEventListener('DOMContentLoaded', function () {
        // Cargar carrito con validación
        cargarCarrito();

        // Selector de distrito (define el costo de envío por zona)
        inicializarDistritos();

        // Configurar eventos
        const btnCupon = document.getElementById('btnAplicarCupon');
        const cuponInput = document.getElementById('cuponInput');
        
        if (btnCupon) btnCupon.addEventListener('click', aplicarCupon);
        if (cuponInput) {
            cuponInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') aplicarCupon();
            });
        }
    });
