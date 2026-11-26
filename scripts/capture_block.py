#!/usr/bin/env python3
"""
Orquestador de Captura por Ventana Horaria (Plan B)
- Lee config/schedule.json en hora de Lima (America/Lima).
- Espera con precisión al segundo si el cron de GitHub arrancó antes.
- Graba todas las radios activas en paralelo usando 1 solo túnel VPN (wireproxy).
- Soporta división automática en Bloque 1 (hasta 23:20) y Bloque 2 (23:20 a 04:02).
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LIMA_TZ = ZoneInfo("America/Lima")


def parse_hhmm(hhmm: str) -> int:
    """Convierte HH:MM (incluyendo 26:00 o 28:00) a minutos desde las 00:00 del día lógico."""
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def get_logical_now():
    """Día lógico de programación empieza a las 05:00 AM (igual que main.js)."""
    now = datetime.now(LIMA_TZ)
    logical_date = now.date()
    minutes_since_midnight = now.hour * 60 + now.minute + (now.second / 60.0)
    if now.hour < 5:
        logical_date = logical_date - timedelta(days=1)
        minutes_since_midnight += 1440
    # Python weekday(): Mon=0..Sun=6 -> JS getDay(): Sun=0, Mon=1..Sat=6
    js_day = (logical_date.weekday() + 1) % 7
    return now, logical_date, js_day, minutes_since_midnight


def safe_slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


def record_single_show(show: dict, station: dict, start_min: int, end_min: int, part_num: int, logical_date_str: str, proxy_url: str):
    slug = safe_slug(show["name"])
    out_dir = os.path.join("captured", f"{slug}__{logical_date_str}__part_{part_num}")
    os.makedirs(out_dir, exist_ok=True)

    # Guardar metadata del show
    meta = {
        "name": show["name"],
        "slug": slug,
        "cover": show["cover"],
        "date": logical_date_str,
        "part": part_num,
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Esperar hasta la hora exacta de inicio de este show
    while True:
        _, _, _, curr_min = get_logical_now()
        wait_sec = (start_min - curr_min) * 60
        if wait_sec <= 1:
            break
        sleep_step = min(30.0, wait_sec)
        time.sleep(sleep_step)

    _, _, _, curr_min = get_logical_now()
    duration_sec = int(max(0, (end_min - curr_min) * 60))
    if duration_sec < 10:
        print(f"[{show['name']}] Tiempo restante menor a 10s ({duration_sec}s), omitiendo.")
        return

    print(f"--> [{show['name']}] Iniciando captura Parte {part_num} por {duration_sec}s ({duration_sec/60:.1f} min)...")

    target_end_ts = time.time() + duration_sec
    frag_idx = 1
    frag_files = []

    use_vpn = station.get("use_vpn", True) and bool(proxy_url)
    env = os.environ.copy()
    if use_vpn:
        env["http_proxy"] = proxy_url
        env["https_proxy"] = proxy_url
    else:
        env.pop("http_proxy", None)
        env.pop("https_proxy", None)

    while time.time() < target_end_ts:
        remaining = int(target_end_ts - time.time())
        if remaining <= 2:
            break

        frag_path = os.path.join(out_dir, f"frag_{frag_idx:03d}.ts")
        cmd = [
            "timeout", "--signal=INT", "--kill-after=10", str(remaining + 20),
            "ffmpeg", "-y", "-loglevel", "warning",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-rw_timeout", "15000000",
        ]
        if use_vpn:
            cmd += ["-http_proxy", proxy_url]

        cmd += [
            "-i", station["url"],
            "-t", str(remaining),
            "-c:a", "copy",
            "-f", "mpegts",
            frag_path,
        ]

        subprocess.run(cmd, env=env)

        if os.path.isfile(frag_path) and os.path.getsize(frag_path) > 0:
            frag_files.append(frag_path)
        frag_idx += 1
        time.sleep(1)

    if not frag_files:
        print(f"⚠️ [{show['name']}] No se capturaron fragmentos de audio.")
        return

    part_ts = os.path.join(out_dir, f"part_{part_num}.ts")
    if len(frag_files) == 1:
        os.replace(frag_files[0], part_ts)
    else:
        list_txt = os.path.join(out_dir, "list.txt")
        with open(list_txt, "w", encoding="utf-8") as lf:
            for fp in frag_files:
                lf.write(f"file '{os.path.basename(fp)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", part_ts],
            check=False,
        )
        for fp in frag_files:
            if os.path.exists(fp):
                os.remove(fp)

    size_mb = os.path.getsize(part_ts) / (1024 * 1024) if os.path.exists(part_ts) else 0
    print(f"✅ [{show['name']}] Parte {part_num} finalizada ({size_mb:.1f} MB).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", required=True, choices=["daytime_12", "daytime_15", "viva_night", "night_block_1", "night_block_2"])
    parser.add_argument("--override-day", type=int, default=-1, help="Opcional: forzar día (0=Dom..6=Sáb)")
    parser.add_argument("--proxy", default=os.environ.get("STREAM_HTTP_PROXY", ""))
    args = parser.parse_args()

    with open("config/schedule.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    now, logical_date, js_day, curr_min = get_logical_now()
    if args.override_day >= 0:
        js_day = args.override_day

    logical_date_str = logical_date.strftime("%Y-%m-%d")
    early_buf = cfg.get("early_buffer_minutes", 10)
    end_buf = cfg.get("end_buffer_minutes", 2)

    print(f"=================================================================")
    print(f" Ventana: {args.window} | Hora Lima: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Día lógico: {logical_date_str} (js_day={js_day})")
    print(f"=================================================================")

    # Punto de corte entre Bloque 1 y Bloque 2 de la noche: 22:50 (1370 min)
    # Permite que Sáb/Dom (5:50 PM - 10:50 PM = 5h) y Bloque 2 (10:50 PM - 4:02 AM = 5h 12m) no superen las 6h de GitHub
    SPLIT_MIN = 22 * 60 + 50

    tasks = []
    for show in cfg["shows"]:
        if js_day not in show["days"]:
            continue

        s_min = parse_hhmm(show["start"]) - early_buf
        e_min = parse_hhmm(show["end"]) + end_buf

        if args.window in ("daytime_12", "daytime_15", "viva_night"):
            if show["window"] == args.window:
                tasks.append((show, s_min, e_min, 1))
        elif args.window == "night_block_1":
            if show["window"] == "night" and s_min < SPLIT_MIN:
                tasks.append((show, s_min, min(e_min, SPLIT_MIN), 1))
        elif args.window == "night_block_2":
            if show["window"] == "night" and e_min > SPLIT_MIN:
                tasks.append((show, max(s_min, SPLIT_MIN), e_min, 2))

    if not tasks:
        print(f"ℹ️ No hay programas activos para la ventana '{args.window}' en día {js_day}. Saliendo.")
        return

    print(f"Programas programados en esta ventana ({len(tasks)}):")
    for show, s_m, e_m, p in tasks:
        print(f"  - {show['name']} (Parte {p}): min {s_m} -> min {e_m} ({(e_m - s_m)} min)")

    threads = []
    for show, s_m, e_m, p in tasks:
        station = cfg["stations"][show["station"]]
        t = threading.Thread(
            target=record_single_show,
            args=(show, station, s_m, e_m, p, logical_date_str, args.proxy),
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("=================================================================")
    print(f" VENTANA {args.window} FINALIZADA.")
    print("=================================================================")


if __name__ == "__main__":
    main()
