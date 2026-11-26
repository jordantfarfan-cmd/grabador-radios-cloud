#!/usr/bin/env python3
"""
Generador local de credenciales OAuth para YouTube (Ejecutar una sola vez por proyecto).
Uso:
  pip install google-auth-oauthlib
  python scripts/get_youtube_token.py client_secret_1.json
Copia el JSON que imprime en consola y guárdalo en GitHub Secrets como YT_TOKEN_1 (y YT_TOKEN_2 para el segundo proyecto).
"""

import json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/get_youtube_token.py <ruta_al_client_secret.json>")
        sys.exit(1)

    secret_file = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    # Verificar el nombre exacto del canal autorizado
    try:
        yt = build("youtube", "v3", credentials=creds)
        res = yt.channels().list(part="snippet", mine=True).execute()
        items = res.get("items", [])
        if items:
            ch = items[0]
            print(f"\n✅ CANAL AUTORIZADO CONFIRMADO: {ch['snippet']['title']} (ID: {ch['id']})")
        else:
            print("\n⚠️ Aviso: No se detectó canal en esta cuenta.")
    except Exception as e:
        print(f"\n⚠️ No se pudo consultar el nombre del canal: {e}")

    output = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

    print("\n" + "=" * 70)
    print("COPIA TODO ESTE TEXTO DE ABAJO Y GUÁRDALO EN GITHUB SECRETS:")
    print("=" * 70)
    print(json.dumps(output))
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
