# JJMC

O JJMC é um utilitário avançado e leve escrito em Python que permite rotear o tráfego do aplicativo Discord através de proxies (HTTP/SOCKS) de forma transparente.

Projetado inicialmente com foco em usuários da América Latina, o JJMC resolve problemas de conectividade e protege a identidade do usuário, tudo isso sem sacrificar a qualidade das chamadas de voz e vídeo.

## Recursos

### Motor Automático: 
Vasculha APIs públicas em tempo real em busca de servidores proxy gratuitos localizados no Cone Sul (Brasil, Argentina, Chile, Uruguai, etc.), filtrando conexões de alta latência e conectando você ao IP mais rápido disponível (< 150ms).

### Memória Inteligente: 
O programa salva os "campeões" de velocidade localmente. Ao religar o software, ele testa seus IPs favoritos primeiro. Se o ping estiver abaixo de 300ms, ele conecta instantaneamente, poupando a rede e evitando Rate Limits em APIs públicas.

### Split Tunneling: 
Engenharia de rede de nível empresarial. Mensagens de texto, login e imagens passam 100% pelo proxy, mantendo sua identidade oculta. No entanto, o tráfego sensível de Voz, Vídeo e Transmissão de Tela (WebRTC) é direcionado para a sua conexão direta. Resultado: Zero carregamento infinito e chamadas com ping perfeito (0 lag).

### Modo Manual: 
Suporte total para a injeção de proxies privados/pagos.

### Utilitário Silencioso: 
Consome virtualmente 0% de CPU e menos de 20MB de RAM enquanto repousa na Bandeja do Sistema (System Tray) do Windows.

### Cross-Platform: 
Arquitetura adaptada para funcionar perfeitamente em ambientes Windows e distribuições Linux (com fallback nativo de GUI).

## Instalação e Uso

Para Usuários Comuns (Windows)

Você não precisa instalar o Python ou entender de código.

Vá até a aba Releases deste repositório (ou acesse a pasta dist se estiver clonando).

Baixe o arquivo ``JJMC.exe

Dê um duplo clique para abrir. O programa ficará minimizado ao lado do relógio do Windows.

Escolha entre "Modo Automático" ou insira seu IP no "Modo Manual" e clique em Ligar Proxy. O Discord será reiniciado automaticamente já sob a nova rede.

Nota: O Windows Defender pode exibir um alerta de segurança na primeira execução (Falso Positivo). Isso ocorre porque o software altera os parâmetros de execução do processo do Discord. Basta clicar em "Mais informações" e "Executar assim mesmo".

Para Desenvolvedores (Rodando do código-fonte)

Clone o repositório:

``git clone https://github.com/DevP3try/JJMC.git


Instale as dependências da interface gráfica:

``pip install PyQt6


Execute o motor principal:

``python JJMC.py


### Como Compilar (.exe)

Se você fez alterações no código e deseja gerar o seu próprio arquivo executável:

#### Instale o empacotador
``pip install pyinstaller

#### Gere o executável silencioso
``python -m PyInstaller --noconsole --onefile JJMC.py


O arquivo final estará disponível na pasta dist/.

## Como funciona o motor por trás dos panos?

O JJMC não mexe em configurações de proxy globais do Windows (que afetariam seu navegador ou jogos). Em vez disso, ele injeta variáveis de ambiente (HTTP_PROXY, HTTPS_PROXY) e flags de inicialização do Chromium (--proxy-server, --proxy-bypass-list) diretamente no isolamento do processo do Discord, garantindo que apenas o aplicativo seja roteado.

## Aviso Legal

Este software foi desenvolvido para fins educacionais e de pesquisa em redes. O uso de proxies gratuitos está sujeito à estabilidade de servidores de terceiros. Os desenvolvedores não se responsabilizam pelo tráfego gerado pelo usuário através do aplicativo.