#!/usr/bin/env python3
"""
Gestor Resiliente de ProtonVPN (wireproxy) con Failover Automático:
- Lee PROTON_WG_CONF, PROTON_WG_CONF_2, PROTON_WG_CONF_3... desde variables de entorno.
- Al iniciar, valida conectividad real a través del túnel y rota automáticamente si un nodo cayó.
- Durante la grabación (multihilo), si una estación falla:
  1) Verifica si el proxy sigue sano antes de tocar nada (evita cortar a las demás radios sanas).
  2) Si el nodo VPN realmente murió o bloqueó tráfico, cambia en ~4s al siguiente servidor .conf.
"""

import os
import subprocess
import threading
import time


def clean_wireguard_conf(raw_conf: str, bind_addr: str = "127.0.0.1:8080") -> str:
    raw = raw_conf.replace("\r\n", "\n")
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("DNS ="):
            line = "DNS = 1.1.1.1"
        elif s.startswith("Address ="):
            v4 = [x.strip() for x in s.split("=", 1)[1].split(",") if ":" not in x]
            if v4:
                line = "Address = " + ", ".join(v4)
        elif s.startswith("AllowedIPs ="):
            line = "AllowedIPs = 0.0.0.0/0"
        lines.append(line)
        if s == "[Interface]":
            lines.append("MTU = 1320")
        elif s == "[Peer]":
            lines.append("PersistentKeepalive = 25")

    return "\n".join(lines) + f"\n\n[http]\nBindAddress = {bind_addr}\n"


def discover_vpn_configs() -> list[tuple[str, str]]:
    configs = []
    env_names = ["PROTON_WG_CONF"] + [f"PROTON_WG_CONF_{i}" for i in range(2, 6)]
    for name in env_names:
        val = os.environ.get(name, "").strip()
        if val:
            configs.append((name, val))
    return configs


class VpnManager:
    def __init__(self, bind_addr: str = "127.0.0.1:8080"):
        self.bind_addr = bind_addr
        self.proxy_url = f"http://{bind_addr}"
        self.configs = discover_vpn_configs()
        self._lock = threading.Lock()
        self._proc = None
        self._log_file = None
        self._current_idx = -1
        self._last_check_ts = 0.0
        self._last_check_ok = False
        self._conf_path = "wireproxy_active.conf"
        self._log_path = "wireproxy.log"

    def has_configs(self) -> bool:
        return len(self.configs) > 0

    def _stop_proc_locked(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=4)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._log_file is not None:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

    def stop(self):
        with self._lock:
            self._stop_proc_locked()
            if os.path.isfile(self._conf_path):
                try:
                    os.remove(self._conf_path)
                except OSError:
                    pass

    def _probe_locked(self) -> tuple[bool, str]:
        if self._proc is None or self._proc.poll() is not None:
            return False, "proceso wireproxy detenido"
        try:
            res = subprocess.run(
                [
                    "curl", "-sS", "--connect-timeout", "5", "--max-time", "8",
                    "--proxy", self.proxy_url,
                    "https://1.1.1.1/cdn-cgi/trace",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if res.returncode == 0 and "ip=" in res.stdout:
                info = {}
                for line in res.stdout.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        info[k] = v
                return True, f"ip={info.get('ip', '?')} loc={info.get('loc', '?')}"
        except Exception as e:
            return False, str(e)
        return False, "sin respuesta por proxy"

    def _start_index_locked(self, idx: int) -> bool:
        label, raw = self.configs[idx]
        self._stop_proc_locked()
        with open(self._conf_path, "w", encoding="utf-8") as f:
            f.write(clean_wireguard_conf(raw, self.bind_addr))

        self._log_file = open(self._log_path, "a", encoding="utf-8")
        self._proc = subprocess.Popen(
            ["wireproxy", "-c", self._conf_path],
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )

        # Dar tiempo al handshake WireGuard (~2-6s)
        for attempt in range(3):
            time.sleep(2.5 if attempt == 0 else 2.0)
            ok, detail = self._probe_locked()
            if ok:
                self._current_idx = idx
                self._last_check_ts = time.time()
                self._last_check_ok = True
                print(f"🛡️ VPN conectada [{label}] ({detail})")
                return True

        print(f"⚠️ Falló validación de nodo VPN [{label}] — probando siguiente respaldo...")
        self._stop_proc_locked()
        return False

    def ensure_healthy(self, force_rotate: bool = False) -> str | None:
        if not self.configs:
            return None

        with self._lock:
            now = time.time()
            if not force_rotate and not self._last_check_ok and self._last_check_ts > 0 and (now - self._last_check_ts < 30.0):
                return None
            if not force_rotate and self._proc is not None and self._proc.poll() is None:
                if now - self._last_check_ts < 10.0 and self._last_check_ok:
                    return self.proxy_url
                ok, _ = self._probe_locked()
                self._last_check_ts = time.time()
                self._last_check_ok = ok
                if ok:
                    return self.proxy_url

            total = len(self.configs)
            start_pos = 0 if self._current_idx < 0 else (self._current_idx + 1) % total
            for offset in range(total):
                cand_idx = (start_pos + offset) % total
                if self._start_index_locked(cand_idx):
                    return self.proxy_url

            self._last_check_ts = time.time()
            self._last_check_ok = False
            print("::warning::Ningún nodo ProtonVPN respondió en este ciclo.")
            return None

    def handle_stream_failure(self) -> str | None:
        """Llamado por un hilo de captura si ffmpeg se cortó: solo rota si el túnel realmente murió."""
        return self.ensure_healthy(force_rotate=False)
