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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from vpn_manager import VpnManager

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


def record_single_show(show: dict, station: dict, start_min: int, end_min: int, part_num: int, logical_date_str: str, fixed_proxy: str, vpn_mgr: VpnManager | None):
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
    fail_streak = 0
    needs_vpn = station.get("use_vpn", True)

    while time.time() < target_end_ts:
        remaining = int(target_end_ts - time.time())
        if remaining <= 2:
            break

        active_proxy = ""
        if needs_vpn:
            if fixed_proxy:
                active_proxy = fixed_proxy
            elif vpn_mgr and vpn_mgr.has_configs():
                active_proxy = vpn_mgr.ensure_healthy() or ""

        use_vpn = needs_vpn and bool(active_proxy)
        env = os.environ.copy()
        if use_vpn:
            env["http_proxy"] = active_proxy
            env["https_proxy"] = active_proxy
        else:
            env.pop("http_proxy", None)
            env.pop("https_proxy", None)

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
            cmd += ["-http_proxy", active_proxy]

        cmd += [
            "-i", station["url"],
            "-t", str(remaining),
            "-c:a", "copy",
            "-f", "mpegts",
            frag_path,
        ]

        t0 = time.time()
        subprocess.run(cmd, env=env)
        elapsed = time.time() - t0

        got_audio = os.path.isfile(frag_path) and os.path.getsize(frag_path) > 4096
        if got_audio:
            frag_files.append(frag_path)
            fail_streak = 0
        else:
            if os.path.isfile(frag_path):
                try:
                    os.remove(frag_path)
                except OSError:
                    pass
            fail_streak += 1

        # Si el fragmento terminó antes de tiempo, verificar salud del túnel VPN y rotar si murió
        if time.time() < target_end_ts - 5:
            if needs_vpn and vpn_mgr and vpn_mgr.has_configs() and (not got_audio or elapsed < 25):
                vpn_mgr.handle_stream_failure()

        frag_idx += 1
        time.sleep(min(5, max(1, fail_streak)))

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
                lf.write(f"file '{os.path.abspath(fp)}'\n")
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

    vpn_tasks = [s_m for show, s_m, _, _ in tasks if cfg["stations"][show["station"]].get("use_vpn", True)]
    fixed_proxy = args.proxy.strip()
    vpn_mgr = None if fixed_proxy else VpnManager()

    if vpn_tasks and vpn_mgr and vpn_mgr.has_configs():
        earliest_vpn_start = min(vpn_tasks)
        print(f"⏳ VPN con failover activo ({len(vpn_mgr.configs)} servidor(es) configurado(s)).")
        while True:
            _, _, _, c_min = get_logical_now()
            wait_sec = (earliest_vpn_start - 0.75 - c_min) * 60
            if wait_sec <= 1:
                break
            time.sleep(min(30.0, wait_sec))
        vpn_mgr.ensure_healthy()

    threads = []
    try:
        for show, s_m, e_m, p in tasks:
            station = cfg["stations"][show["station"]]
            t = threading.Thread(
                target=record_single_show,
                args=(show, station, s_m, e_m, p, logical_date_str, fixed_proxy, vpn_mgr),
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
    finally:
        if vpn_mgr:
            vpn_mgr.stop()

    print("=================================================================")
    print(f" VENTANA {args.window} FINALIZADA.")
    print("=================================================================")


if __name__ == "__main__":
    main()
