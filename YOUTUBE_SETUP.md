# 📺 Configuración de Subida Automática a YouTube (Dinámica con Balanceo de Cuota)

Este sistema sube tus programas directamente desde GitHub Actions a tu **único canal de YouTube** en estado **Privado**, para que tú solo abras **YouTube Studio** en tu navegador, recortes los minutos exactos de inicio en el Editor de YouTube y los publiques sin descargar archivos pesados a tu PC.

---

## ¿Por qué 1 o 2 proyectos de Google Cloud?

* **Cuota gratis de YouTube API:** Cada proyecto de Google Cloud te regala **10,000 unidades diarias** (= máximo **6 videos por día**).
* **Lunes a Jueves y Domingos:** Como solo grabas **2 radios**, el **Proyecto 1** (`YT_TOKEN_1`) cubre el 100% sin tocar nada más.
* **Viernes y Sábados (8–9 radios):** Al llegar al video #6 del día (o si el Proyecto 1 agota cuota), el script cambia **automáticamente** al **Proyecto 2** (`YT_TOKEN_2`), dándote **12 subidas diarias gratis** hacia el mismo canal de YouTube.

> **Importante:** Ambos proyectos pertenecen a tu misma cuenta de Google y se autorizan sobre tu **mismo canal de YouTube**.

---

## Pasos para generar `YT_TOKEN_1` (y opcionalmente `YT_TOKEN_2`)

### 1. Crear el Proyecto 1 en Google Cloud (3 minutos)
1. Entra a [console.cloud.google.com](https://console.cloud.google.com/).
2. Crea un proyecto nuevo llamado `radios-yt-1`.
3. Ve a **APIs y servicios > Biblioteca**, busca **YouTube Data API v3** y haz clic en **Habilitar**.
4. Ve a **APIs y servicios > Pantalla de consentimiento de OAuth**:
   * Elige **Externo** -> **Crear**.
   * Nombre de app: `Grabador Radios 1`, pon tu correo en soporte y desarrollador.
   * **⚠️ MUY IMPORTANTE (Para que no caduque cada 7 días):** Ve a **Público / Audience** y haz clic en **"Publicar aplicación" (Publish App)** para pasarla de *Testing* a **In Production**.
5. Ve a **Credenciales > Crear credenciales > ID de cliente de OAuth**:
   * Tipo: **Aplicación de escritorio (Desktop app)**.
   * Descarga el archivo JSON y guárdalo como `client_secret_1.json`.

### 2. Obtener el Token en tu PC (30 segundos)
Abre PowerShell en tu carpeta `cloud-recorder` y ejecuta:
```powershell
pip install google-auth-oauthlib google-api-python-client
python scripts/get_youtube_token.py "ruta\a\client_secret_1.json"
```
* Se abrirá tu navegador: inicia sesión con la cuenta de tu canal de YouTube y acepta los permisos (si sale aviso de "app no verificada", haz clic en *Configuración avanzada > Ir a Grabador Radios*).
* La consola imprimirá una línea JSON larga `{ "token": ... }`.
* Cópiala y guárdala en **GitHub > Settings > Secrets > Actions** con el nombre **`YT_TOKEN_1`**.

### 3. (Solo para Viernes y Sábados de 7+ videos) Repite para `YT_TOKEN_2`
* Crea un segundo proyecto `radios-yt-2` en Google Cloud Console, habilita **YouTube Data API v3**, publícalo en **In Production**, descarga `client_secret_2.json`, ejecuta `python scripts/get_youtube_token.py client_secret_2.json` y guárdalo en GitHub Secrets como **`YT_TOKEN_2`**.
* ¡Listo! El sistema usará `YT_TOKEN_1` de Lunes a Jueves y Domingos, y equilibrará automáticamente entre `YT_TOKEN_1` y `YT_TOKEN_2` los Viernes y Sábados.
