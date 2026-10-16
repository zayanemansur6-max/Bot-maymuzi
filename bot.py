import time
from playwright.sync_api import sync_playwright

COOKIES_CONTA_1 = "_ga=GA1.1.1221982072.1792109445;_ga_3E78078BSL=GS2.1.s1792109445$o1$g1$t1792110063$j60$l0$h0"
COOKIES_CONTA_2 = "_ga=GA1.1.1221982072.1792109445;_ga_3E78078BSL=GS2.1.s1792109445$o1$g1$t1792110547$j58$l0$h0"

def parse_cookies(cookie_string, domain="mymuze.vm.co.mz"):
    cookies = []
    for item in cookie_string.split(";"):
        if "=" in item:
            name, value = item.strip().split("=", 1)
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/"
            })
    return cookies

def fechar_popups_e_avisos(page):
    """
    Tenta fechar ou aceitar pop-ups, termos, planos e banners de navegação.
    Não gera erro caso nenhum esteja presente.
    """
    # Lista de textos e seletores comuns de botões de pop-ups/banners
    textos_botoes = [
        "Aceitar", "Concordar", "Continuar", "Entendi", 
        "Continuar no plano", "Continuar nas estações", "Continuar com plano",
        "Fechar", "OK", "Skip", "Ignorar"
    ]
    
    for texto in textos_botoes:
        try:
            # Procura botões com os textos acima e clica se estiverem visíveis
            botao = page.locator(f"text=/{texto}/i")
            if botao.count() > 0 and botao.first.is_visible():
                print(f"--> Pop-up/Aviso detetado. A clicar em: '{texto}'")
                botao.first.click(timeout=3000)
                time.sleep(1)
        except Exception:
            pass # Se não encontrar ou já tiver saído, ignora silenciosamente

def run_bot(cookie_string, account_name):
    print(f"\n==========================================")
    print(f"A iniciar processo para: {account_name}")
    print(f"==========================================")
    
    with sync_playwright() as p:
        # Lançar o navegador em modo headless (no GitHub Actions)
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-notifications"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Adicionar cookies de sessão
        context.add_cookies(parse_cookies(cookie_string))
        
        page = context.new_page()
        
        # Aceitar automaticamente diálogos nativos do navegador (ex: alertas)
        page.on("dialog", lambda dialog: dialog.accept())
        
        try:
            print("A carregar o MyMuze...")
            page.goto("https://mymuze.vm.co.mz/index.html#/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            
            # Limpar pop-ups iniciais de entrada/termos/planos
            fechar_popups_e_avisos(page)
            
            # Garantir reprodução ou clicar no botão Play se existir
            print("A procurar elementos de reprodução/estação...")
            fechar_popups_e_avisos(page) # Segunda verificação caso surja outro aviso
            
            # Tentar clicar no primeiro botão de Play visível
            play_btn = page.locator(".play-button, .btn-play, [aria-label*='Play'], [aria-label*='Tocar']").first
            if play_btn.is_visible():
                play_btn.click()
                print("Botão Play clicado com sucesso!")
            
            # Manter a sessão ativa e a tocar durante o tempo desejado (ex: 2 minutos por conta)
            print("Música em reprodução. A aguardar reprodução...")
            time.sleep(120) 
            
            print(f"Sucesso! Sessão concluída sem erros para {account_name}.")

        except Exception as e:
            print(f"Erro capturado na execução de {account_name}: {e}")
            # Tira uma captura de ecrã para debug no GitHub Actions se algo falhar
            page.screenshot(path=f"erro_{account_name}.png")
            
        finally:
            browser.close()

if __name__ == "__main__":
    run_bot(COOKIES_CONTA_1, "Conta_1")
    time.sleep(5)
    run_bot(COOKIES_CONTA_2, "Conta_2")
            
