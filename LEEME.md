# Tarifas de Transporte

App para celular que consulta tarifas de transporte terrestre por **origen,
destino, tipo y tamaño de contenedor**. Los datos salen de una planilla Excel
que mantiene un operador; los celulares se actualizan solos.

---

## Las dos personas que usan esto

**El operador** edita `\\PC-02\Compartido\tarifas.xlsx` y **guarda**. Nada
más: esta PC publica sola cada 10 minutos.

**Los usuarios** abren la app en el celular, escriben la clave una sola vez y
consultan. No instalan nada desde una tienda ni actualizan nada a mano.

---

## Cómo se actualiza una tarifa

1. Abrir la planilla: **`\\PC-02\Compartido\tarifas.xlsx`**.
2. Cambiar, agregar o borrar filas en la hoja **TARIFAS**.
3. **Guardar** el Excel (con guardar alcanza; no hace falta cerrarlo).

Y listo. Dentro de los 10 minutos siguientes, esta PC publica sola.

Para no esperar, doble clic en **`PUBLICAR.bat`**, que hace lo mismo al
instante y muestra el detalle en pantalla.

La ventana negra muestra el resultado:

- **Filas validas: N** y *Listo* → publicado.
- **"Las tarifas no cambiaron"** → ya estaba todo publicado. Pasa si se ejecuta
  dos veces seguidas, o si el Excel se guardó sin cambios reales.
- **Avisos** → se publicó igual, pero conviene mirarlos (tarifas vencidas,
  rutas repetidas, tipos raros).
- **ERRORES** → **no se publicó nada**. Dice número de fila y problema.
  Se corrige el Excel y se vuelve a ejecutar.

Los celulares toman las tarifas nuevas al abrir la app, o al tocar el botón
de refrescar arriba a la derecha.

---

## Dónde vive la planilla

En el recurso compartido **`\\PC-02\Compartido\tarifas.xlsx`**, para que la
mantenga el operador desde su propia PC sin depender de esta.

La ruta está en **`planilla.txt`**, en la carpeta del proyecto: una sola línea
con la ruta completa. Si la planilla se muda, se cambia ahí y nada más. Si se
borra ese archivo, `PUBLICAR.bat` usa la copia local
`datos\tarifas-ejemplo.xlsx`, que es la plantilla vacia de referencia.

> No conviene que esa copia se vuelva a llamar `tarifas.xlsx`: Excel no
> admite dos libros abiertos con el mismo nombre y abre el segundo en
> **solo lectura**, sin decir por que.

`PUBLICAR.bat` solo **lee** la planilla, así que puede estar abierta en Excel
mientras tanto — pero lee la última versión **guardada**.

Si PC-02 está apagada o fuera de la red, el publicador lo dice con ese texto y
no toca nada de lo que ya estaba publicado.

> `planilla.txt` no se sube al repositorio: no tiene sentido publicar los
> nombres de las máquinas de la oficina.

## La planilla

Hoja **TARIFAS**, una fila por tarifa:

| Columna | Obligatoria | Detalle |
|---|---|---|
| ORIGEN | sí | Ciudad o terminal |
| DESTINO | sí | Ciudad o terminal |
| TAMANO | sí | `20` o `40` |
| TIPO | sí | DRY, HC, REEFER, OPEN TOP, FLAT RACK, TANK |
| TARIFA | sí | Número puro: `1450`, no `U$S 1.450` |
| MONEDA | sí | `USD` o `ARS` |
| TRANSPORTISTA | no | Se muestra como etiqueta |
| VIGENCIA DESDE | no | Fecha |
| VIGENCIA HASTA | no | Vacío = sin vencimiento |
| OBSERVACIONES | no | Texto libre, aparece en la tarjeta |

No cambiar los nombres ni el orden de la fila 1. Mayúsculas y acentos no
importan para buscar: `San Rafael` y `SAN RAFAEL` son lo mismo.

