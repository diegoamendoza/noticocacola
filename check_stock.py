#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_stock.py  -  Version para GitHub Actions.

Revisa el stock de laminas/sobres del Mundial 2026 en miCoca-Cola.cl
usando la API publica de catalogo de VTEX. Esta pensado para correr dentro
de un job de GitHub Actions: hace un loop revisando cada 60 segundos durante
LOOP_MINUTES minutos y luego termina (el cron del workflow lo vuelve a lanzar).

Toda la configuracion sensible (topic de ntfy, correo) se lee desde variables
de entorno, que en GitHub se guardan como "Secrets". Solo libreria estandar.
"""

import os
import json
import time
import ssl
import smtplib
import urllib.parse
import urllib.request
import urllib.error
from email.message import EmailMessage
from datetime import datetime, timezone

# ----------------- Config fija del sitio -----------------
PAGE_URL = "https://andina.micoca-cola.cl/laminas-coleccionables-mundial-fifa-2026"
API_BASE = "https://andina.micoca-cola.cl/api/catalog_system/pub/products/search"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ----------------- Helpers de entorno -----------------
def env(name, default=""):
    return os.environ.get(name, default).strip()


def env_list(name, default_list):
    raw = env(name)
    if not raw:
        return default_list
    return [x.strip() for x in raw.split(",") if x.strip()]


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes", "si", "sí")


SALES_CHANNEL = env("SALES_CHANNEL", "1")
SEARCH_TERMS = env_list("SEARCH_TERMS", [
    "laminas mundial", "sobres mundial",
    "album mundial 2026", "coleccionables mundial fifa",
])
NAME_KEYWORDS = env_list("NAME_KEYWORDS", [
    "lamin", "sobre", "album", "coleccion", "panini", "fifa", "mundial",
])
# Si NAME_KEYWORDS viene como "none" o "*" -> no filtra
if [k.lower() for k in NAME_KEYWORDS] in (["none"], ["*"]):
    NAME_KEYWORDS = []

CHECK_INTERVAL = int(env("CHECK_INTERVAL", "60"))   # segundos entre chequeos
LOOP_MINUTES = float(env("LOOP_MINUTES", "5"))      # cuanto dura el loop en este job

USE_NTFY = env_bool("USE_NTFY", True)
NTFY_TOPIC = env("NTFY_TOPIC")
NTFY_SERVER = env("NTFY_SERVER", "https://ntfy.sh")

USE_EMAIL = env_bool("USE_EMAIL", False)
EMAIL_FROM = env("EMAIL_FROM")
EMAIL_TO = env("EMAIL_TO")
EMAIL_APP_PASSWORD = env("EMAIL_APP_PASSWORD")
SMTP_HOST = env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(env("SMTP_PORT", "465"))


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] {msg}", flush=True)


# ----------------- Logica de catalogo -----------------
def http_get_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def buscar_productos():
    encontrados = {}
    for term in SEARCH_TERMS:
        q = urllib.parse.quote(term)
        url = f"{API_BASE}?ft={q}&sc={SALES_CHANNEL}&_from=0&_to=49"
        try:
            data = http_get_json(url)
            if isinstance(data, list):
                for p in data:
                    pid = p.get("productId") or p.get("productName")
                    if pid:
                        encontrados[pid] = p
        except Exception as e:
            log(f"  aviso: error buscando '{term}': {e}")
    return list(encontrados.values())


def nombre_coincide(nombre):
    if not NAME_KEYWORDS:
        return True
    n = nombre.lower()
    return any(k in n for k in NAME_KEYWORDS)


def detectar_disponibles(productos):
    hits = {}
    for p in productos:
        nombre = p.get("productName") or ""
        if not nombre_coincide(nombre):
            continue
        link_text = p.get("linkText", "")
        link = f"https://andina.micoca-cola.cl/{link_text}/p" if link_text else PAGE_URL
        for item in p.get("items", []):
            for seller in item.get("sellers", []):
                offer = seller.get("commertialOffer", {}) or {}
                qty = offer.get("AvailableQuantity", 0) or 0
                if offer.get("IsAvailable", False) or qty > 0:
                    hits[nombre] = {"nombre": nombre, "precio": offer.get("Price"),
                                    "cantidad": qty, "link": link}
                    break
    return list(hits.values())


# ----------------- Notificaciones -----------------
def notificar_ntfy(cuerpo):
    if not (USE_NTFY and NTFY_TOPIC):
        return
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{NTFY_TOPIC}",
                                     data=cuerpo.encode("utf-8"), method="POST")
        req.add_header("Title", "STOCK Laminas Mundial 2026!")
        req.add_header("Priority", "urgent")
        req.add_header("Tags", "soccer,shopping,rotating_light")
        req.add_header("Click", PAGE_URL)
        urllib.request.urlopen(req, timeout=20)
        log("  -> ntfy enviado")
    except Exception as e:
        log(f"  error ntfy: {e}")


def notificar_email(cuerpo):
    if not (USE_EMAIL and EMAIL_FROM and EMAIL_TO and EMAIL_APP_PASSWORD):
        return
    try:
        msg = EmailMessage()
        msg["From"], msg["To"] = EMAIL_FROM, EMAIL_TO
        msg["Subject"] = "STOCK disponible - Laminas Mundial 2026"
        msg.set_content(cuerpo)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=25) as s:
            s.login(EMAIL_FROM, EMAIL_APP_PASSWORD.replace(" ", ""))
            s.send_message(msg)
        log("  -> correo enviado")
    except Exception as e:
        log(f"  error correo: {e}")


def avisar(hits):
    lineas = []
    for h in hits:
        precio = f"${int(h['precio']):,}".replace(",", ".") if h.get("precio") else "s/precio"
        lineas.append(f"- {h['nombre']} ({precio}) - stock: {h['cantidad']}\n  {h['link']}")
    cuerpo = ("Hay stock de laminas/sobres del Mundial 2026:\n\n"
              + "\n".join(lineas) + f"\n\nComprar ahora: {PAGE_URL}")
    notificar_ntfy(cuerpo)
    notificar_email(cuerpo)


# ----------------- Loop principal del job -----------------
def main():
    log(f"Job iniciado. Loop de {LOOP_MINUTES} min, chequeo cada {CHECK_INTERVAL}s.")
    avisados = set()
    deadline = time.time() + LOOP_MINUTES * 60
    primera = True

    while primera or time.time() < deadline:
        primera = False
        try:
            hits = detectar_disponibles(buscar_productos())
            actuales = {h["nombre"] for h in hits}
            nuevos = [h for h in hits if h["nombre"] not in avisados]
            if nuevos:
                log(f"STOCK DETECTADO: {', '.join(h['nombre'] for h in nuevos)}")
                avisar(nuevos)
                avisados |= actuales
            elif hits:
                log(f"con stock (ya avisado en este job): {', '.join(actuales)}")
            else:
                log("sin stock todavia")
        except Exception as e:
            log(f"error en ciclo: {e}")

        if time.time() + CHECK_INTERVAL < deadline:
            time.sleep(CHECK_INTERVAL)
        else:
            break

    log("Job terminado.")


if __name__ == "__main__":
    main()
