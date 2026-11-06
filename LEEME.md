# Tarifas de Transporte

App para celular que consulta el tarifario de transporte terrestre a Chile.
Se elige **zona de carga, contenedor y modalidad**, y muestra **todos los
transportistas ordenados del más barato al más caro**.

Los datos salen del Excel que ya mantiene la empresa. Nadie carga nada dos
veces.

---

## Las dos personas que usan esto

**El operador** edita el tarifario como siempre y hace doble clic en
`PUBLICAR.bat`. Nada más.

**Los usuarios** abren la app en el celular, escriben la clave una sola vez y
consultan. No instalan nada desde una tienda ni actualizan nada a mano.

---

## Cómo se actualiza el tarifario

1. Abrir **`\\PC-02\Compartido\TARIFAS TTE TERRESTRE  01-04-26.xlsx`**.
2. Editar la hoja **`TARIFARIO DESDE EL <fecha>`** como siempre.
3. **Guardar** (con guardar alcanza; no hace falta cerrar el Excel).
4. Doble clic en **`PUBLICAR.bat`**.

La ventana negra muestra el resultado:

- **Tarifas: N** y *Listo* → publicado.
- **"Las tarifas no cambiaron"** → ya estaba todo publicado.
- **Avisos** → se publicó igual, pero conviene leerlos (ver más abajo).
- **ERRORES** → **no se publicó nada**; el celular sigue con lo anterior.

Los celulares toman las tarifas nuevas al abrir la app, o al tocar el botón de
refrescar arriba a la derecha.

> Cuando cambie el **nombre del archivo** (lleva la fecha), hay que actualizar
> esa línea en `planilla.txt`. La **hoja** en cambio se detecta sola: se usa la
> `TARIFARIO DESDE EL <fecha>` más reciente.

---

## Qué lee de la planilla, y qué no

**Sí:** la grilla de cada transportista — 8 zonas × 3 contenedores (20, 40,
40 HCR) × 2 modalidades (OW = ida, RT = ida y vuelta), más sus recargos
(GENSET, CDA, VACÍO 20, VACÍO 40) y su ficha: fecha de cotización, ATA, empresa
chilena y contactos.

**No:** la sección **COTIZACIONES PUNTUALES** del final de la hoja. Mezcla
unidades (contenedor, big bag, pallets, tambores), monedas y notas como
"MAS IVA" en las mismas celdas. Leerla automáticamente daría importes
equivocados, así que se consulta en el Excel como hasta ahora.

### Los recargos se muestran, no se suman

La app muestra la tarifa del flete y, al lado, los recargos de ese
transportista. **No los suma**: quién cotiza decide cuáles aplican.

### Celdas que la app descarta a propósito

Cuando un transportista no cotizó una zona, la celda a veces trae igual la
**suma de sus propios recargos** (por ejemplo GENSET + CDA), porque quedó la
fórmula. Publicar eso haría que aparezca como el más barato por lejos: el peor
error posible acá.

La app descarta un valor solo si cumple **las dos condiciones**: que sea
exactamente una suma de recargos de ese mismo transportista, y que además esté
por debajo de la mitad de lo que cobran los demás en esa misma zona, contenedor
y modalidad. Cada descarte aparece en los avisos de `PUBLICAR.bat`, con nombre
y motivo, para poder corregir el Excel si hace falta.

### La moneda

La grilla no dice en ninguna celda en qué moneda está: es **USD**, confirmado
por la dirección el 06/11/2026, y así la muestra la app. Está fijo en `MONEDA`,
en `scripts\tarifario.py`.

Si alguna vez se cotizara en pesos, **no alcanza con cambiar ese valor**:
convivirían las dos monedas en la misma grilla y habría que leer la moneda fila
por fila. Conviene avisar antes de empezar a cargar tarifas en pesos ahí.

---

## La clave de acceso

Está en **`config.txt`**, en la carpeta del proyecto, no en el Excel:

