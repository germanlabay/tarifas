/* Tarifas de Transporte - logica de la app.
 *
 * Los datos llegan en datos/tarifas.json, cifrados con AES-256-GCM.
 * La clave que escribe el usuario deriva la llave con PBKDF2 y descifra en el
 * telefono: el servidor nunca ve la clave y el archivo publicado es ilegible
 * sin ella. Una vez descifrado se guarda localmente para funcionar sin señal.
 *
 * Modelo: una tarifa es transportista x zona de carga x tamaño x modalidad
 * (ida / ida y vuelta). El destino es el mismo para toda la grilla y viaja en
 * datos.destino. Los recargos (GENSET, CDA, vacios) son del transportista y se
 * muestran al lado de la tarifa, sin sumarse: quien cotiza decide cual aplica.
 */

const RUTA_DATOS = 'datos/tarifas.json';
const LS_CLAVE = 'tarifas.clave';
const LS_DATOS = 'tarifas.datos';

const $ = (id) => document.getElementById(id);

const estado = {
  datos: null,
  clave: null,
  filtros: { zona: null, t: null, tam: null, mod: null, texto: '' },
  campoHoja: null,
};

/* ================= utilidades ================= */

const sinAcentos = (t) =>
  String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();

const escapar = (t) =>
  String(t == null ? '' : t).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function deB64(b64) {
  const bruto = atob(b64);
  const bytes = new Uint8Array(bruto.length);
  for (let i = 0; i < bruto.length; i++) bytes[i] = bruto.charCodeAt(i);
  return bytes;
}

