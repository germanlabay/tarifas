# Dejar la app en internet (una sola vez)

Hasta que se haga esto, `PUBLICAR.bat` genera el archivo pero no lo sube: la app
solo se puede probar en esta PC con `PROBAR-EN-ESTA-PC.bat`.

Usamos **GitHub Pages**: gratis, sin vencimiento, con https (obligatorio para
que el celular pueda descifrar las tarifas) y queda historial de cada cambio de
tarifas, que sirve para saber qué valor regía tal día.

Son unos 15 minutos, **una sola vez**. Después el operador solo usa
`PUBLICAR.bat`.

---

## 1. Cuenta de GitHub

Crear una en <https://github.com/signup> si no hay. Conviene una cuenta de la
empresa, no personal: el día que la persona se va, la app sigue.

Anotar el **nombre de usuario**; forma parte de la URL final.

---

## 2. Crear el repositorio

En <https://github.com/new>:

- **Repository name:** `tarifas`
- **Public** ← sí, público
- **No** tildar "Add a README file"
- Botón **Create repository**

> **¿Público no expone las tarifas?** No. Lo que se sube es
> `docs\datos\tarifas.json`, **cifrado con la clave de acceso**. Sin la clave es
> ruido. El Excel, que sí tiene la clave en texto plano, está excluido por
> `.gitignore` y nunca se sube.
>
> GitHub Pages en repositorios privados requiere plan pago; por eso público +
> cifrado.

---

## 3. Preparar la carpeta

Abrir **PowerShell** en `C:\Users\usuario\MarblauTarifas` (clic derecho en la
carpeta → *Abrir en Terminal*) y pegar, cambiando el nombre y el mail:

```powershell
git config --global user.name "Operador MARBLAU"
git config --global user.email "marblausa@gmail.com"
```

Después, cambiando `USUARIO` por el nombre de usuario de GitHub:

```powershell
git init
git add .
git commit -m "App de tarifas"
git branch -M main
git remote add origin https://github.com/USUARIO/tarifas.git
git push -u origin main
```

En el `git push` se abre una ventana del navegador para iniciar sesión en
GitHub. Es normal y pasa una sola vez: Windows guarda la credencial.

**Control:** antes del `push`, `git status` **no** tiene que mencionar
`tarifas.xlsx` ni `venv`. Si los menciona, falta el `.gitignore`; no seguir.

---

## 4. Encender GitHub Pages

En el repositorio, **Settings** → **Pages** (menú izquierdo):

- **Source:** `Deploy from a branch`
- **Branch:** `main` — y en la carpeta de al lado: **`/docs`**
- **Save**

Esperar un minuto y recargar. Arriba aparece la dirección:

```
https://USUARIO.github.io/tarifas/
```

Esa es **la URL que se reparte**. Abrirla en el celular, escribir la clave y
agregarla a la pantalla principal (ver `LEEME.md`).

---

## 5. Probar el circuito completo

1. Cambiar una tarifa en `datos\tarifas.xlsx` y guardar.
2. Doble clic en `PUBLICAR.bat`.
3. Tiene que terminar con **`Publicado en internet.`**
4. En el celular, abrir la app y tocar el botón de refrescar: aparece el cartel
   *Tarifas actualizadas* con el valor nuevo.

Si el paso 3 dice *"la carpeta no es un repositorio git"* o *"no tiene remoto
origin"*, algo del paso 3 anterior quedó a medias.

GitHub tarda entre 20 segundos y 2 minutos en servir el cambio.

---

## Repartir la app

Mandar por WhatsApp estas dos cosas:

> Tarifas de transporte: https://USUARIO.github.io/tarifas/
> Clave: (la que figura en CONFIG)
>
> Al abrirla, agregala a la pantalla principal:
> Android → menú ⋮ → Agregar a pantalla principal
> iPhone → compartir → Agregar a inicio

Conviene mandar la clave por separado del enlace.

---

## Mantenimiento

- **Sacarle el acceso a alguien:** cambiar `CLAVE_ACCESO` en la hoja CONFIG,
  publicar, y pasarle la clave nueva solo a quien corresponde.
- **Cambiar de PC:** copiar la carpeta entera (sin `venv`), instalar Python,
  crear el entorno de nuevo y clonar el repositorio. El Excel se copia a mano,
  porque no está en el repositorio.
- **Respaldo del Excel:** copiarlo a Google Drive. Es el único archivo que no se
  puede regenerar.
- **Historial:** en GitHub, pestaña *Commits*, está cada publicación con fecha y
  hora. Para ver qué tarifas regían tal día hay que descifrar ese `tarifas.json`
  con la clave que estaba vigente en ese momento.

---

## Alternativas

Si GitHub no sirve por política interna, la app funciona en **cualquier hosting
estático con https**: subir el contenido de `docs\` por FTP o al panel que sea.
`PUBLICAR.bat` seguirá generando `docs\datos\tarifas.json`, pero la subida habrá
que hacerla con la herramienta de ese hosting.
