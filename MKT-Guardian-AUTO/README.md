# Descritivo Técnico do Sistema - Fábrica de Mídia Guardian-AI (v15.0)

Este documento descreve de forma analítica e profissional a arquitetura, o stack tecnológico e o pipeline automatizado de geração de ativos de marketing (imagens e vídeos de alta conversão) para o aplicativo de segurança cibernética **Guardian-AI**.

---

## 1. Stack Tecnológico Atual

A aplicação opera sobre uma infraestrutura modular em Python 3.12, utilizando APIs de última geração para orquestração de inteligência artificial generativa e manipulação de mídia em baixo nível.

* **Linguagem Base:** Python 3.12+ (executado em ambiente virtual isolado `venv`).
* **Orquestração Visual & Prompts:** `google-genai` (utilizando o modelo `gemini-3.1-flash-lite`).
* **Geração de Imagem Base:** `google-genai` (utilizando o modelo `gemini-3.1-flash-image`).
* **Geração de Vídeo Nativo:** API Kling AI (Gateway Internacional de Singapura, modelo **Kling 3.0 Turbo**).
* **Locução Profissional (TTS):** API ElevenLabs (Modelo `eleven_multilingual_v2`).
* **Renderização Gráfica Headless:** `playwright` (Chromium Headless) para injeção de layouts HTML5/CSS3 (TailwindCSS).
* **Processamento e Multiplexação de Mídia:** `FFmpeg` (via subprocessos nativos do Linux).
* **Gerenciamento de Ambiente:** `python-dotenv` para isolamento seguro de credenciais.

---

## 2. Pipeline de Execução Detalhado (Etapa por Etapa)

O fluxo de trabalho foi refatorado para garantir o isolamento completo entre as mídias estáticas e dinâmicas, eliminando duplicidades no orquestrador e blindando o sistema contra textos distorcidos em línguas estrangeiras.

### Etapa 1: Ingestão de Dados e Geração de Áudio
1. O orquestrador envia os dados criativos coletados (gancho inicial, copy e público-alvo).
2. O sistema expande o texto em uma narrativa de alta conversão adaptada para os limites do Instagram Reels/Meta Ads.
3. O texto é enviado à API da ElevenLabs para gerar a voz institucional limpa.
4. O FFmpeg captura a voz gerada, varre a pasta `trilhas_sonoras/musicas_suspense` de forma dinâmica, sorteia uma faixa e faz a mixagem de fundo (aplicando atenuação de `-24dB` na trilha para dar o peso psicológico necessário, sem gerar ruídos ou distorções).

### Etapa 2: Isolamento de Fluxo e Direção de Arte
O sistema divide o caminho de execução dependendo da escolha do usuário no menu principal:

#### Fluxo A: Imagem Estática Premium
1. O Gemini gera um prompt publicitário estrito focado na mãe determinado/protetora e na filha (Mariana) visível ao fundo, com iluminação de estúdio high-end.
2. A imagem pura e limpa (totalmente livre de textos distorcidos) é gerada pelo Gemini Image.
3. O Playwright abre uma instância invisível do navegador, monta um layout HTML com TailwindCSS, renderiza a imagem de fundo, desenha a Headline de impacto no topo, injeta o card de notificação real do **Guardian-AI** em português perfeito no centro e insere o botão vermelho de conversão na base.
4. Um screenshot em alta definição (`.jpg` com 98% de qualidade) é salvo.

#### Fluxo B: Vídeo em Movimento Cinematográfico (Kling 3.0 Turbo)
1. O sistema envia uma requisição HTTP direta usando a API Key como Bearer Token estático para o endpoint oficial de Singapura.
2. O payload é estruturado com o prompt de estúdio publicitário focado em proteção infantil contra grooming, configurado nativamente na proporção vertical `9:16`.
3. O sistema entra em um ciclo de monitoramento (*polling*) a cada 10 segundos na rota de tarefas até que o servidor retorne o status de sucesso e o link do MP4 bruto.
4. O vídeo em movimento limpo é baixado para a pasta local.

### Etapa 3: Composição Sequencial por Frames (Solução Definitiva)
Para garantir que as mensagens em português do Brasil fiquem nítidas e não sofram distorções no vídeo, o motor aplica a engenharia de renderização frame a frame:
1. O FFmpeg explode o vídeo bruto baixado da Kling AI em frames sequenciais de imagem de alta qualidade.
2. O Playwright entra em ação: para cada frame extraído, o navegador headless projeta o frame como background e renderiza por cima dele a interface real, com as fontes corporativas da marca e o link oficial.
3. O navegador salva o frame processado. Esse ciclo se repete para toda a sequência do vídeo.
4. O FFmpeg é acionado uma última vez para juntar todos os frames processados de volta em um fluxo de vídeo a 25 quadros por segundo, embutindo simultaneamente o arquivo de áudio final (Voz + Trilha Sonora).
5. O cache de frames é limpo por segurança, entregando o arquivo `anuncio_video_final.mp4` pronto para veiculação no Meta Ads.
