/* Tarifas de Transporte - logica de la app.
 *
 * Los datos llegan en datos/tarifas.json, cifrados con AES-256-GCM.
 * La clave que escribe el usuario deriva la llave con PBKDF2 y descifra en el
 * telefono: el servidor nunca ve la clave y el archivo publicado es ilegible
 * sin ella. Una vez descifrado se guarda localmente para funcionar sin señal.
 */

const RUTA_DATOS = 'datos/tarifas.json';
const LS_CLAVE = 'tarifas.clave';
const LS_DATOS = 'tarifas.datos';

const $ = (id) => document.getElementById(id);

const estado = {
  datos: null,        // { generado, titulo, empresa, tarifas: [] }
  clave: null,
  filtros: { origen: null, destino: null, tam: null, tipo: null, texto: '' },
  campoHoja: null,
};

/* ================= utilidades ================= */

const sinAcentos = (t) =>
  String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();

function deB64(b64) {
  const bruto = atob(b64);
  const bytes = new Uint8Array(bruto.length);
  for (let i = 0; i < bruto.length; i++) bytes[i] = bruto.charCodeAt(i);
  return bytes;
}

function formatoMonto(n, moneda) {
  const simbolo = moneda === 'USD' ? 'U$S' : '$';
  return simbolo + ' ' + n.toLocaleString('es-AR', {
    minimumFractionDigits: n % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

function haceCuanto(iso) {
  const t = new Date(iso);
  if (isNaN(t)) return 'fecha desconocida';
  const seg = Math.floor((Date.now() - t.getTime()) / 1000);
  if (seg < 90) return 'hace un momento';
  const min = Math.floor(seg / 60);
  if (min < 60) return `hace ${min} min`;
  const hs = Math.floor(min / 60);
  if (hs < 24) return `hace ${hs} h`;
  const dias = Math.floor(hs / 24);
  if (dias === 1) return 'ayer';
  if (dias < 30) return `hace ${dias} días`;
  return t.toLocaleDateString('es-AR');
}

let avisoTimer;
function aviso(texto) {
  const caja = $('aviso');
  caja.textContent = texto;
  caja.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => { caja.hidden = true; }, 2800);
}

/* ================= descifrado ================= */

async function descifrar(sobre, clave) {
  const base = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(clave), 'PBKDF2', false, ['deriveKey']
  );
  const llave = await crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: deB64(sobre.kdf.sal),
      iterations: sobre.kdf.iteraciones,
      hash: 'SHA-256',
    },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt']
  );
  const plano = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: deB64(sobre.cifrado.iv) },
    llave,
    deB64(sobre.cifrado.datos)
  );
  return JSON.parse(new TextDecoder().decode(plano));
}

async function bajarSobre() {
  const resp = await fetch(RUTA_DATOS + '?t=' + Date.now(), { cache: 'no-store' });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  return resp.json();
}

/* ================= estado de los datos ================= */

function mostrarEstado(clase, texto) {
  $('estado-punto').className = 'punto' + (clase ? ' ' + clase : '');
  $('estado-texto').textContent = texto;
}

function guardarLocal() {
  try {
    localStorage.setItem(LS_DATOS, JSON.stringify(estado.datos));
  } catch (e) {
    // sin espacio: la app sigue funcionando en memoria hasta cerrarla
  }
}

function aplicarDatos(datos, { avisar } = {}) {
  const anterior = estado.datos && estado.datos.generado;
  estado.datos = datos;
  guardarLocal();

  document.title = datos.titulo || 'Tarifas de Transporte';
  $('titulo-app').textContent = datos.titulo || 'Tarifas de Transporte';

  mostrarEstado('', `${datos.tarifas.length} tarifas · actualizado ${haceCuanto(datos.generado)}`);
  construirFichas();
  render();

  if (avisar && anterior && anterior !== datos.generado) {
    aviso('Tarifas actualizadas');
  }
}

async function sincronizar({ manual } = {}) {
  const boton = $('boton-refrescar');
  boton.classList.add('girando');
  try {
    const sobre = await bajarSobre();

    if (estado.datos && sobre.generado === estado.datos.generado) {
      mostrarEstado('', `${estado.datos.tarifas.length} tarifas · actualizado ${haceCuanto(estado.datos.generado)}`);
      if (manual) aviso('Ya tiene las tarifas al día');
      return;
    }

    const datos = await descifrar(sobre, estado.clave);
    aplicarDatos(datos, { avisar: true });
    if (manual && !estado.datos) aviso('Tarifas actualizadas');
  } catch (err) {
    if (err && err.name === 'OperationError') {
      // la clave de publicacion cambio: hay que pedirla de nuevo
      localStorage.removeItem(LS_CLAVE);
      pedirClave('El operador cambió la clave. Pida la nueva y vuelva a entrar.');
      return;
    }
    if (estado.datos) {
      const sinRed = !navigator.onLine;
      mostrarEstado(sinRed ? 'offline' : 'error',
        (sinRed ? 'Sin conexión · ' : 'No se pudo actualizar · ') +
        `datos de ${haceCuanto(estado.datos.generado)}`);
      if (manual) aviso(sinRed ? 'Sin conexión, mostrando lo guardado' : 'No se pudo conectar');
    } else {
      mostrarEstado('error', 'No se pudieron cargar las tarifas');
      if (manual) aviso('No se pudo conectar');
    }
  } finally {
    boton.classList.remove('girando');
  }
}

