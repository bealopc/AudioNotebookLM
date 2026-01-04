# Audio EDU — Diálogos con Gemini (GUI + CLI) y transcripción con Whisper

Herramientas para generar **diálogos educativos a dos voces** con **Gemini TTS** y (opcionalmente) **transcribir** el audio con **Whisper**. Están pensadas para docentes y creadores que necesiten audios naturales y controlados por **idioma, acento y nivel CEFR**.

> ⚠️ Este repositorio **no** incluye la parte de **vídeo** (talking-head). Esa integración se probó con SadTalker fuera de este repo y **no está operativa aquí** (ver _“Estado del módulo de vídeo”_ más abajo).

---

## ¿Qué hay en este repo?

- **`dialogo_gui.py`** — Aplicación de escritorio (Tkinter):
  - Eliges **idioma** (es, en, ar, wo, uk, ru, fr, de, it, pt, zh, ja, ko, tr, pl),
  - **acento** (códigos BCP-47 como es-ES, en-US, uk-UA, ru-RU, ar-SA, wo-SN, …),
  - **nivel CEFR** (A1–C2),
  - las **dos voces** (Ana/Luis),
  - y el **tema** o un **texto propio**.
  - Genera `.wav` y un `.dialogo.txt` con el texto final. Puedes activar **transcripción** automática (Whisper).

- **`dialogo_cli.py`** — Versión por consola para **lotes** y automatización:
  - Mismos parámetros (tema, voces, idioma/acento/CEFR, salida, transcripción),
  - perfecta para scripts o pipelines.

---

## Requisitos

- **Windows** + **Python 3.10** (recomendado).
- **Gemini API Key** (ponla en `GEMINI_API_KEY` o `GOOGLE_API_KEY`).
- Paquetes:
  ```powershell
  pip install google-genai
  # Transcripción (opcional):
  pip install openai-whisper


FFmpeg en PATH (recomendado si usas Whisper).
Si vas a compilar la GUI como EXE con PyInstaller, mira la sección “Empaquetado”.

Instalación rápida

Clona o copia este repo en tu equipo (por ejemplo en %USERPROFILE%\AudioNotebookLM).

1.Instala dependencias:

pip install google-genai
pip install openai-whisper   # solo si vas a transcribir

2. Configura tu API key (elige una de estas):

Ventana de la GUI → Configurar API Key… (se guarda en ~\AudioNotebookLM\.gemini_key), o
variable de entorno:

[Environment]::SetEnvironmentVariable("GEMINI_API_KEY","TU_CLAVE","User")

Uso — GUI (dialogo_gui.py)

Lanza la app:

python "%USERPROFILE%\AudioNotebookLM\dialogo_gui.py"

Idioma (es,en,ar,wo,uk,ru,fr,de,it,pt,zh,ja,ko,tr,pl).
Acento (BCP-47: es-ES,en-US,en-GB,uk-UA,ru-RU,ar-SA,wo-SN,…).
Nivel CEFR (A1–C2) para controlar complejidad.
Voz Ana / Voz Luis: Kore, Puck, Brix.
Escribe tema (o marca “Usar mi texto tal cual”).
(Opcional) Transcribir con Whisper.
Generar audio.

Salidas en la carpeta elegida:

NOMBRE.dialogo.txt — diálogo (limpio).
NOMBRE.wav — audio Gemini (dos voces).
(si activas) Transcripción Whisper (.txt/.srt/.vtt según configuración por defecto de Whisper).

Uso — CLI (dialogo_cli.py)

Ejemplo:
python "%USERPROFILE%\AudioNotebookLM\dialogo_cli.py" `
  -t "Diferencias entre volcanes y terremotos" `
  --voices "Ana=Kore;Luis=Puck" `
  --out "$HOME\AudioNotebookLM\salida_volcanes" `
  --lang "uk" `
  --dialect "uk-UA" `
  --level "A2" `
  --transcribe

Parámetros clave

-t/--topic — tema (obligatorio si no pasas texto por otro lado).
--voices — Nombre=Voz;Nombre=Voz (máx. 2; por defecto Ana=Kore;Luis=Puck).
--out — ruta base sin extensión; se crean .dialogo.txt y .wav.
--lang — es,en,ar,wo,uk,ru,fr,de,it,pt,zh,ja,ko,tr,pl.
--dialect — acento BCP-47 (es-ES,en-US,ar-SA,wo-SN,…).
--level — CEFR (A1..C2).
--transcribe — activa Whisper al final.

Cómo funciona (resumen técnico)

Prompting: el GUI/CLI construye un prompt con:
idioma legible (English, Ukrainian, Arabic…),
pista de acento (BCP-47) y nivel CEFR,
formato del diálogo (solo líneas Ana: / Luis:).

Gemini:

Texto: gemini-2.0-flash.
Audio: gemini-2.5-flash-preview-tts con multi-speaker (Ana/Luis mapeadas a voces).

Whisper (opcional):
Auto-detección o fuerza idioma cuando aplica.
Requiere FFmpeg en PATH.

Limitaciones conocidas

Cobertura exacta por idioma/acento depende del motor TTS de Gemini. Algunos (p. ej. Wolof) pueden tener pronunciación variable; si no te convence, usa tu texto y otra vía de TTS específica para ese idioma.
Whisper es opcional y consume CPU; en equipos lentos, puede tardar.

Solución de problemas

“Falta API key” → Configúrala desde la GUI o con la variable de entorno.
Whisper no crea archivos → instala openai-whisper y FFmpeg; ejecuta el CLI con --transcribe.
Acento no suena “nativo” → cambia de voz (Kore/Puck/Brix) y refuerza el dialect_hint en el código si hace falta.
Caracteres raros en nombre de archivo → usa nombres base simples (sin acentos/espacios).

Estado del módulo de vídeo (SadTalker)

En el chat original se experimentó con SadTalker (para convertir audio + imagen en un vídeo tipo talking-head). Esa parte no forma parte de este repositorio y no está operativa aquí.
Lo que verás en este repo genera audio + texto únicamente.
Si en el futuro quieres añadirlo, la idea sería:
Tomar el .wav generado por estas herramientas,
Pasarlo a 16 kHz mono (ffmpeg -ac 1 -ar 16000),
Llamar a SadTalker/inference.py con tu imagen (--source_image avatar.png) y el audio (--driven_audio),
Escribir el .mp4 de salida.

Eso requiere otro repo/configuración (Torch, modelos, etc.) y no se incluye aquí.

Empaquetado (opcional_no funcionó) — GUI en EXE

Para distribuir la GUI como ejecutable:
cd "%USERPROFILE%\AudioNotebookLM"
py -3.10 -m venv .venv_build
& ".venv_build\Scripts\Activate.ps1"
pip install -U pip pyinstaller google-genai
pyinstaller --noconfirm --onefile --noconsole --name "DialogoGemini" dialogo_gui.py

El EXE quedará en dist\DialogoGemini.exe.
En el primer arranque pedirá API Key y la guardará en ~\AudioNotebookLM\.gemini_key.

Roadmap

✔️ GUI multi-idioma con CEFR y acentos BCP-47.
✔️ CLI para automatizar lotes.
☐ Selector ampliable de voces / compatibilidad por idioma.
☐ Exportación a paquetes (EXE) con perfil de idiomas.
☐ (Futuro) Script auxiliar de vídeo (SadTalker) fuera de este repo.