```
CLAVE_ACCESO=<la clave que use la gente>
```

Está acá a propósito: el Excel vive en un compartido que ve toda la oficina, y
la clave no tiene por qué estar ahí.

> **Nunca escribir la clave real en este archivo ni en ningún otro del
> repositorio**, que es público. `config.txt` está excluido justamente por eso.

Las tarifas se publican **cifradas con esa clave** (AES-256). El archivo que
queda en internet es ilegible sin ella, así que no hay problema en que el
repositorio sea público.

Si cambia la clave y vuelve a publicar, los usuarios ven un cartel pidiendo la
clave nueva. Es la forma de sacarle el acceso a alguien.

---

## Probar sin publicar

Doble clic en **`PROBAR-EN-ESTA-PC.bat`**: abre la app en el navegador de esta
PC contra los datos ya generados. Dejar la ventana negra abierta mientras se
usa.

---

## Instalar la app en el celular

Abrir **https://germanlabay.github.io/tarifas/** y:

- **Android / Chrome:** menú ⋮ → *Agregar a pantalla principal*.
- **iPhone / Safari:** botón compartir → *Agregar a inicio*.

Queda con ícono propio y pantalla completa. Después de la primera vez funciona
**sin señal**, mostrando las últimas tarifas bajadas; el encabezado avisa de
cuándo son.

---

## Estructura

```
MarblauTarifas\
├─ PUBLICAR.bat              ← el operador usa esto
├─ PROBAR-EN-ESTA-PC.bat     ← previsualizar en esta PC
├─ config.txt                ← clave de acceso y textos (NO se versiona)
├─ planilla.txt              ← ruta al Excel (NO se versiona)
├─ docs\                     ← la app publicada
│  ├─ index.html, app.js, estilos.css, sw.js, manifest, iconos
│  └─ datos\tarifas.json     ← generado y cifrado por PUBLICAR.bat
├─ scripts\
│  ├─ publicar.py            ← valida, cifra y sube
│  └─ tarifario.py           ← entiende la planilla matriz
└─ venv\                     ← Python local
```

---

## Si algo falla

| Síntoma | Qué pasa |
|---|---|
| "no se llega a la planilla en la red" | PC-02 apagada o fuera de red. No se publicó nada; el celular sigue con lo anterior. |
| "no se encontró una hoja de tarifario" | Cambió el nombre de la hoja. Se puede fijar a mano con `HOJA=` en `config.txt`. |
| La app pide la clave de nuevo | Cambió la `CLAVE_ACCESO`. Repartir la nueva. |
| "Sin conexión" en el encabezado | El celular no tiene datos. Muestra lo último bajado y dice de cuándo es. |
| El celular no ve el cambio | Verificar que `PUBLICAR.bat` terminó con *Publicado en internet*, y mirar la pestaña **Actions** del repositorio. |
| Falta un transportista | No tiene ninguna tarifa cargada en la hoja, o su bloque no tiene nombre en la columna B. Sale en los avisos. |

---

## Detalles técnicos

- La app es una **PWA**: HTML, CSS y JavaScript sin dependencias externas, sin
  servidor propio y sin base de datos.
- `tarifario.py` entiende la planilla matriz: un bloque por transportista, con
  las zonas en columnas de a tres (20 / 40 / 40 HCR) y las filas OW, RT,
  GENSET, CDA, VACIO 20 y VACIO 40.
- `publicar.py` arma un JSON y lo cifra con **AES-256-GCM**, con la llave
  derivada de la clave por **PBKDF2-SHA256** (210.000 iteraciones). El
  descifrado ocurre en el celular; la clave nunca viaja al servidor.
- El service worker cachea el armazón de la app, **no** las tarifas: estas se
  piden siempre a la red y la última copia descifrada queda en el celular.
- Requiere **https** (o `localhost`): el navegador no permite descifrar en
  conexiones inseguras.