/* ================= filtros ================= */

function pasaParcial(t, omitir) {
  const f = estado.filtros;
  if (omitir !== 'origen' && f.origen && t.o !== f.origen) return false;
  if (omitir !== 'destino' && f.destino && t.d !== f.destino) return false;
  if (omitir !== 'tam' && f.tam && t.tam !== f.tam) return false;
  if (omitir !== 'tipo' && f.tipo && t.tipo !== f.tipo) return false;
  if (omitir !== 'texto' && f.texto) {
    const palabras = sinAcentos(f.texto).split(/\s+/).filter(Boolean);
    if (!palabras.every((p) => t.b.includes(p))) return false;
  }
  return true;
}

const filtradas = () => (estado.datos ? estado.datos.tarifas.filter((t) => pasaParcial(t)) : []);

function opcionesDe(campo) {
  const llave = { origen: 'o', destino: 'd', tam: 'tam', tipo: 'tipo' }[campo];
  const cuentas = new Map();
  for (const t of estado.datos.tarifas) {
    if (!pasaParcial(t, campo)) continue;
    cuentas.set(t[llave], (cuentas.get(t[llave]) || 0) + 1);
  }
  const lista = [...cuentas.entries()].map(([valor, cuenta]) => ({ valor, cuenta }));
  if (campo === 'tam') {
    lista.sort((a, b) => Number(a.valor) - Number(b.valor));
  } else {
    lista.sort((a, b) => a.valor.localeCompare(b.valor, 'es'));
  }
  return lista;
}

function hayFiltros() {
  const f = estado.filtros;
  return !!(f.origen || f.destino || f.tam || f.tipo || f.texto);
}

function fijar(campo, valor) {
  estado.filtros[campo] = estado.filtros[campo] === valor ? null : valor;
  construirFichas();
  render();
}

/* ================= pintado ================= */

function construirFichas() {
  if (!estado.datos) return;

  for (const [campo, contenedor] of [['tam', $('fichas-tam')], ['tipo', $('fichas-tipo')]]) {
    const todas = [...new Set(estado.datos.tarifas.map((t) => (campo === 'tam' ? t.tam : t.tipo)))];
    todas.sort((a, b) => (campo === 'tam' ? Number(a) - Number(b) : a.localeCompare(b, 'es')));
    const disponibles = new Set(opcionesDe(campo).map((o) => o.valor));

    contenedor.innerHTML = '';
    for (const valor of todas) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ficha';
      b.textContent = campo === 'tam' ? valor + "'" : valor;
      b.setAttribute('aria-pressed', String(estado.filtros[campo] === valor));
      b.disabled = !disponibles.has(valor) && estado.filtros[campo] !== valor;
      b.addEventListener('click', () => fijar(campo, valor));
      contenedor.appendChild(b);
    }
  }

  for (const [campo, boton, salida] of [
    ['origen', $('sel-origen'), $('val-origen')],
    ['destino', $('sel-destino'), $('val-destino')],
  ]) {
    const valor = estado.filtros[campo];
    salida.textContent = valor || 'Cualquiera';
    salida.classList.toggle('vacio', !valor);
    boton.classList.toggle('activo', !!valor);
  }

  $('boton-limpiar').hidden = !hayFiltros();
}

