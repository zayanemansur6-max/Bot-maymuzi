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

SELETOR_PLAY = "a.play-actions-play"

# Guarda qualquer áudio/vídeo que o site tente tocar
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


def na_tela_de_login(page):
    try:
        t = page.inner_text("body").lower()
    except Exception:
        return False
    return "introduz o código" in t or "novo dispositivo" in t


def musica_tocando(page):
    try:
        return page.evaluate(
            """() => [...(window.__medias || []),
                ...document.querySelectorAll('audio, video')]
                .some(m => !m.paused && m.currentTime > 0)"""
        )
    except Exception:
        return False


def pause_visivel(page):
    try:
        return page.locator('[class*="pause" i]').filter(
            visible=True).count() > 0
    except Exception:
        return False


def esta_tocando(page):
    return musica_tocando(page) or pause_visivel(page)


def clicar_play(page, n):
    alvo = page.locator(SELETOR_PLAY)
    total = alvo.count()
    print(f"[Conta {n}] Botões de play encontrados: {total}")
    if total == 0:
        return False

    for idx in range(min(total, 3)):
        el = alvo.nth(idx)
        try:
            el.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        try:
            # passa o mouse no cartão (o botão pode só aparecer assim)
            el.locator("xpath=../..").hover(timeout=3000)
        except Exception:
            pass

        for metodo in ("normal", "forçado", "direto"):
            try:
                if metodo == "normal":
                    el.click(timeout=3000)
                elif metodo == "forçado":
                    el.click(timeout=3000, force=True)
                else:
                    el.evaluate("e => e.click()")
            except Exception as e:
                print(f"[Conta {n}] Play #{idx + 1} ({metodo}) falhou: "
                      f"{str(e)[:60]}")
                continue
            time.sleep(4)
            fechar_popups_e_avisos(page)
            if esta_tocando(page):
                print(f"[Conta {n}] Play #{idx + 1} funcionou ({metodo}).")
                return True
            print(f"[Conta {n}] Play #{idx + 1} ({metodo}) clicado, "
                  "mas sem som ainda.")
    return False


def diagnostico(page, n):
    print(f"[Conta {n}] --- DIAGNÓSTICO ---")
    try:
        print("URL:", page.url)
        midias = page.evaluate(
            """() => [...(window.__medias || []),
                ...document.querySelectorAll('audio, video')].map(m => ({
                tag: m.tagName, paused: m.paused, t: m.currentTime,
                ready: m.readyState, erro: m.error ? m.error.code : null,
                src: (m.currentSrc || '').slice(0, 80)}))"""
        )
        print("MIDIAS (erro 4 = formato não suportado):", midias)
        info = page.evaluate(
            """() => {
                const q = s => [...document.querySelectorAll(s)];
                const caixa = e => {
                    const r = e.getBoundingClientRect();
                    return Math.round(r.width) + 'x' + Math.round(r.height);
                };
                const p = q('a.play-actions-play')[0];
                return {
                  play_total: q('a.play-actions-play').length,
                  play_primeiro_tamanho: p ? caixa(p) : null,
                  play_primeiro_html: p ? p.outerHTML.slice(0, 200) : null,
                  com_pause: q('[class*=pause i]').map(
                      e => (e.className + '').slice(0, 40)).slice(0, 8),
                  com_player: q('[class*=player i]').map(
                      e => (e.className + '').slice(0, 40)).slice(0, 8),
                };
            }"""
        )
        for k, v in info.items():
            print(f"  {k}: {v}")
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
        time.sleep(2)

        tocando = clicar_play(page, n)
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