Hoja **CONFIG**: **ya no se usa.** El título, el nombre de la empresa y la
clave de acceso salen de `config.txt`, en la carpeta del proyecto. Si quedó
una clave escrita en esa hoja, `PUBLICAR.bat` avisa y la ignora: conviene
borrar esa celda, porque el Excel está en un compartido que ve toda la
oficina.

---

## La publicación automática

Una tarea programada de Windows, **`MARBLAU - Publicar tarifas`**, corre cada
10 minutos en esta PC y publica si hay algo nuevo. No abre ninguna ventana.

Si no cambió nada, no hace nada: no sube commits vacíos ni molesta a los
celulares.

### Corre solo con la sesión iniciada

Necesita llegar a PC-02 y a GitHub, y una tarea configurada como "aunque el
usuario no haya iniciado sesión" **no tiene credenciales de red**. Por eso
corre solo mientras haya alguien con sesión abierta en esta PC. Si la PC está
apagada o con la sesión cerrada, las tarifas esperan.

### Cómo saber si está funcionando

Dos archivos en `datos\`:

| Archivo | Qué dice |
|---|---|
| `estado.txt` | La hora de la última corrida y si publicó. Se reescribe **siempre**, aunque no haya cambios. |
| `publicacion.log` | Solo las publicaciones reales y los errores, con el detalle completo. |

Si la fecha de `estado.txt` quedó vieja, la tarea no está corriendo. Si hay
líneas con `FALLO` en el registro, ahí está el motivo.

> El registro se recorta solo cuando pasa de 200 KB.

### Apagarla o cambiarle el intervalo

Desde PowerShell, en esta PC:

```powershell
# apagarla
Disable-ScheduledTask -TaskName "MARBLAU - Publicar tarifas"

# volver a encenderla
Enable-ScheduledTask -TaskName "MARBLAU - Publicar tarifas"

