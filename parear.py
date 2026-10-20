import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

URL = "https://mymuze.vm.co.mz/index.html#/home"
CONTA = sys.argv[1] if len(sys.argv) > 1 else "1"
ESPERA_MAX = 420  # segundos para você digitar o código no app
PASTA = "sessoes"
os.makedirs(PASTA, exist_ok=True)


def texto(page):
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def tela_de_codigo(t):
    t = t.lower()
    return "introduz o código" in t or "novo dispositivo" in t


def ler_codigo(t):
    m = re.search(r"\b(\d{6})\b", t)
    return m.group(1) if m else None


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    inicio = time.time()
    ultimo_codigo = None
    sucesso = False

    while time.time() - inicio < ESPERA_MAX:
        t = texto(page)
        if tela_de_codigo(t):
            codigo = ler_codigo(t)
            if codigo and codigo != ultimo_codigo:
                ultimo_codigo = codigo
                page.screenshot(path="captura_codigo.png")
                print("\n" + "=" * 40, flush=True)
                print(f"   CONTA {CONTA}  ->  CÓDIGO:  {codigo}", flush=True)
                print("   No app MyMuze: ⚙ > Novo dispositivo > digite o código", flush=True)
                print("=" * 40 + "\n", flush=True)
        elif ultimo_codigo:
            sucesso = True  # saiu da tela de código = login feito
            break
        time.sleep(3)

    if not sucesso:
        print("Tempo esgotado: o código não foi usado a tempo.", flush=True)
        browser.close()
        sys.exit(1)

    time.sleep(5)
    page.screenshot(path="captura_pos_login.png")
    destino = f"{PASTA}/sessao_{CONTA}.json"
    try:
        context.storage_state(path=destino, indexed_db=True)
    except TypeError:
        context.storage_state(path=destino)
    print(f"Conta {CONTA} pareada! Sessão guardada.", flush=True)
    browser.close()
  