function formatoMonto(n) {
  const moneda = (estado.datos && estado.datos.moneda) || 'USD';
  const simbolo = moneda === 'USD' ? 'U$S' : '$';
  return simbolo + ' ' + n.toLocaleString('es-AR', {
    minimumFractionDigits: n % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

// "20" -> "20'" pero "40 HCR" se deja como esta: la comilla de pies solo va
// cuando el tamaño es un numero pelado.
const etiquetaTam = (v) => (/^\d+$/.test(v) ? v + "'" : v);

const textoModalidad = (id) => {
  const m = estado.datos && estado.datos.modalidades.find((x) => x.id === id);
  return m ? m.texto : id;
};

function fechaCorta(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00');
  return isNaN(d) ? iso : d.toLocaleDateString('es-AR');
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

const resumen = (d) => `${d.tarifas.length} tarifas · actualizado ${haceCuanto(d.generado)}`;

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

  mostrarEstado('', resumen(datos));
  construirFichas();
  render();

  if (avisar && anterior && anterior !== datos.generado) aviso('Tarifas actualizadas');
}

async function sincronizar({ manual } = {}) {
  const boton = $('boton-refrescar');
  boton.classList.add('girando');
  try {
    const sobre = await bajarSobre();

    if (estado.datos && sobre.generado === estado.datos.generado) {
      mostrarEstado('', resumen(estado.datos));
      if (manual) aviso('Ya tiene las tarifas al día');
      return;
    }

    const datos = await descifrar(sobre, estado.clave);
    aplicarDatos(datos, { avisar: true });
  } catch (err) {
    if (err && err.name === 'OperationError') {
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
  if (omitir !== 'zona' && f.zona && t.zona !== f.zona) return false;
  if (omitir !== 't' && f.t && t.t !== f.t) return false;
  if (omitir !== 'tam' && f.tam && t.tam !== f.tam) return false;
  if (omitir !== 'mod' && f.mod && t.mod !== f.mod) return false;
  if (omitir !== 'texto' && f.texto) {
    const palabras = sinAcentos(f.texto).split(/\s+/).filter(Boolean);
    if (!palabras.every((p) => t.b.includes(p))) return false;
  }
  return true;
}

const filtradas = () => (estado.datos ? estado.datos.tarifas.filter((t) => pasaParcial(t)) : []);

function opcionesDe(campo) {
  const cuentas = new Map();
  for (const t of estado.datos.tarifas) {
    if (!pasaParcial(t, campo)) continue;
    cuentas.set(t[campo], (cuentas.get(t[campo]) || 0) + 1);
  }
  const orden = campo === 'zona' ? estado.datos.zonas : null;
  const lista = [...cuentas.entries()].map(([valor, cuenta]) => ({ valor, cuenta }));
  if (orden) {
    lista.sort((a, b) => orden.indexOf(a.valor) - orden.indexOf(b.valor));
  } else {
    lista.sort((a, b) => a.valor.localeCompare(b.valor, 'es'));
  }
  return lista;
}

function hayFiltros() {
  const f = estado.filtros;
  return !!(f.zona || f.t || f.tam || f.mod || f.texto);
}

function fijar(campo, valor) {
  estado.filtros[campo] = estado.filtros[campo] === valor ? null : valor;
  construirFichas();
  render();
}

/* ================= pintado ================= */

function construirFichas() {
  if (!estado.datos) return;

  const grupos = [
    ['tam', $('fichas-tam'), estado.datos.tamanos.map((v) => ({ v, texto: etiquetaTam(v) }))],
    ['mod', $('fichas-mod'), estado.datos.modalidades.map((m) => ({ v: m.id, texto: m.texto }))],
  ];

  for (const [campo, contenedor, opciones] of grupos) {
    const disponibles = new Set(opcionesDe(campo).map((o) => o.valor));
    contenedor.innerHTML = '';
    for (const { v, texto } of opciones) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ficha';
      b.textContent = texto;
      b.setAttribute('aria-pressed', String(estado.filtros[campo] === v));
      b.disabled = !disponibles.has(v) && estado.filtros[campo] !== v;
      b.addEventListener('click', () => fijar(campo, v));
      contenedor.appendChild(b);
    }
  }

  for (const [campo, boton, salida, vacio] of [
    ['zona', $('sel-zona'), $('val-zona'), 'Elegir zona'],
    ['t', $('sel-transportista'), $('val-transportista'), 'Todos'],
  ]) {
    const valor = estado.filtros[campo];
    salida.textContent = valor || vacio;
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

function recargosHTML(ficha) {
  if (!ficha || !ficha.recargos) return '';
  const partes = Object.entries(ficha.recargos)
    .map(([k, v]) => `<span class="recargo"><span class="recargo-n">${escapar(k)}</span>
      ${escapar(formatoMonto(v))}</span>`);
  if (!partes.length) return '';
  return `<div class="recargos"><span class="recargos-titulo">Recargos aparte</span>
    <div class="recargos-lista">${partes.join('')}</div></div>`;
}

function contactoHTML(ficha) {
  if (!ficha || !ficha.contactos || !ficha.contactos.length) return '';
  const c = ficha.contactos[0];
  const trozos = [];
  if (c.nombre) trozos.push(escapar(c.nombre));
  if (c.tel) {
    const limpio = c.tel.replace(/[^\d+]/g, '');
    trozos.push(`<a href="tel:${escapar(limpio)}">${escapar(c.tel)}</a>`);
  }
  if (c.mail) trozos.push(`<a href="mailto:${escapar(c.mail)}">${escapar(c.mail)}</a>`);
  return trozos.length ? `<p class="tarjeta-obs">${trozos.join(' · ')}</p>` : '';
}

function tarjetaHTML(t, posicion) {
  const ficha = estado.datos.transportistas[t.t] || {};
  const etiquetas = [
    `<span class="etiqueta">${escapar(etiquetaTam(t.tam))} · ${escapar(textoModalidad(t.mod))}</span>`,
    ficha.fecha ? `<span class="etiqueta">Cotizado ${escapar(fechaCorta(ficha.fecha))}</span>` : '',
    ficha.chilena ? `<span class="etiqueta">CL: ${escapar(ficha.chilena)}</span>` : '',
  ].filter(Boolean).join('');

  return `
    <article class="tarjeta${posicion === 0 ? ' mejor' : ''}">
      <div class="tarjeta-arriba">
        <div class="tarjeta-ruta">
          <div class="tarjeta-tramo">
            <span class="punta">${escapar(t.t)}</span>
            <span class="punta sub"><span class="flecha" aria-hidden="true">&rarr;</span>${escapar(t.zona)} a ${escapar(estado.datos.destino)}</span>
          </div>
        </div>
        <div class="tarjeta-precio">
          ${posicion === 0 ? '<div class="insignia">más barato</div>' : ''}
          <div class="precio-monto">${escapar(formatoMonto(t.tarifa))}</div>
          <div class="precio-moneda">${escapar(estado.datos.moneda)}</div>
        </div>
      </div>
      <div class="etiquetas">${etiquetas}</div>
      ${recargosHTML(ficha)}
      ${contactoHTML(ficha)}
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
  const ficha = estado.datos.transportistas[t.t] || {};
  const partes = [
    `${t.zona} a ${estado.datos.destino}`,
    `Contenedor ${etiquetaTam(t.tam)} - ${textoModalidad(t.mod)}`,
    `Transportista: ${t.t}`,
    `Tarifa: ${formatoMonto(t.tarifa)} ${estado.datos.moneda}`,
  ];
  if (ficha.recargos && Object.keys(ficha.recargos).length) {
    partes.push('Recargos aparte: ' +
      Object.entries(ficha.recargos).map(([k, v]) => `${k} ${formatoMonto(v)}`).join(', '));
  }
  if (ficha.fecha) partes.push(`Cotizado el ${fechaCorta(ficha.fecha)}`);
  return partes.join('\n');
}

function render() {
  const caja = $('resultados');
  const cuenta = $('resultados-cuenta');

  if (!estado.datos) { caja.innerHTML = ''; return; }

  if (!hayFiltros()) {
    cuenta.textContent = `${estado.datos.tarifas.length} tarifas`;
    caja.innerHTML = `<div class="vacio-mensaje">${iconoVacio()}
      <p>Elegí la <strong>zona de carga</strong>, el contenedor y la modalidad.<br>
      Te muestro todos los transportistas, del más barato al más caro.</p></div>`;
    return;
  }

  const lista = filtradas();
  cuenta.textContent = lista.length === 1 ? '1 tarifa' : `${lista.length} tarifas`;

  if (!lista.length) {
    caja.innerHTML = `<div class="vacio-mensaje">${iconoVacio()}
      <p>Ningún transportista tiene esa combinación cotizada.<br>Probá quitando un filtro.</p></div>`;
    return;
  }

  // Ordenar por precio solo tiene sentido cuando se compara lo mismo; si no,
  // se agrupa por zona y tamaño para no mezclar peras con manzanas.
  const comparable = !!(estado.filtros.zona && estado.filtros.tam && estado.filtros.mod);
  if (comparable) {
    lista.sort((a, b) => a.tarifa - b.tarifa);
  } else {
    const orden = estado.datos.zonas;
    lista.sort((a, b) =>
      orden.indexOf(a.zona) - orden.indexOf(b.zona) ||
      a.tam.localeCompare(b.tam, 'es') ||
      a.mod.localeCompare(b.mod, 'es') ||
      a.tarifa - b.tarifa);
  }

  caja.innerHTML = lista.map((t, i) => tarjetaHTML(t, comparable ? i : -1)).join('');
}

/* ================= hoja de seleccion ================= */

const TITULOS_HOJA = { zona: 'Zona de carga', t: 'Transportista' };

function abrirHoja(campo) {
  estado.campoHoja = campo;
  $('hoja-titulo').textContent = TITULOS_HOJA[campo];
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

  lista.innerHTML = [
    `<li><button class="hoja-opcion" data-valor="" aria-selected="${!actual}">
       <span>${campo === 'zona' ? 'Todas las zonas' : 'Todos'}</span>${!actual ? tilde : ''}</button></li>`,
    ...opciones.map((o) => `
      <li><button class="hoja-opcion" data-valor="${escapar(o.valor)}" aria-selected="${actual === o.valor}">
        <span>${escapar(o.valor)}</span>
        ${actual === o.valor ? tilde : `<span class="cuenta">${o.cuenta}</span>`}
      </button></li>`),
  ].join('');
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

function limpiarFiltros() {
  estado.filtros = { zona: null, t: null, tam: null, mod: null, texto: '' };
  $('campo-texto').value = '';
  $('limpiar-texto').hidden = true;
  construirFichas();
  render();
}

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
  $('sel-zona').addEventListener('click', () => abrirHoja('zona'));
  $('sel-transportista').addEventListener('click', () => abrirHoja('t'));
  $('boton-limpiar').addEventListener('click', limpiarFiltros);

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
      const d = JSON.parse(guardado);
      if (d && Array.isArray(d.tarifas) && d.zonas) {
        aplicarDatos(d);
        mostrarEstado('', 'Buscando tarifas nuevas...');
      } else {
        localStorage.removeItem(LS_DATOS);   // formato viejo
      }
    } catch (e) {
      localStorage.removeItem(LS_DATOS);
    }
  }
  if (!estado.datos) mostrarEstado('', 'Cargando tarifas...');

  await sincronizar();

  if (!estado.datos) {
    pedirClave('No se pudieron cargar las tarifas. Verifique la conexión y reintente.');
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}

iniciar();
