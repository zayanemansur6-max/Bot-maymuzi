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

SELETOR_PLAY = (
    '.play-button, .btn-play, .play-btn, [class*="play" i], '
    '[id*="play" i], [title*="play" i], [title*="tocar" i], '
    '[aria-label*="play" i], [aria-label*="tocar" i]'
)


def clicar_texto_exato(page, texto, espera=2):
    """Clica num elemento visível cujo texto é exatamente 'texto'."""
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
    # 1) Pop-up de plano: escolher a opção gratuita
    if clicar_texto_exato(page, r"Continuar nas esta[cç][õo]es", espera=3):
        print(f"[Conta {n}] Pop-up: 'Continuar nas estações' clicado.")
    # 2) Aba Estações
    if clicar_texto_exato(page, r"Esta[cç][õo]es", espera=3):
        print(f"[Conta {n}] Aba 'Estações' aberta.")


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


def diagnostico(page, n):
    print(f"[Conta {n}] --- DIAGNÓSTICO ---")
    try:
        print("URL:", page.url)
        texto = page.inner_text("body").replace("\n", " | ")
        print("TEXTO:", texto[:600])
        midias = page.evaluate(
            """() => [...document.querySelectorAll('audio,video')].map(m => ({
                tag: m.tagName, paused: m.paused, t: m.currentTime,
                src: (m.currentSrc || '').slice(0, 60)}))"""
        )
        print("MIDIAS:", midias)
        itens = page.evaluate(
            """() => [...document.querySelectorAll(
                'button, a, [role=button], [onclick]')]
                .filter(e => e.offsetParent !== null)
                .slice(0, 40)
                .map(e => [e.tagName.toLowerCase(),
                    (e.className || '').toString().slice(0, 40),
                    e.getAttribute('aria-label') || '',
                    (e.innerText || '').trim().slice(0, 25)].join(' ~ '))"""
        )
        print("BOTÕES VISÍVEIS (tag ~ classe ~ aria-label ~ texto):")
        for i in itens:
            print("  ", i)
    except Exception as e:
        print("diagnóstico falhou:", e)


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
        ir_para_estacoes(page, n)
        fechar_popups_e_avisos(page)

        try:
            page.locator(SELETOR_PLAY).filter(visible=True).first.click(
                timeout=8000)
            print(f"[Conta {n}] Botão de play clicado.")
        except Exception:
            print(f"[Conta {n}] Botão não achado, a tentar a tecla Espaço...")
            page.keyboard.press("Space")

        time.sleep(4)
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
