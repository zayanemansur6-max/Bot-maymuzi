import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

URL_ALVO = "https://mymuze.vm.co.mz/index.html#/home"
TOTAL_CONTAS = 2
TEMPO_OUVINDO = 30  # segundos
PASTA = "sessoes"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Nunca clicar em "Atualizar agora" (é a opção paga).
TEXTOS_BOTOES = [
    "Aceitar", "Concordar", "Entendi", "Fechar", "OK", "Skip", "Ignorar",
]

SELETORES_PLAY = [
    "a.play-actions-play",
    ".play-button", ".btn-play", ".play-btn",
    '[aria-label*="play" i]', '[aria-label*="tocar" i]',
]

# Guarda qualquer áudio/vídeo que o site tente tocar (mesmo fora da página)
SCRIPT_VIGIA = """
(() => {
  window.__medias = [];
  const orig = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function (...a) {
    window.__medias.push(this);
    return orig.apply(this, a);
  };
})();
"""

JS_MIDIAS = """() => [...(window.__medias || []),
    ...document.querySelectorAll('audio, video')]"""


def clicar_texto_exato(page, texto, espera=2):
    try:
        padrao = re.compile(rf"^\s*{texto}\s*$", re.I)
        alvo = page.get_by_text(padrao).filter(visible=True)
        if alvo.count() > 0:
            alvo.first.click(timeout=3000)
            time.sleep(espera)
            return True
    except Exception:
        pass
    return False


def fechar_popups_e_avisos(page):
    for texto in TEXTOS_BOTOES:
        if clicar_texto_exato(page, re.escape(texto), espera=1):
            print(f"  --> Aviso fechado: '{texto}'")


def ir_para_estacoes(page, n):
    if clicar_texto_exato(page, r"Continuar nas esta[cç][õo]es", espera=3):
        print(f"[Conta {n}] Pop-up: 'Continuar nas estações' clicado.")
    if clicar_texto_exato(page, r"Esta[cç][õo]es", espera=3):
        print(f"[Conta {n}] Aba 'Estações' aberta.")


def clicar_play(page, n):
    for seletor in SELETORES_PLAY:
        try:
            alvo = page.locator(seletor).filter(visible=True)
            if alvo.count() == 0:
                continue
            el = alvo.first
            try:
                el.scroll_into_view_if_needed(timeout=3000)
                el.hover(timeout=3000)
            except Exception:
                pass
            try:
                el.click(timeout=5000)
            except Exception:
                el.click(timeout=3000, force=True)
            print(f"[Conta {n}] Play clicado com: {seletor}")
            return True
        except Exception:
            continue
    return False


def na_tela_de_login(page):
    try:
        t = page.inner_text("body").lower()
    except Exception:
        return False
    return "introduz o código" in t or "novo dispositivo" in t


def musica_tocando(page):
    return page.evaluate(
        f"""() => ({JS_MIDIAS[6:]})()
            .some(m => !m.paused && m.currentTime > 0)"""
        if False else
        """() => [...(window.__medias || []),
            ...document.querySelectorAll('audio, video')]
            .some(m => !m.paused && m.currentTime > 0)"""
    )


def diagnostico(page, n):
    print(f"[Conta {n}] --- DIAGNÓSTICO ---")
    try:
        print("URL:", page.url)
        texto = page.inner_text("body").replace("\n", " | ")
        print("TEXTO:", texto[:400])
        midias = page.evaluate(
            """() => [...(window.__medias || []),
                ...document.querySelectorAll('audio, video')].map(m => ({
                tag: m.tagName, paused: m.paused, t: m.currentTime,
                ready: m.readyState, erro: m.error ? m.error.code : null,
                src: (m.currentSrc || '').slice(0, 80)}))"""
        )
        print("MIDIAS (erro 4 = formato não suportado):", midias)
    except Exception as e:
        print("diagnóstico falhou:", e)


def abrir_navegador(p):
    args = ["--no-sandbox", "--disable-setuid-sandbox",
            "--disable-notifications",
            "--autoplay-policy=no-user-gesture-required"]
    try:
        b = p.chromium.launch(channel="chrome", headless=True, args=args)
        print("Navegador: Google Chrome")
        return b
    except Exception:
        print("Navegador: Chromium do Playwright")
        return p.chromium.launch(headless=True, args=args)


def rodar_conta(p, n):
    arquivo = f"{PASTA}/sessao_{n}.json"
    if not os.path.exists(arquivo):
        print(f"[Conta {n}] {arquivo} não existe. Rode 'Parear conta' primeiro.")
        return False

    browser = abrir_navegador(p)
    context = browser.new_context(
        storage_state=arquivo, user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
    )
    context.add_init_script(SCRIPT_VIGIA)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())

    try:
        print(f"\n===== Conta {n} de {TOTAL_CONTAS} =====")
        page.goto(URL_ALVO, wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)

        if na_tela_de_login(page):
            page.screenshot(path=f"captura_{n}.png")
            print(f"[Conta {n}] ERRO: caiu na tela de login. "
                  "A sessão expirou, rode 'Parear conta' de novo.")
            return False

        fechar_popups_e_avisos(page)
        ir_para_estacoes(page, n)
        fechar_popups_e_avisos(page)

        if not clicar_play(page, n):
            print(f"[Conta {n}] Botão não achado, a tentar a tecla Espaço...")
            page.keyboard.press("Space")

        time.sleep(6)
        fechar_popups_e_avisos(page)

        tocando = musica_tocando(page)
        page.screenshot(path=f"captura_{n}.png")

        if not tocando:
            print(f"[Conta {n}] ERRO: a música não começou.")
            diagnostico(page, n)
            return False

        print(f"[Conta {n}] A tocar! A aguardar {TEMPO_OUVINDO}s...")
        time.sleep(TEMPO_OUVINDO)
        print(f"[Conta {n}] Concluída.")
        return True

    except Exception as e:
        print(f"[Conta {n}] ERRO: {e}")
        try:
            page.screenshot(path=f"captura_{n}.png")
        except Exception:
            pass
        return False
    finally:
        browser.close()
        time.sleep(2)


def main():
    with sync_playwright() as p:
        resultados = {n: rodar_conta(p, n) for n in range(1, TOTAL_CONTAS + 1)}
    print("\nResumo:", {f"conta_{n}": ("ok" if r else "falhou")
                        for n, r in resultados.items()})
    return all(resultados.values())


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
