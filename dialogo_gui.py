# dialogo_gui.py - GUI para crear diálogos con Gemini (2 voces) y transcribir con Whisper
# Requiere: google-genai, openai-whisper (opcional para transcribir), ffmpeg (recomendado)
import os, sys, re, wave, threading, subprocess, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from google import genai
from google.genai import types

APP_DIR = os.path.join(os.path.expanduser("~"), "AudioNotebookLM")
KEY_FILE = os.path.join(APP_DIR, ".gemini_key")

VOICES = ["Kore", "Puck", "Brix"]

# Idiomas ofrecidos en la app
LANGS = ["es", "en", "ar", "wo", "uk", "ru", "fr", "de", "it", "pt", "zh", "ja", "ko", "tr", "pl"]

# Acentos / variantes (BCP-47)
DIALECTS = [
    "", "es-ES", "en-US", "en-GB",
    "uk-UA", "ru-RU", "ar-SA", "wo-SN",
    "fr-FR", "de-DE", "it-IT", "pt-PT", "pt-BR",
    "zh-CN", "ja-JP", "ko-KR", "tr-TR", "pl-PL"
]

LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2"]

def write_wav(path, pcm, rate=24000):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def clean_dialogue(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```.*?\n", "", t)
    t = re.sub(r"\n```$", "", t)
    return t.replace("\r\n", "\n").strip()

def dialect_hint(code: str) -> str:
    m = {
        "es-ES": "Usa español de España (vosotros, ordenador, coche, zumo, vale).",
        "en-US": "Use U.S. English and American accent.",
        "en-GB": "Use British English and UK accent.",
        "uk-UA": "Usa ucraniano estándar.",
        "ru-RU": "Usa ruso estándar.",
        "ar-SA": "Usa árabe moderno estándar (MSA).",
        "wo-SN": "Usa wolof de Senegal.",
        "fr-FR": "Utilise le français standard (France).",
        "de-DE": "Verwende Standarddeutsch (Deutschland).",
        "it-IT": "Usa italiano estándar (Italia).",
        "pt-PT": "Usa português de Portugal.",
        "pt-BR": "Use português do Brasil.",
        "zh-CN": "使用简体中文（中国大陆）。",
        "ja-JP": "標準的な日本語（日本）。",
        "ko-KR": "표준 한국어(대한민국)을 사용하세요.",
        "tr-TR": "Standart Türkiye Türkçesi kullan.",
        "pl-PL": "Używaj standardowego języka polskiego."
    }
    return m.get(code, "")

def lang_label(code: str) -> str:
    return {
        "es": "Spanish", "en": "English", "ar": "Arabic", "wo": "Wolof", "uk": "Ukrainian", "ru": "Russian",
        "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese",
        "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "tr": "Turkish", "pl": "Polish"
    }.get(code, code)

def level_hint(cefr: str) -> str:
    if not cefr:
        return ""
    cefr = cefr.upper()
    base = f"CEFR level {cefr}. "
    if cefr == "A2":
        return base + ("Short, simple sentences (≤12 words), basic vocabulary, avoid idioms, "
                       "present/preterite only, explain unknown words briefly.")
    if cefr == "B1":
        return base + ("Clear language, limited complex clauses, everyday topics, define terms when needed.")
    if cefr == "B2":
        return base + ("Moderate complexity, natural phrasing, some domain terms with brief explanations.")
    return base + "Match complexity to that level."

def build_prompt(topic, lang, dialect, level, words):
    style_bits = []
    if dialect:
        style_bits.append(dialect_hint(dialect))
    if level:
        style_bits.append(level_hint(level))
    style = " ".join([s for s in style_bits if s])
    return (
        f"Write an educational dialogue in {lang_label(lang)} between Ana and Luis about: {topic}. "
        "Only lines starting with 'Ana:' or 'Luis:'. No narrator. Friendly, clear, podcast pace. "
        f"{style} Target length ~{words} words. Avoid long paragraphs; use turns of 1–3 sentences."
    )

def load_api_key():
    # 1) variable de entorno; 2) fichero local; 3) vacío
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(KEY_FILE):
        try:
            return open(KEY_FILE, "r", encoding="utf-8").read().strip()
        except:
            pass
    return ""

def save_api_key(k):
    try:
        with open(KEY_FILE, "w", encoding="utf-8") as f:
            f.write(k.strip())
        os.environ["GEMINI_API_KEY"] = k.strip()
        return True
    except:
        return False

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Diálogo Gemini (2 voces) + Whisper")
        self.geometry("780x680")
        self.resizable(True, True)

        self.out_dir = tk.StringVar(value=APP_DIR)
        self.base_name = tk.StringVar(value="salida_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.lang = tk.StringVar(value="es")
        self.dialect = tk.StringVar(value="")
        self.level = tk.StringVar(value="")
        self.voiceA = tk.StringVar(value=VOICES[0])
        self.voiceB = tk.StringVar(value=VOICES[1] if len(VOICES) > 1 else VOICES[0])
        self.wordcount = tk.IntVar(value=320)
        self.mytext = tk.BooleanVar(value=False)
        self.transcribe = tk.BooleanVar(value=True)

        # Barra superior: carpeta salida + nombre base
        top = ttk.Frame(self); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Carpeta de salida:").pack(side="left")
        ttk.Entry(top, textvariable=self.out_dir, width=60).pack(side="left", padx=6)
        ttk.Button(top, text="Elegir…", command=self.choose_dir).pack(side="left")
        ttk.Label(top, text="Nombre base:").pack(side="left", padx=(12, 2))
        ttk.Entry(top, textvariable=self.base_name, width=24).pack(side="left")

        # Opciones
        opts = ttk.LabelFrame(self, text="Opciones"); opts.pack(fill="x", padx=10, pady=6)
        row1 = ttk.Frame(opts); row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Idioma (es/en):").pack(side="left")
        ttk.Combobox(row1, textvariable=self.lang, values=LANGS, width=8, state="readonly").pack(side="left", padx=6)
        ttk.Label(row1, text="Acento:").pack(side="left", padx=(16, 2))
        ttk.Combobox(row1, textvariable=self.dialect, values=DIALECTS, width=8, state="readonly").pack(side="left", padx=6)
        ttk.Label(row1, text="Nivel CEFR:").pack(side="left", padx=(16, 2))
        ttk.Combobox(row1, textvariable=self.level, values=LEVELS, width=6, state="readonly").pack(side="left", padx=6)

        row2 = ttk.Frame(opts); row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Voz Ana:").pack(side="left")
        ttk.Combobox(row2, textvariable=self.voiceA, values=VOICES, width=10, state="readonly").pack(side="left", padx=6)
        ttk.Label(row2, text="Voz Luis:").pack(side="left", padx=(16, 2))
        ttk.Combobox(row2, textvariable=self.voiceB, values=VOICES, width=10, state="readonly").pack(side="left", padx=6)
        ttk.Label(row2, text="Duración aprox. (palabras):").pack(side="left", padx=(16, 2))
        sc = ttk.Scale(row2, from_=150, to=600, orient="horizontal", variable=self.wordcount, command=lambda e: self.update_wc())
        sc.pack(side="left", fill="x", expand=True, padx=6)
        self.wc_label = ttk.Label(row2, text=str(self.wordcount.get())); self.wc_label.pack(side="left")

        # Texto/tema
        txtf = ttk.LabelFrame(self, text="Contenido (si marcas 'Usar mi texto', se leerá tal cual; si no, se generará un diálogo a partir del tema)")
        txtf.pack(fill="both", expand=True, padx=10, pady=6)
        self.text = tk.Text(txtf, wrap="word", height=16)
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        self.text.insert("1.0", "Escribe aquí el tema o pega el texto…")
        chks = ttk.Frame(self); chks.pack(fill="x", padx=10)
        ttk.Checkbutton(chks, text="Usar mi texto tal cual (no generar diálogo)", variable=self.mytext).pack(side="left")
        ttk.Checkbutton(chks, text="Transcribir con Whisper", variable=self.transcribe).pack(side="left", padx=16)

        # Botones
        btns = ttk.Frame(self); btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Configurar API Key…", command=self.set_key).pack(side="left")
        self.run_btn = ttk.Button(btns, text="Generar audio", command=self.run)
        self.run_btn.pack(side="right")
        self.status = ttk.Label(self, text="Listo."); self.status.pack(fill="x", padx=10, pady=(0, 8))

    def update_wc(self):
        self.wc_label.config(text=str(int(self.wordcount.get())))

    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_dir.get() or APP_DIR, title="Elige carpeta de salida")
        if d:
            self.out_dir.set(d)

    def set_key(self):
        def ok():
            k = e.get().strip()
            if not k:
                messagebox.showwarning("Clave vacía", "Pega tu API key.")
                return
            if save_api_key(k):
                messagebox.showinfo("OK", "API key guardada.")
                win.destroy()
            else:
                messagebox.showerror("Error", "No se pudo guardar la clave.")
        win = tk.Toplevel(self); win.title("Configurar API key")
        ttk.Label(win, text="Pega tu API key de Gemini:").pack(padx=12, pady=8)
        e = ttk.Entry(win, width=60); e.pack(padx=12, pady=6); e.focus_set()
        ttk.Button(win, text="Guardar", command=ok).pack(pady=10)

    def run(self):
        api_key = load_api_key()
        if not api_key:
            messagebox.showwarning("Falta API Key", "Configura tu API key primero.")
            return
        # Parámetros
        out_dir = self.out_dir.get().strip() or APP_DIR
        base = self.base_name.get().strip() or "salida"
        os.makedirs(out_dir, exist_ok=True)
        base_path = os.path.join(out_dir, re.sub(r"[^\w\-\.]+", "_", base))
        lang = self.lang.get()
        dialect = self.dialect.get()
        level = self.level.get()
        voiceA = self.voiceA.get()
        voiceB = self.voiceB.get()
        wordcount = int(self.wordcount.get())
        txt = self.text.get("1.0", "end").strip()
        use_mytext = self.mytext.get()
        do_transc = self.transcribe.get()

        self.run_btn.config(state="disabled")
        self.status.config(text="Generando… (no cierres la ventana)")
        threading.Thread(
            target=self._worker,
            args=(api_key, base_path, lang, dialect, level, voiceA, voiceB, wordcount, txt, use_mytext, do_transc),
            daemon=True
        ).start()

    def _worker(self, api_key, base_path, lang, dialect, level, voiceA, voiceB, wordcount, txt, use_mytext, do_transc):
        try:
            client = genai.Client(api_key=api_key)
            if use_mytext:
                dialogue = txt
            else:
                prompt = build_prompt(txt, lang, dialect, level, wordcount)
                resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                dialogue = getattr(resp, "text", None)
                if not dialogue and getattr(resp, "candidates", None):
                    dialogue = resp.candidates[0].content.parts[0].text
                dialogue = clean_dialogue(dialogue or "")
                if not dialogue:
                    raise RuntimeError("No se obtuvo texto del modelo.")

            txt_path = base_path + ".dialogo.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(dialogue)

            mapping = {"Ana": voiceA, "Luis": voiceB}
            speaker_cfg = []
            for name, voice in mapping.items():
                speaker_cfg.append(
                    types.SpeakerVoiceConfig(
                        speaker=name,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    )
                )

            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=dialogue,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=speaker_cfg
                        )
                    ),
                ),
            )
            pcm = resp2.candidates[0].content.parts[0].inline_data.data
            wav_path = base_path + ".wav"
            write_wav(wav_path, pcm)

            if do_transc:
                whisper_map = {
                    "es": "es", "en": "en", "ar": "ar", "uk": "uk", "ru": "ru", "fr": "fr", "de": "de", "it": "it", "pt": "pt",
                    "zh": "zh", "ja": "ja", "ko": "ko", "tr": "tr", "pl": "pl"
                    # "wo": autodetección
                }
                lang_for_whisper = whisper_map.get(lang)
                cmd = [sys.executable, "-m", "whisper", wav_path, "--model", "small"]
                if lang_for_whisper:
                    cmd += ["--language", lang_for_whisper]
                subprocess.run(cmd, check=False)

            self.after(0, lambda: self._done_ok(base_path))
        except Exception as e:
            self.after(0, lambda: self._done_err(e))

    def _done_ok(self, base_path):
        self.status.config(text="Listo.")
        self.run_btn.config(state="normal")
        messagebox.showinfo("Terminado", f"Creado:\n{base_path}.dialogo.txt\n{base_path}.wav\n(y transcripción .txt si la marcaste)")

    def _done_err(self, e):
        self.status.config(text="Error.")
        self.run_btn.config(state="normal")
        messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    if not os.path.isdir(APP_DIR):
        os.makedirs(APP_DIR, exist_ok=True)
    App().mainloop()
