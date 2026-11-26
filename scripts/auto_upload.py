#!/usr/bin/env python3
"""
Auto-subidor Híbrido (Post-Grabación):
- Recorre todos los audios consolidados en final_audios/<SLUG>__<FECHA>/
- Los empaqueta a 1080x1080 1 FPS BT.709 CRF 18 + Opus 320 kbps (solo lectura de carátula).
- Los sube automáticamente en Privado con etiqueta [CRUDO] para que Content ID evalúe
  bloqueos por copyright durante la madrugada mientras duermes.
- El audio .ts maestro sigue guardado 3 días en GitHub Artifacts para cortes instantáneos en Plan B.
"""

import glob
import json
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from media_utils import download_cover, format_date_es, mux_mp4, probe_duration


def main():
    has_token = any(os.environ.get(f"YT_TOKEN_{i}", "").strip() for i in range(1, 11))
    if not has_token:
        print("ℹ️ No hay YT_TOKEN_* configurados en Secrets. Omitiendo auto-subida a YouTube.")
        return

    with open("config/schedule.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    covers_base_url = cfg["covers_base_url"]

    audio_dirs = sorted(glob.glob("final_audios/*"))
    if not audio_dirs:
        print("ℹ️ No hay audios consolidados en final_audios/ para auto-subir.")
        return

    work_dir = "work_autoupload"
    os.makedirs(work_dir, exist_ok=True)
    upload_script = os.path.join(SCRIPT_DIR, "upload_youtube.py")

    slot_idx = 0
    for d in audio_dirs:
        audio_ts = os.path.join(d, "audio.ts")
        meta_json = os.path.join(d, "meta.json")
        if not os.path.isfile(audio_ts) or os.path.getsize(audio_ts) < 10_000:
            continue

        slot_idx += 1
        meta = {}
        if os.path.isfile(meta_json):
            with open(meta_json, "r", encoding="utf-8") as f:
                meta = json.load(f)

        show_name = meta.get("name", os.path.basename(d))
        date_str = meta.get("date", "")
        date_label = format_date_es(date_str)
        cover_file = meta.get("cover", f"{show_name.replace(' ', '%20')}.png")

        print(f"\n=================================================================")
        print(f" Auto-Subida [CRUDO] #{slot_idx}: {show_name} ({date_label})")
        print(f"=================================================================")

        cover_path = os.path.join(work_dir, "cover.png")
        download_cover(cover_file, covers_base_url, cover_path)

        try:
            dur_sec = probe_duration(audio_ts)
            print(f"--> Duración medida: {dur_sec:.1f}s")
        except Exception as e:
            print(f"::warning::No se pudo medir duración de {show_name}: {e}")
            dur_sec = None

        mp4_path = os.path.join(work_dir, "raw_upload.mp4")
        try:
            print("--> Empaquetando MP4 1080x1080 (1 FPS, BT.709, Opus 320 kbps)...")
            mux_mp4(cover_path, audio_ts, mp4_path, dur_sec)
            mp4_mb = os.path.getsize(mp4_path) / (1024 * 1024)
            print(f"✅ MP4 listo ({mp4_mb:.1f} MB). Subiendo a YouTube en Privado...")

            yt_title = f"{show_name} - {date_label} [CRUDO]"
            yt_desc = (
                f"Grabación automática cruda de {show_name} ({date_label}). "
                f"Subida en Privado para verificación previa de inicio y Content ID."
            )
            res = subprocess.run(
                [
                    sys.executable, upload_script,
                    "--file", mp4_path,
                    "--title", yt_title,
                    "--description", yt_desc,
                    "--privacy", "private",
                    "--slot-index", str(slot_idx),
                ],
                check=False,
            )
            if res.returncode != 0:
                print(
                    f"::warning::No se pudo auto-subir '{yt_title}' (posible cuota YouTube agotada). "
                    f"El audio completo sigue guardado 3 días en GitHub Artifacts."
                )
        finally:
            if os.path.isfile(mp4_path):
                os.remove(mp4_path)

    shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
