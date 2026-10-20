import os
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

TEXTOS_BOTOES = [
    "Aceitar", "Concordar", "Continuar", "Entendi",
    "Continuar no plano", "Continuar nas estações", "Continuar com plano",
    "Fechar", "OK", "Skip", "Ignorar",
]

SELETOR_PLAY = (
    '.play-button, .btn-play, .play-btn, '
    '[aria-label*="Play"], [aria-label*="Tocar"]'
)


def fechar_popups_e_avisos(page):
    for texto in TEXTOS_BOTOES:
        try:
            botao = page.locator(f"text=/{texto}/i")
            if botao.count() > 0 and botao.first.is_visible():
                print(f"  --> Aviso detetado, a clicar em: '{texto}'")
                botao.first.click(timeout=3000)
                time.sleep(1)
        except Exception:
            pass


def na_tela_de_login(page):
    try:
        t = page.inner_text("body").lower()
    except Exception:
        return False
    return "introduz o código" in t or "novo dispositivo" in t


def musica_tocando(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('audio, video')]
            .some(m => !m.paused && m.currentTime > 0)"""
    )


def rodar_conta(p, n):
    arquivo = f"{PASTA}/sessao_{n}.json"
    if not os.path.exists(arquivo):
        print(f"[Conta {n}] {arquivo} não existe. Rode 'Parear conta' primeiro.")
        return False

    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox",
              "--disable-notifications",
              "--autoplay-policy=no-user-gesture-required"],
    )
    context = browser.new_context(
        storage_state=arquivo, user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
    )
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
        fechar_popups_e_avisos(page)

        try:
            page.locator(SELETOR_PLAY).first.click(timeout=8000)
            print(f"[Conta {n}] Botão de play clicado.")
        except Exception:
            print(f"[Conta {n}] Botão não achado, a tentar a tecla Espaço...")
            page.keyboard.press("Space")

        time.sleep(4)
        fechar_popups_e_avisos(page)

        tocando = musica_tocando(page)
        page.screenshot(path=f"captura_{n}.png")

        if not tocando:
            print(f"[Conta {n}] ERRO: a música não começou. "
                  f"Veja captura_{n}.png")
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