# borrarla del todo
Unregister-ScheduledTask -TaskName "MARBLAU - Publicar tarifas" -Confirm:$false
```

También aparece en el **Programador de tareas** de Windows, con ese nombre.
Con la tarea apagada, `PUBLICAR.bat` sigue funcionando a mano.

---

## La clave de acceso

Está en **`config.txt`**, en la carpeta del proyecto:

```
CLAVE_ACCESO=<la clave que use la gente>
```

Está acá y no en el Excel a propósito: el Excel vive en un compartido que ve
toda la oficina, y la clave no tiene por qué estar ahí.

> **Nunca escribir la clave real en este archivo ni en ningún otro del
> repositorio**, que es público. `config.txt` y `planilla.txt` están excluidos
> justamente por eso. Una clave que entra al historial de git queda expuesta
> para siempre, aunque después se borre.

Las tarifas se publican **cifradas con esa clave** (AES-256). El archivo que
queda en internet es ilegible sin la clave, así que no hay problema en que el
repositorio sea público.

Si cambia la clave y vuelve a publicar, los usuarios ven un cartel pidiendo la
clave nueva. Es la forma de sacarle el acceso a alguien: cambiar la clave,
publicar y repartir la nueva al resto.

> **Nunca subir el Excel al repositorio**, tenga clave o no: son las tarifas de
> la empresa. Por eso `.gitignore` excluye `/datos/`.

---

## Probar sin publicar

Doble clic en **`PROBAR-EN-ESTA-PC.bat`**: abre la app en el navegador de esta
PC contra los datos ya generados. Dejar la ventana negra abierta mientras se
usa; cerrarla corta el servidor.

Sirve para revisar cómo quedó un cambio antes de que lo vean los demás —
siempre que se haya ejecutado `PUBLICAR.bat` primero.

---

## Instalar la app en el celular

Abrir **https://germanlabay.github.io/tarifas/** y:

- **Android / Chrome:** menú ⋮ → *Agregar a pantalla principal*.
- **iPhone / Safari:** botón compartir → *Agregar a inicio*.

Queda con ícono propio, pantalla completa y sin barra del navegador. Después de
la primera vez funciona **sin señal**, mostrando las últimas tarifas bajadas; el
encabezado avisa de cuándo son.

---

## Estructura

```
MarblauTarifas\
├─ PUBLICAR.bat              ← el operador usa esto
├─ PROBAR-EN-ESTA-PC.bat     ← previsualizar en esta PC
├─ config.txt                ← clave de acceso y textos (NO se versiona)
├─ planilla.txt              ← donde esta el Excel (hoy, en PC-02)
├─ datos\
│  ├─ tarifas-ejemplo.xlsx   ← plantilla de referencia; respaldo si falla la red
│  ├─ estado.txt             ← ultima corrida automatica
│  ├─ publicacion.log        ← publicaciones y errores
│  └─ .huella                ← para no republicar si nada cambio
├─ docs\                     ← la app publicada (GitHub Pages exige este nombre)
│  ├─ index.html, app.js, estilos.css, sw.js, manifest, iconos
│  └─ datos\tarifas.json     ← generado y cifrado por PUBLICAR.bat
├─ scripts\
│  ├─ publicar.py            ← valida, cifra y sube
│  ├─ publicar_auto.py       ← lo mismo, sin ventana, para la tarea programada
│  ├─ crear_plantilla.py     ← regenera el Excel desde cero
│  ├─ crear_iconos.py        ← regenera los iconos
│  └─ tarifario.py           ← sin usar: lee el tarifario matriz de Chile
└─ venv\                     ← Python local (openpyxl, cryptography, pillow)
```

---

## Si algo falla

| Síntoma | Qué pasa |
|---|---|
| `PUBLICAR.bat` dice ERRORES | Hay filas mal cargadas. Dice cuáles. No se publicó nada; el celular sigue con las tarifas anteriores. |
| La app pide la clave de nuevo | Cambió la `CLAVE_ACCESO` de `config.txt`. Repartir la nueva. |
| "Clave incorrecta" | La clave no coincide con la de la última publicación. |
| "Sin conexión" en el encabezado | El celular no tiene datos. Muestra lo último bajado y dice de cuándo es. |
| El celular no ve el cambio | Mirar `datos\estado.txt`: dice cuándo corrió la publicación automática y si publicó. Después tocar el botón de refrescar en la app. |
| `estado.txt` con fecha vieja | La tarea programada no está corriendo: sesión cerrada en esta PC, o la tarea deshabilitada. |
| Tarifa marcada como vencida | La `VIGENCIA HASTA` de esa fila ya pasó. Actualizarla o vaciarla. |

---

## Detalles técnicos

- La app es una **PWA**: HTML, CSS y JavaScript sin dependencias externas, sin
  servidor propio y sin base de datos.
- `publicar.py` lee el Excel con `openpyxl`, valida fila por fila, arma un JSON
  y lo cifra con **AES-256-GCM**, con la llave derivada de la clave por
  **PBKDF2-SHA256** (210.000 iteraciones). El descifrado ocurre en el celular;
  la clave nunca viaja al servidor.
- El service worker cachea el armazón de la app, **no** las tarifas: estas se
  piden siempre a la red y la última copia descifrada queda en el celular. Así
  la app nunca muestra una tarifa vieja creyendo que es la actual.
- Requiere **https** (o `localhost`): el navegador no permite descifrar en
  conexiones inseguras. GitHub Pages ya sirve por https.

---

## El tarifario matriz de Chile

Hubo una version de esta app que leia directamente
`\\PC-02\Compartido\TARIFAS TTE TERRESTRE  01-04-26.xlsx`: la matriz de 8
zonas de carga contra Chile, con 10 transportistas, modalidad ida / ida y
vuelta y los recargos de cada uno. Mostraba 388 tarifas reales sin cargar nada
a mano.

Se dejo de lado por pedido de la direccion, para volver a la busqueda por
origen y destino, que cubre cualquier destino y no solo Chile.

El lector sigue en `scripts\tarifario.py` y la ruta esta anotada en
`planilla.txt`. Si alguna vez conviene volver a leer esa planilla, no hay que
escribirlo de nuevo: esta en el historial de git, en el commit
`a909a2e`.
