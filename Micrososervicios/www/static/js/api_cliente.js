/* Cliente HTTP del API Gateway (LibrosPE) — fetch con JWT stateless.
 *
 * Uso:
 *   apiLogin('/api/v1/auth/login', {correo, clave})
 *   apiFetch('/api/v1/ventas/crear', {method:'POST', body:{...}})
 *
 * El token se guarda en localStorage y viaja SIEMPRE en
 * Authorization: Bearer <jwt> (nunca en cookies -> inmune a CSRF).
 * Ante 401 se borra el token y se redirige a /api/login.
 */
(function () {
  'use strict';

  var LLAVE = 'librospe_jwt';

  function token() {
    try { return localStorage.getItem(LLAVE) || ''; } catch (e) { return ''; }
  }

  function guardarToken(t) {
    try { localStorage.setItem(LLAVE, t); } catch (e) { /* sin storage */ }
  }

  function cerrarSesion() {
    try { localStorage.removeItem(LLAVE); } catch (e) { /* sin storage */ }
  }

  function apiFetch(ruta, opciones) {
    opciones = opciones || {};
    var cabeceras = Object.assign({ 'Accept': 'application/json' }, opciones.headers || {});
    var t = token();
    if (t) cabeceras['Authorization'] = 'Bearer ' + t;

    var body = opciones.body;
    if (body !== undefined && body !== null && typeof body !== 'string') {
      cabeceras['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }

    return fetch(ruta, {
      method: opciones.method || 'GET',
      headers: cabeceras,
      body: body,
      credentials: 'omit'
    }).then(function (resp) {
      var tipo = (resp.headers.get('Content-Type') || '');
      var promesa = tipo.indexOf('json') >= 0 ? resp.json() : resp.text();
      return promesa.then(function (datos) {
        if (resp.status === 401) {
          cerrarSesion();
          window.location.href = '/api/login';
          return Promise.reject({ status: 401, datos: datos });
        }
        if (!resp.ok) {
          return Promise.reject({ status: resp.status, datos: datos });
        }
        return datos;
      });
    });
  }

  function apiLogin(ruta, credenciales) {
    return apiFetch(ruta, { method: 'POST', body: credenciales })
      .then(function (datos) {
        if (datos && datos.token) guardarToken(datos.token);
        return datos;
      });
  }

  window.apiFetch = apiFetch;
  window.apiLogin = apiLogin;
  window.apiCerrarSesion = cerrarSesion;
  window.apiToken = token;
})();
