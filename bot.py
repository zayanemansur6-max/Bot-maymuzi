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

JS_CARTAO = """e => {
  let c = e;
  while (c.parentElement && (c.getBoundingClientRect().width < 120
         || c.getBoundingClientRect().height < 120)) c = c.parentElement;
  const r = c.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2,
          w: Math.round(r.width), h: Math.round(r.height),
          cls: (c.className + '').slice(0, 40)};
}"""

JS_TOPO = """([x, y]) => {
  const t = document.elementFromPoint(x, y);
  return t ? t.tagName + '.' + (t.className + '').slice(0, 40) : null;
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
        if m.type == "error":
            eventos.append("console: " + m.text[:110])

    page.on("response", resp)
    page.on("console", cons)


def clicar_play(page, n):
    alvo = page.locator(SELETOR_PLAY)
    total = alvo.count()
    print(f"[Conta {n}] Botões de play encontrados: {total}")

    for idx in range(min(total, 6)):
        el = alvo.nth(idx)
        try:
            el.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass

        card = None
        try:
            card = el.evaluate(JS_CARTAO)
            page.mouse.move(card["x"], card["y"])
            time.sleep(0.8)
        except Exception:
            pass

        try:
            visivel = el.is_visible()
        except Exception:
            visivel = False
        box = None
        try:
            box = el.bounding_box()
        except Exception:
            pass
        topo = None
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            try:
                topo = page.evaluate(JS_TOPO, [cx, cy])
            except Exception:
                pass
        print(f"[Conta {n}] Play #{idx + 1}: visível={visivel} "
              f"cartão={card and (card['w'], card['h'])} "
              f"caixa={box and (round(box['x']), round(box['y']))} "
              f"topo={topo}")

        metodo = None
        try:
            el.click(timeout=3000)
            metodo = "normal"
        except Exception:
            if box:
                page.mouse.click(cx, cy)
                metodo = "mouse"
        if not metodo:
            continue

        time.sleep(4)
        modais = modais_visiveis(page)
        if modais:
            print(f"[Conta {n}]   pop-ups após o clique: {modais}")
        fechar_popups_e_avisos(page)

        if esta_tocando(page):
            print(f"[Conta {n}] Play #{idx + 1} funcionou ({metodo}).")
            return True
        print(f"[Conta {n}]   clicado ({metodo}), mas sem som.")
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