function iconoVacio() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
    stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle>
    <path d="m20 20-3.5-3.5"></path></svg>`;
}

function tarjetaHTML(t) {
  const etiquetas = [
    `<span class="etiqueta">${t.tam}' ${t.tipo}</span>`,
    t.transportista ? `<span class="etiqueta">${t.transportista}</span>` : '',
    t.vencida
      ? `<span class="etiqueta alerta">Vencida ${new Date(t.hasta + 'T00:00').toLocaleDateString('es-AR')}</span>`
      : (t.hasta ? `<span class="etiqueta">Vigente hasta ${new Date(t.hasta + 'T00:00').toLocaleDateString('es-AR')}</span>` : ''),
  ].filter(Boolean).join('');

  return `
    <article class="tarjeta${t.vencida ? ' vencida' : ''}">
      <div class="tarjeta-arriba">
        <div class="tarjeta-ruta">
          <div class="tarjeta-tramo">
            <span class="punta">${t.o}</span>
            <span class="punta"><span class="flecha" aria-hidden="true">&rarr;</span>${t.d}</span>
          </div>
          <div class="tarjeta-meta">Contenedor ${t.tam} pies ${t.tipo}</div>
        </div>
        <div class="tarjeta-precio">
          <div class="precio-monto">${formatoMonto(t.tarifa, t.moneda)}</div>
          <div class="precio-moneda">${t.moneda}</div>
        </div>
      </div>
      <div class="etiquetas">${etiquetas}</div>
      ${t.obs ? `<p class="tarjeta-obs">${t.obs}</p>` : ''}
      <div class="tarjeta-pie">
        <button class="boton-copiar" data-copiar="${t.id}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="12" height="12" rx="2"></rect>
            <path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg>
          Copiar
        </button>
      </div>
    </article>`;
}

function textoParaCopiar(t) {
  const partes = [
    `${t.o} > ${t.d}`,
    `Contenedor ${t.tam}' ${t.tipo}`,
    `Tarifa: ${formatoMonto(t.tarifa, t.moneda)} ${t.moneda}`,
  ];
  if (t.transportista) partes.push(`Transportista: ${t.transportista}`);
  if (t.obs) partes.push(t.obs);
  if (t.vencida) partes.push('ATENCIÓN: tarifa vencida, confirmar antes de cotizar.');
  return partes.join('\n');
}

function render() {
  const caja = $('resultados');
  const cuenta = $('resultados-cuenta');

  if (!estado.datos) { caja.innerHTML = ''; return; }

  if (!hayFiltros()) {
    cuenta.textContent = `${estado.datos.tarifas.length} tarifas`;
    caja.innerHTML = `<div class="vacio-mensaje">${iconoVacio()}
      <p>Elija <strong>origen y destino</strong>, o escriba la ruta en el buscador.</p></div>`;
    return;
  }

  const lista = filtradas();
  cuenta.textContent = lista.length === 1 ? '1 tarifa' : `${lista.length} tarifas`;

  if (!lista.length) {
    caja.innerHTML = `<div class="vacio-mensaje">${iconoVacio()}
      <p>No hay tarifa cargada para esa combinación.<br>Pruebe quitando un filtro.</p></div>`;
    return;
  }

  lista.sort((a, b) =>
    a.o.localeCompare(b.o, 'es') || a.d.localeCompare(b.d, 'es') ||
    Number(a.tam) - Number(b.tam) || a.tipo.localeCompare(b.tipo, 'es')
  );
  caja.innerHTML = lista.map(tarjetaHTML).join('');
}

/* ================= hoja de origen / destino ================= */

function abrirHoja(campo) {
  estado.campoHoja = campo;
  $('hoja-titulo').textContent = campo === 'origen' ? 'Origen' : 'Destino';
  $('hoja-filtro').value = '';
  $('hoja').hidden = false;
  document.body.style.overflow = 'hidden';
  pintarHoja();
  setTimeout(() => $('hoja-filtro').focus({ preventScroll: true }), 120);
}

function cerrarHoja() {
  $('hoja').hidden = true;
  document.body.style.overflow = '';
  estado.campoHoja = null;
}

function pintarHoja() {
  const campo = estado.campoHoja;
  if (!campo) return;

  const filtro = sinAcentos($('hoja-filtro').value.trim());
  const opciones = opcionesDe(campo).filter((o) => !filtro || sinAcentos(o.valor).includes(filtro));
  const actual = estado.filtros[campo];
  const lista = $('hoja-lista');

  if (!opciones.length) {
    lista.innerHTML = '<li class="hoja-vacio">Sin coincidencias.</li>';
    return;
  }

  const tilde = `<svg class="tilde" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7"></path></svg>`;

  const filas = [
    `<li><button class="hoja-opcion" data-valor="" aria-selected="${!actual}">
       <span>Cualquiera</span>${!actual ? tilde : ''}</button></li>`,
    ...opciones.map((o) => `
      <li><button class="hoja-opcion" data-valor="${o.valor}" aria-selected="${actual === o.valor}">
        <span>${o.valor}</span>
        ${actual === o.valor ? tilde : `<span class="cuenta">${o.cuenta}</span>`}
      </button></li>`),
  ];
  lista.innerHTML = filas.join('');
}

/* ================= clave de acceso ================= */

function pedirClave(mensaje) {
  $('app').hidden = true;
  $('pantalla-clave').hidden = false;
  const error = $('clave-error');
  if (mensaje) { error.textContent = mensaje; error.hidden = false; }
  else { error.hidden = true; }
  $('campo-clave').value = '';
  setTimeout(() => $('campo-clave').focus({ preventScroll: true }), 150);
}

