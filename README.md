# Agente de WhatsApp con Claude + Twilio + Google Sheets

Bot de WhatsApp para Replit que:

1. Recibe webhooks de mensajes de WhatsApp entrantes desde Twilio.
2. Responde automáticamente usando la API de Claude (Anthropic).
3. Detecta prospectos potenciales por palabras clave (`consulta`, `precio`,
   `información`, `venta`, `necesito`, configurables).
4. Guarda los prospectos calificados en Google Sheets con las columnas:
   `Fecha`, `Nombre`, `Teléfono`, `Mensaje`, `Clasificación`.
5. Valida la firma de cada webhook de Twilio, maneja errores en cada paso
   sin caerse, y registra todas las acciones en logs (consola + archivo
   rotativo en `logs/app.log`).

## ⚠️ Importante: la hoja de Google Sheets debes crearla tú

Este agente **no puede crear la hoja de cálculo ni la cuenta de servicio de
Google por sí mismo** — requiere acceso a tu cuenta de Google, que Claude no
tiene. El código sí crea automáticamente la pestaña `Prospectos` y los
encabezados dentro de la hoja la primera vez que se ejecuta, pero **tú
debes crear estos tres elementos antes**:

### Paso A — Crear la hoja de cálculo

1. Ve a [sheets.google.com](https://sheets.google.com) y crea una hoja de
   cálculo nueva (puede estar vacía).
2. Cópiale el nombre que quieras, por ejemplo "Prospectos WhatsApp".
3. Copia la URL completa de la hoja (la de la barra de direcciones del
   navegador) — la necesitarás como `GOOGLE_SHEETS_URL`.

### Paso B — Crear una cuenta de servicio de Google Cloud

El bot necesita credenciales propias (no tu usuario) para poder escribir en
la hoja mediante la API. Esto se llama "cuenta de servicio".

1. Ve a [console.cloud.google.com](https://console.cloud.google.com/) y crea
   un proyecto nuevo (o usa uno existente).
2. En el buscador del proyecto, habilita estas dos APIs:
   - **Google Sheets API**
   - **Google Drive API**
3. Ve a **APIs y servicios → Credenciales → Crear credenciales → Cuenta de
   servicio**. Dale un nombre (ej. `whatsapp-bot-sheets`) y créala.
4. Entra a la cuenta de servicio recién creada → pestaña **Claves** → **Agregar
   clave → Crear clave nueva → JSON**. Se descargará un archivo `.json`.
5. Abre ese archivo y copia **todo su contenido** (es un JSON de una sola
   pieza) — lo necesitarás como `GOOGLE_SERVICE_ACCOUNT_JSON`.
6. Dentro del JSON descargado busca el campo `"client_email"` — es algo como
   `whatsapp-bot-sheets@tu-proyecto.iam.gserviceaccount.com`.

### Paso C — Compartir la hoja con la cuenta de servicio

1. Abre la hoja de cálculo del Paso A.
2. Haz clic en **Compartir** (botón azul, arriba a la derecha).
3. Pega el `client_email` del Paso B y dale permisos de **Editor**.
4. Guarda.

Sin este paso, el bot recibirá un error de permisos al intentar escribir.

## Variables de entorno / Secrets requeridos

En Replit: abre el ícono de candado ("Secrets") en la barra lateral y agrega
cada una de estas (nunca las escribas directamente en el código):

| Variable | Descripción |
|---|---|
| `TWILIO_ACCOUNT_SID` | SID de tu cuenta de Twilio |
| `TWILIO_AUTH_TOKEN` | Auth Token de tu cuenta de Twilio |
| `ANTHROPIC_API_KEY` | API key de Anthropic (Claude) |
| `GOOGLE_SHEETS_URL` | URL de la hoja creada en el Paso A |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Contenido completo del JSON del Paso B (en una sola línea) |

Opcionales (tienen valores por defecto razonables, ver `.env.example`):
`CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `CLAUDE_EFFORT`, `BUSINESS_NAME`,
`PROSPECT_KEYWORDS`, `VALIDATE_TWILIO_SIGNATURE`, `PORT`, `LOG_LEVEL`.

> Si `GOOGLE_SHEETS_URL` / `GOOGLE_SERVICE_ACCOUNT_JSON` todavía no están
> configurados, el bot igual arranca y sigue respondiendo mensajes de
> WhatsApp con Claude — simplemente no podrá guardar prospectos hasta que
> completes los pasos A-C, y lo dejará registrado en el log como
> advertencia.

## Configurar el webhook de Twilio (WhatsApp Sandbox o número de producción)

1. En Replit, ejecuta el proyecto (botón **Run**) o usa **Deployments** para
   una URL estable de producción. Copia la URL pública que te da Replit,
   por ejemplo `https://tu-repl.usuario.repl.co`.
2. En la [consola de Twilio](https://console.twilio.com/) → **Messaging →
   Try it out → Send a WhatsApp message** (sandbox) o en la configuración de
   tu número de WhatsApp de producción, configura el webhook **"WHEN A
   MESSAGE COMES IN"** apuntando a:

   ```
   https://tu-repl.usuario.repl.co/webhook/whatsapp
   ```

   Método: `HTTP POST`.

## Ejecutar en Replit

1. Sube este proyecto a un Repl de tipo Python (o importa el repositorio de
   GitHub directamente en Replit).
2. Configura los Secrets listados arriba.
3. Presiona **Run**. Verás en la consola los logs de arranque.
4. Para producción persistente, usa **Deployments** en Replit (usa
   automáticamente `gunicorn` según el `.replit` incluido).

## Ejecutar en local (opcional, para pruebas)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y completa los valores
python app.py
```

Para probar el webhook localmente sin exponer tu máquina a internet puedes
usar [ngrok](https://ngrok.com/) y apuntar el webhook de Twilio a la URL que
te dé ngrok. Si pruebas con `curl` directamente (sin pasar por Twilio real),
pon `VALIDATE_TWILIO_SIGNATURE=false` en tu `.env` solamente para esa
prueba local — nunca en producción.

## Correr las pruebas

```bash
python -m unittest discover tests -v
```

## Estructura del proyecto

```
app.py                    # Servidor Flask: webhook, health check, orquestación
config.py                 # Carga y valida variables de entorno
logging_config.py         # Logging a consola + archivo rotativo (logs/app.log)
claude_client.py          # Llamadas a la API de Claude con manejo de errores
sheets_client.py          # Escritura en Google Sheets vía gspread
prospect_classifier.py    # Clasificación de prospectos por palabras clave
tests/                    # Pruebas unitarias del clasificador
requirements.txt
.env.example              # Plantilla de variables de entorno
.replit                   # Configuración de ejecución/deploy en Replit
```

## Notas de producción

- **Nunca** subas un `.env` real ni el JSON de la cuenta de servicio al
  repositorio (`.gitignore` ya los excluye).
- El webhook valida la firma `X-Twilio-Signature` en cada petición; una
  firma inválida se rechaza con `403` y queda registrada en el log.
- Cualquier error (Claude, Google Sheets, clasificación) se captura y
  registra sin interrumpir la respuesta al usuario de WhatsApp: si Claude
  falla, se envía un mensaje de repliegue; si Sheets falla, el prospecto
  simplemente no se guarda pero el usuario sigue recibiendo su respuesta.
- Todos los eventos relevantes (mensaje entrante, clasificación, guardado en
  Sheets, respuesta de Claude, respuesta enviada, y cualquier error) se
  registran en `logs/app.log` y en la consola.
