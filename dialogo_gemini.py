from google import genai
from google.genai import types
import os, wave, argparse, re, subprocess, sys

def write_wav(path, pcm, rate=24000):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate); wf.writeframes(pcm)

def clean_dialogue(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```.*?\n", "", t)
    t = re.sub(r"\n```$", "", t)
    return t.replace("\r\n","\n").strip()

def dialect_hint(code: str) -> str:
    m = {
        "en-US": "Use U.S. English (American accent) with U.S. vocabulary (apartment, elevator, trash, soccer).",
        "en-GB": "Use British English (UK accent) with UK vocabulary (flat, lift, rubbish, football).",
        "es-ES": "Usa español de España (castellano peninsular): 'vosotros', vocabulario como ordenador, coche, zumo.",
        "es-MX": "Usa español de México: 'ustedes', vocabulario como computadora, carro, jugo.",
    }
    return m.get(code, "")

def level_hint(cefr: str) -> str:
    if not cefr: return ""
    cefr = cefr.upper()
    base = f"CEFR level {cefr}. "
    if cefr == "A2":
        return base + ("Short, simple sentences (≤12 words), basic vocabulary, avoid idioms/slang, "
                       "present/preterite only, explain unknown words briefly.")
    if cefr == "B1":
        return base + ("Clear language, limited complex clauses, everyday topics, define terms when needed.")
    if cefr == "B2":
        return base + ("Moderate complexity, natural phrasing, some domain terms with brief explanations.")
    return base + "Match complexity to that level."
    
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-t","--topic", required=True, help="Tema del diálogo")
    ap.add_argument("--voices", default="Ana=Kore;Luis=Puck", help="Mapeo nombre=voz;nombre=voz (máx. 2)")
    ap.add_argument("--out", default=os.path.join(os.path.expanduser("~"),"AudioNotebookLM","salida"), help="Ruta base de salida (sin extensión)")
    ap.add_argument("--lang", default="es", help="Idioma principal del diálogo (es/en)")
    ap.add_argument("--dialect", default="", help="Dialecto/acento: en-US, en-GB, es-ES, es-MX")
    ap.add_argument("--level", default="", help="Nivel CEFR: A1–C2 (ej.: A2)")
    ap.add_argument("--model_text", default="gemini-2.0-flash")
    ap.add_argument("--model_tts", default="gemini-2.5-flash-preview-tts")
    ap.add_argument("--transcribe", action="store_true", help="Lanza Whisper al terminar")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la API key. Define GEMINI_API_KEY o GOOGLE_API_KEY.")

    client = genai.Client(api_key=api_key)

    style_bits = []
    if args.dialect: style_bits.append(dialect_hint(args.dialect))
    if args.level:   style_bits.append(level_hint(args.level))
    style = " ".join([s for s in style_bits if s])

    prompt = (
        f"Write an educational dialogue in {args.lang} between Ana and Luis about: {args.topic}. "
        "Only lines starting with 'Ana:' or 'Luis:'. No narrator. Friendly, clear, podcast pace. "
        f"{style} Length 250–400 words. Avoid long paragraphs; use turns of 1–3 sentences."
    )

    # 1) Generar el diálogo (texto)
    resp = client.models.generate_content(model=args.model_text, contents=prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        text = resp.candidates[0].content.parts[0].text
    text = clean_dialogue(text or "")
    if not text:
        raise RuntimeError("No se obtuvo texto del modelo. Reintenta.")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    txt_path = args.out + ".dialogo.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 2) TTS dos voces
    mapping = dict(pair.split("=",1) for pair in args.voices.split(";"))
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
        model=args.model_tts,
        contents=text,
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
    wav_path = args.out + ".wav"
    write_wav(wav_path, pcm)
    print("Creado diálogo:", txt_path)
    print("Creado audio  :", wav_path)

    # 3) (opcional) Transcribir con Whisper
    if args.transcribe:
        cmd = [sys.executable, "-m", "whisper", wav_path, "--language", args.lang if args.lang in ("es","en") else "es", "--model", "small"]
        print("Transcribiendo con Whisper...")
        subprocess.run(cmd, check=False)
        print("Transcripción lista (mismo nombre con extensión .txt).")

if __name__ == "__main__":
    main()
