import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

URL_ALVO = "https://mymuze.vm.co.mz/index.html#/home"
TOTAL_CONTAS = 7
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

# Elementos das estações de rádio (parte gratuita)
SELETORES_ESTACAO = [
    '[class*="tag-station-player-icon-wrap"]',
    '[class*="tag-station-radio"]',
]

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

JS_CAIXA = """e => {
  const r = e.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2,
          w: Math.round(r.width), h: Math.round(r.height)};
}"""

JS_MODAIS = """() => [...document.querySelectorAll(
    '[class*=modal i], [class*=popup i], [class*=dialog i], '
    + '[role=dialog], [class*=overlay i]')]
  .filter(e => e.offsetParent !== null && e.innerText.trim())
  .slice(0, 3)
  .map(e => e.innerText.trim().replace(/\\n/g, ' | ').slice(0, 200))"""


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


def modais_visiveis(page):
    try:
        return page.evaluate(JS_MODAIS)
    except Exception:
        return []


def ligar_vigias(page, eventos):
    def resp(r):
        try:
            url = r.url
            ct = r.headers.get("content-type") or ""
            media = ("audio" in ct or "mpegurl" in ct or any(
                x in url.lower()
                for x in (".mp3", ".m4a", ".aac", ".m3u8", ".mpd", ".ogg")))
            if media or r.status >= 400:
                eventos.append(f"{r.status} {ct[:18]} {url[:90]}")
        except Exception:
            pass

    def cons(m):
        if m.type == "error" and "Content Security Policy" not in m.text:
            eventos.append("console: " + m.text[:110])

    page.on("response", resp)
    page.on("console", cons)


def tentar_detalhe(page, n):
    """Se abriu a página da estação, clica no play visível dela."""
    opcoes = (
        page.locator("a.play-actions-play").filter(visible=True),
        page.get_by_text(re.compile(r"^\s*Reproduzir\s*$", re.I)).filter(
            visible=True),
    )
    for loc in opcoes:
        try:
            if loc.count() > 0:
                loc.first.click(timeout=3000)
                time.sleep(4)
                fechar_popups_e_avisos(page)
                if esta_tocando(page):
                    return True
        except Exception:
            pass
    return False


def clicar_play(page, n):
    url_lista = page.url
    for seletor in SELETORES_ESTACAO:
        alvo = page.locator(seletor)
        total = alvo.count()
        print(f"[Conta {n}] '{seletor}': {total} encontrados")
        if total == 0:
            continue
        try:
            html = alvo.first.evaluate(
                "e => (e.parentElement || e).outerHTML.slice(0, 500)")
            print(f"[Conta {n}] HTML da estação: {html}")
        except Exception:
            pass

        for idx in range(min(total, 4)):
            el = alvo.nth(idx)
            try:
                el.evaluate(
                    "e => e.scrollIntoView({block:'center', inline:'center'})")
                time.sleep(1)
                c = el.evaluate(JS_CAIXA)
            except Exception as e:
                print(f"[Conta {n}] Estação #{idx + 1}: erro {str(e)[:60]}")
                continue
            print(f"[Conta {n}] Estação #{idx + 1}: tamanho={c['w']}x{c['h']}")

            for metodo in ("mouse", "direto"):
                try:
                    if metodo == "mouse":
                        page.mouse.move(c["x"], c["y"])
                        time.sleep(0.5)
                        page.mouse.click(c["x"], c["y"])
                    else:
                        el.evaluate("e => e.click()")
                except Exception:
                    continue
                time.sleep(4)

                modais = modais_visiveis(page)
                if modais:
                    print(f"[Conta {n}]   pop-ups após o clique: {modais}")
                fechar_popups_e_avisos(page)

                if esta_tocando(page):
                    print(f"[Conta {n}] Estação #{idx + 1} tocou ({metodo}).")
                    return True

                if page.url != url_lista:
                    print(f"[Conta {n}]   o clique abriu: {page.url}")
                    if tentar_detalhe(page, n):
                        print(f"[Conta {n}] Tocou pela página da estação.")
                        return True
                    page.go_back()
                    time.sleep(3)
                    break
                print(f"[Conta {n}]   clique ({metodo}): sem som.")
    return False


def diagnostico(page, n, eventos):
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
        print("REDE/ERROS (últimos 12):")
        for e in eventos[-12:]:
            print("  ", e)
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
    eventos = []
    ligar_vigias(page, eventos)

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
            diagnostico(page, n, eventos)
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
