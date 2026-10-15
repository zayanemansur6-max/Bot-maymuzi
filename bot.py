import json
from playwright.sync_api import sync_playwright

def executar_sessao(nome_conta, cookies_json, url_musica):
    print(f"\n========================================")
    print(f"🎵 A iniciar a automação para: {nome_conta}")
    print(f"========================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        if cookies_json:
            try:
                cookies = json.loads(cookies_json)
                context.add_cookies(cookies)
                print("🔑 Cookies injetados com sucesso!")
            except Exception as e:
                print(f"⚠️ Erro ao carregar os cookies: {e}")

        page = context.new_page()

        try:
            print(f"🌐 A aceder ao MyMuze...")
            page.goto(url_musica, timeout=60000)
            page.wait_for_load_timeout(5000)

            print("🔍 A verificar o pop-up do plano gratuito ('Continuar nas Estações')...")
            try:
                botao_estacoes = page.locator("text=Continuar nas Estações")
                if botao_estacoes.is_visible(timeout=5000):
                    print("👉 Pop-up detetado! A clicar...")
                    botao_estacoes.click()
                    page.wait_for_load_timeout(3000)
                else:
                    print("✅ Pop-up não visível. A prosseguir...")
            except Exception:
                print("ℹ️ Nenhuma intervenção necessária.")

            print("⏳ Música em reprodução na nuvem... A aguardar 90 segundos.")
            page.wait_for_load_timeout(90000)
            print(f"🏁 Sessão de {nome_conta} concluída com sucesso!")

        except Exception as e:
            print(f"❌ Ocorreu um erro: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    url_alvo = "https://api.prod.kuackmedia.com/share/mymuze/track/195833155?redirect=1"
    
    # COLE OS SEUS COOKIES AQUI DIRETAMENTE ENTRE AS ASPAS:
    cookie_conta1 = 'COLE_AQUI_O_TEXTO_DOS_COOKIES_DA_CONTA_1'
    cookie_conta2 = 'COLE_AQUI_O_TEXTO_DOS_COOKIES_DA_CONTA_2'

    if cookie_conta1 and cookie_conta1 != 'COLE_AQUI_O_TEXTO_DOS_COOKIES_DA_CONTA_1':
        executar_sessao("Conta 1", cookie_conta1, url_alvo)
    
    if cookie_conta2 and cookie_conta2 != 'COLE_AQUI_O_TEXTO_DOS_COOKIES_DA_CONTA_2':
        executar_sessao("Conta 2", cookie_conta2, url_alvo)
        