function entrarApp() {
  $('pantalla-clave').hidden = true;
  $('app').hidden = false;
}

async function probarClave(clave) {
  const sobre = await bajarSobre();
  const datos = await descifrar(sobre, clave);   // lanza OperationError si no coincide
  estado.clave = clave;
  try { localStorage.setItem(LS_CLAVE, clave); } catch (e) { /* modo privado */ }
  entrarApp();
  aplicarDatos(datos);
}

/* ================= arranque ================= */

function conectarEventos() {
  $('form-clave').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const clave = $('campo-clave').value.trim();
    const error = $('clave-error');
    const boton = $('boton-entrar');

    if (!clave) return;
    boton.disabled = true;
    boton.textContent = 'Verificando...';
    error.hidden = true;

    try {
      await probarClave(clave);
    } catch (err) {
      if (err && err.name === 'OperationError') {
        error.textContent = 'Clave incorrecta.';
      } else if (!navigator.onLine) {
        error.textContent = 'Sin conexión. Conéctese una vez para activar la app.';
      } else {
        error.textContent = 'No se pudieron bajar las tarifas. Reintente.';
      }
      error.hidden = false;
      $('campo-clave').select();
    } finally {
      boton.disabled = false;
      boton.textContent = 'Entrar';
    }
  });

  $('boton-refrescar').addEventListener('click', () => sincronizar({ manual: true }));

  $('sel-origen').addEventListener('click', () => abrirHoja('origen'));
  $('sel-destino').addEventListener('click', () => abrirHoja('destino'));

  $('boton-invertir').addEventListener('click', () => {
    const f = estado.filtros;
    [f.origen, f.destino] = [f.destino, f.origen];
    construirFichas();
    render();
  });

  $('boton-limpiar').addEventListener('click', () => {
    estado.filtros = { origen: null, destino: null, tam: null, tipo: null, texto: '' };
    $('campo-texto').value = '';
    $('limpiar-texto').hidden = true;
    construirFichas();
    render();
  });

  let debounce;
  $('campo-texto').addEventListener('input', (ev) => {
    const v = ev.target.value;
    $('limpiar-texto').hidden = !v;
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      estado.filtros.texto = v.trim();
      construirFichas();
      render();
    }, 120);
  });

  $('limpiar-texto').addEventListener('click', () => {
    $('campo-texto').value = '';
    $('limpiar-texto').hidden = true;
    estado.filtros.texto = '';
    construirFichas();
    render();
  });

  $('hoja-filtro').addEventListener('input', pintarHoja);

  $('hoja').addEventListener('click', (ev) => {
    if (ev.target.hasAttribute('data-cerrar')) { cerrarHoja(); return; }
    const opcion = ev.target.closest('.hoja-opcion');
    if (!opcion) return;
    estado.filtros[estado.campoHoja] = opcion.dataset.valor || null;
    cerrarHoja();
    construirFichas();
    render();
  });

  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && !$('hoja').hidden) cerrarHoja();
  });

  $('resultados').addEventListener('click', async (ev) => {
    const boton = ev.target.closest('[data-copiar]');
    if (!boton) return;
    const t = estado.datos.tarifas.find((x) => String(x.id) === boton.dataset.copiar);
    if (!t) return;
    try {
      await navigator.clipboard.writeText(textoParaCopiar(t));
      aviso('Tarifa copiada');
    } catch (e) {
      aviso('No se pudo copiar');
    }
  });

  window.addEventListener('online', () => sincronizar());
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && estado.clave) sincronizar();
  });
}

async function iniciar() {
  conectarEventos();

  if (!window.isSecureContext || !crypto.subtle) {
    $('pantalla-clave').hidden = false;
    $('clave-error').textContent =
      'Abra la app por https (o localhost). El navegador no permite descifrar en conexiones no seguras.';
    $('clave-error').hidden = false;
    $('form-clave').hidden = true;
    return;
  }

  const clave = localStorage.getItem(LS_CLAVE);
  if (!clave) { pedirClave(); return; }

  estado.clave = clave;
  entrarApp();

  const guardado = localStorage.getItem(LS_DATOS);
  if (guardado) {
    try {
      aplicarDatos(JSON.parse(guardado));
      mostrarEstado('', 'Buscando tarifas nuevas...');
    } catch (e) {
      localStorage.removeItem(LS_DATOS);
    }
  } else {
    mostrarEstado('', 'Cargando tarifas...');
  }

  await sincronizar();

  if (!estado.datos) {
    pedirClave('No se pudieron cargar las tarifas. Verifique la conexión y reintente.');
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}

iniciar();
