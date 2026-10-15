import os
import json
from playwright.sync_api import sync_playwright

def executar_sessao(nome_conta, cookies_json, url_musica):
    print(f"\n========================================")
    print(f"🎵 A iniciar a automação para: {nome_conta}")
    print(f"========================================\n")

    with sync_playwright() as p:
        # Inicia o navegador em modo invisível (headless) na nuvem
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Se houver cookies guardados, injeta-os para manter a sessão logada
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
            
            # Aguarda um momento para a página carregar
            page.wait_for_load_timeout(5000)

            # Lógica inteligente: Verifica se aparece o pop-up "Continuar nas Estações"
            print("🔍 A verificar o pop-up do plano gratuito ('Continuar nas Estações')...")
            try:
                # Procura o botão pelo texto ou seletor
                botao_estacoes = page.locator("text=Continuar nas Estações")
                if botao_estacoes.is_visible(timeout=5000):
                    print("👉 Pop-up detetado! A clicar em 'Continuar nas Estações'...")
                    botao_estacoes.click()
                    page.wait_for_load_timeout(3000)
                else:
                    print("✅ O pop-up não apareceu (já está na zona livre/logada). A prosseguir...")
            except Exception:
                print("ℹ️ Nenhuma intervenção do pop-up necessária.")

            # Mantém a simulação de reprodução por 90 segundos
            print("⏳ Música em reprodução na nuvem... A aguardar 90 segundos.")
            page.wait_for_load_timeout(90000)
            print(f"🏁 Sessão de {nome_conta} concluída com sucesso!")

        except Exception as e:
            print(f"❌ Ocorreu um erro durante a execução da {nome_conta}: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    # Lê os dados seguros configurados no GitHub Secrets
    url_alvo = "https://api.prod.kuackmedia.com/share/mymuze/track/195833155?redirect=1"
    
    cookie_conta1 = os.environ.get("COOKIE_CONTA_1", "")
    cookie_conta2 = os.environ.get("COOKIE_CONTA_2", "")

    if cookie_conta1:
        executar_sessao("Conta 1", cookie_conta1, url_alvo)
    else:
        print("⚠️ COOKIE_CONTA_1 não configurado.")

    if cookie_conta2:
        executar_sessao("Conta 2", cookie_conta2, url_alvo)
    else:
        print("⚠️ COOKIE_CONTA_2 não configurado.")
      
