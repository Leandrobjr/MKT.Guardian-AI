# MKT Guardian AI — Fábrica Automatizada de Campanhas Digitais

**Versão do sistema:** Orquestrador v4.5 · Fábrica de Mídia v18.4  
**Produto promovido:** [Guardian AI](https://guardian-ai.app) — proteção inteligente contra golpes no WhatsApp  
**Repositório:** MKT-Guardian-AUTO (dentro do projeto MKT.Guardian-AI)

---

## Visão geral

O **MKT Guardian AI** é uma plataforma de automação de marketing digital desenvolvida para produzir, em escala, campanhas publicitárias de alta conversão voltadas ao aplicativo **Guardian AI**. O sistema combina inteligência artificial generativa, síntese de voz profissional, geração de imagem e vídeo, composição gráfica automatizada e fluxos de aprovação humana — tudo orquestrado a partir de um servidor Linux dedicado.

Em termos práticos: o operador escolhe **para quem** falar, **qual golpe** abordar e **em qual canal** veicular; a fábrica entrega criativos prontos (imagem e/ou vídeo com narração, cards visuais e call-to-action), com narrativa coerente ao contexto da campanha e alinhada às capacidades reais do produto.

---

## O problema que resolve

Agências e equipes de growth enfrentam três gargalos ao escalar campanhas de apps de segurança digital:

1. **Repetição de narrativas** — o mesmo roteiro de “proteja sua família” aparece em campanhas para escolas, empresários e idosos, reduzindo conversão.
2. **Custo e tempo de produção** — cada vídeo exige copywriter, designer, locutor, editor e revisão; APIs de vídeo e voz têm custo por unidade.
3. **Risco de mensagem incorreta** — prometer funcionalidades que o app não possui (ex.: monitorar grupos de WhatsApp) gera reprovação, reclamações e desperdício de mídia.

O MKT Guardian AI automatiza a produção mantendo **contexto por público × tipo de golpe**, **verdade do produto** e **aprovação humana antes de gastar com mídia cara**.

---

## O que o sistema faz

| Capacidade | Descrição |
|------------|-----------|
| **Geração de copy persuasiva** | Roteiros em framework PAS (Problema → Agitação → Solução), manchetes de impacto, CTAs e mensagens simuladas de golpistas no WhatsApp |
| **Contexto inteligente por campanha** | Narrativa, ganchos, cena visual e CTA adaptados à combinação público-alvo + tipo de golpe (ex.: escolas + grooming ≠ pais + PIX) |
| **Produção de imagem estática** | Fotos publicitárias geradas por IA (formato feed 1:1) com overlay de marca: headline, card de alerta, card Guardian AI e botão de conversão |
| **Produção de vídeo comercial** | Vídeos verticais 9:16 com narração ElevenLabs, trilha sonora, movimento (Kling AI ou fallback estático) e identidade visual Guardian |
| **Presets por canal** | Meta Reels (tom pausado, ~32s), TikTok/Shorts (urgente, ~18s) ou feed quadrado — cada um com voz, trilha e layout calibrados |
| **Aprovação da estória (pré-produção)** | Valida roteiro e contexto **antes** de gerar vídeo/áudio, economizando APIs |
| **Aprovação do criativo final** | Via terminal ou bot Telegram: aprovar, melhorar ou rejeitar |
| **Memória de aprendizado** | Registra correções, aprovações e rejeições para refinar campanhas futuras |
| **Publicação Instagram** | Integração opcional com Meta Graph API (Reels e imagens) após aprovação |
| **Estrutura de tráfego Meta** | Mapeamento técnico de segmentação (idade, interesses) para campanhas pagas |

---

## Como funciona — fluxo operacional

### Entrada: wizard de 6 etapas

O operador configura a campanha escolhendo:

| Etapa | Escolha | Efeito no criativo |
|-------|---------|-------------------|
| 1 | **Público-alvo (ICP)** | Idosos, pais, empresários, escolas |
| 2 | **Tipo de golpe** | PIX, falso parente, grooming, phishing, clonagem, falsa central |
| 3 | **Tipo de mídia** | Imagem estática (feed) ou vídeo animado (Reels/Shorts) |
| 4 | **Canal de veiculação** | Meta Ads (pausado) ou TikTok/YouTube Shorts (urgente) |
| 5 | **Objetivo de conversão** | Instalação do app ou geração de leads |
| 6 | **Fluxo pós-criação** | Aprovação Telegram e/ou publicação automática no Instagram |

### Pipeline automatizado

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ Motor de        │     │ Agente Criativo  │     │ Aprovação da        │
│ Contexto        │ ──► │ (Gemini)         │ ──► │ Estória (opcional)  │
│ público × golpe │     │ copy + roteiro   │     │ terminal / Telegram │
└─────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                              │
┌─────────────────┐     ┌──────────────────┐                  ▼
│ Entrega final   │ ◄── │ Composição visual│ ◄── ┌─────────────────────┐
│ MP4 / JPG + MP3 │     │ cards + CTA      │     │ Fábrica de Mídia      │
└─────────────────┘     └──────────────────┘     │ voz · imagem · vídeo  │
         │                                        └─────────────────────┘
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Aprovação do    │ ──► │ Publicação       │
│ criativo        │     │ Instagram (opt.) │
└─────────────────┘     └──────────────────┘
```

**Detalhamento das fases:**

1. **Resolução de contexto** — O `Campaign Context Engine` consulta a matriz `campanha_context_matrix.json` e define protagonista, ganchos, frase do golpista, direção de arte e CTA para aquela combinação específica.

2. **Geração criativa** — O Gemini produz JSON estruturado: manchete, roteiro de narração, mensagem do card golpista, personagem visual e CTA. Guardrails impedem jargão técnico e violações das capacidades reais do Guardian AI.

3. **Enforcement de verdade do produto** — Pós-processamento garante que a copy não prometa bloqueio de mensagens, monitoramento de grupos ou funcionalidades inexistentes.

4. **Aprovação da estória** — Quando ativada (`STORY_APPROVAL=1`), o operador revisa headline, roteiro, card golpista e cena **sem consumir APIs de vídeo/voz**. Pode aprovar, melhorar (reescrever) ou rejeitar.

5. **Produção de mídia** — A Fábrica de Mídia executa:
   - Narração via **ElevenLabs** (voz neural multilíngue)
   - Mixagem com trilha (suspense ou corporativa)
   - Imagem base via **Gemini Image**
   - Vídeo via **Kling AI 3.0 Turbo** (com fallback para vídeo estático + zoom Ken Burns)
   - Overlay gráfico (headline + 2 cards + botão CTA) via **Pillow/FFmpeg**

6. **Aprovação do criativo** — Preview enviado ao Telegram ou exibido no terminal. Feedback “Melhorar” regera copy ou recomposição visual (até 3 revisões).

7. **Publicação** — Opcionalmente, postagem no Instagram via Meta Graph API.

---

## Públicos-alvo e tipos de campanha

### Públicos (ICP)

- **Idosos / aposentados** — proteção de economias contra falso parente e falsa central
- **Pais e responsáveis** — grooming, aliciamento e segurança dos filhos no WhatsApp privado
- **Empresários / comerciantes** — golpes PIX, boletos falsos e WhatsApp Business
- **Dirigentes e educadores escolares** — conscientização de famílias, grooming em chat privado, phishing disfarçado de secretaria

### Tipos de golpe abordados

Falso parente · Golpe do PIX · Falsa central bancária · Grooming / aliciamento · Phishing · Clonagem de WhatsApp

Cada combinação **público + golpe** possui narrativa, frases-modelo e direção visual próprias — evitando campanhas genéricas ou fora de contexto.

---

## Diferenciais competitivos

- **Contexto narrativo por matriz** — Não depende apenas do LLM “adivinhar” o público; regras de negócio em JSON garantem coerência.
- **Verdade do produto hardcoded** — Capacidades e limitações do Guardian AI injetadas no prompt e no pós-processamento.
- **Dupla aprovação** — Estória antes da produção cara; criativo antes da publicação.
- **Variedade visual** — Engine alterna persona, iluminação, enquadramento e gênero do protagonista entre campanhas.
- **Layout profissional ad-safe** — Cards compactos na faixa inferior; rosto, mãos e celular permanecem visíveis no quadro.
- **Operação remota** — Bot Telegram para configurar campanhas e aprovar criativos a partir do celular.
- **Memória persistente** — Correções do administrador alimentam campanhas futuras.

---

## Arquitetura de módulos

| Módulo | Função |
|--------|--------|
| `campaign_orchestrator.py` | Orquestrador principal — menu, pipeline, aprovações |
| `campaign_context_engine.py` | Motor de contexto público × golpe |
| `mkt_agent_01.py` (MediaFactory) | Fábrica de mídia — áudio, imagem, vídeo, overlay |
| `channel_presets.py` | Presets técnicos por canal (Meta, TikTok, feed) |
| `tts_narration.py` | Normalização de roteiro e textos fixos dos cards |
| `visual_variety.py` | Diversidade visual entre campanhas |
| `video_compositor.py` | Pipeline FFmpeg (overlay PNG + áudio + vídeo Kling) |
| `telegram_bot.py` / `telegram_approval.py` | Bot e fluxo de aprovação via Telegram |
| `story_approval.py` | Formatação da aprovação pré-produção |
| `meta_publisher.py` | Publicação no Instagram (Meta Graph API) |
| `traffic_manager.py` | Estruturação de segmentação Meta Ads |
| `agent_memory.py` | Memória de correções e aprovações |
| `feedback_router.py` | Classificação de feedback “Melhorar” |
| `kling_client.py` | Cliente API Kling AI para geração de vídeo |

### Base de conhecimento (`contexto_negocio/`)

- `guardian_base.json` — ICPs, golpes, guardrails, identidade visual, capacidades do produto
- `campanha_context_matrix.json` — Overrides narrativos por combinação público × golpe
- `GOLPES WHATSAPP.md` — Base educativa sobre fraudes
- `PLANO MKT Guardian AUTO.md` — Estratégia editorial e calendário
- `memoria/` — Histórico de correções, aprovações e rejeições

---

## Stack tecnológico

### Núcleo

| Camada | Tecnologia |
|--------|------------|
| Linguagem | Python 3.12+ |
| Ambiente | Linux (servidor dedicado), virtualenv |
| Configuração | python-dotenv (`.env`) |
| Orquestração de IA | Google GenAI SDK (`google-genai`) |

### Inteligência artificial

| Função | Serviço / Modelo |
|--------|------------------|
| Copy e roteiro | Gemini 3.1 Flash Lite |
| Geração de imagem | Gemini 3.1 Flash Image |
| Geração de vídeo | Kling AI 3.0 Turbo (API internacional) |
| Narração (TTS) | ElevenLabs Multilingual v2 |
| Segmentação de tráfego | Gemini (estrutura JSON Meta Ads) |

### Mídia e composição

| Função | Tecnologia |
|--------|------------|
| Overlay gráfico (cards, CTA) | Pillow (PIL) |
| Composição de vídeo | FFmpeg (libx264, AAC, zoompan, overlay PNG) |
| Movimento em fallback | Ken Burns orgânico (video_motion) |
| Trilhas sonoras | Biblioteca local (`trilhas_sonoras/`) |

### Integrações e publicação

| Canal | Tecnologia |
|-------|------------|
| Aprovação remota | Telegram Bot API |
| Instagram | Meta Graph API v21.0 + ImgBB (hospedagem temporária de imagem) |
| Meta Ads (estrutura) | facebook-business SDK |
| TikTok | Preset de produção ativo; API de postagem em configuração |

### Dependências principais

```
google-genai · Pillow · requests · python-dotenv · facebook-business · PyJWT · playwright*
```

\* Playwright disponível para fluxos legados; pipeline atual usa Pillow + FFmpeg.

---

## Formatos de saída

Arquivos gerados em `output_campanha/`:

| Arquivo | Descrição |
|---------|-----------|
| `{seq}_{publico}_{midia}_{data}.mp4` | Vídeo comercial final (quando solicitado) |
| `{seq}_{publico}_{midia}_{data}.jpg` | Imagem com overlay completo |
| `{seq}_{publico}_{midia}_{data}_base.jpg` | Imagem base sem overlay |
| `{seq}_{publico}_{midia}_{data}.mp3` | Narração + trilha mixada |

**Formatos por canal:**

- Feed Instagram/Facebook: **1080×1080** (1:1)
- Reels / TikTok / Shorts: **1080×1920** (9:16)

---

## Canais de operação

### Terminal (servidor Linux)

Execução direta do orquestrador com menu interativo — indicado para operação estável e diagnóstico.

### Bot Telegram

Wizard completo das 6 etapas, aprovação da estória, aprovação do criativo e notificações de erro — indicado para operação mobile.

---

## Segurança e governança

- Credenciais isoladas em `.env` (nunca versionado no Git)
- Lock de instância única do bot (evita conflitos de aprovação)
- Validação de `job_id` em callbacks Telegram (evita aprovar previews obsoletos)
- Guardrails de idade e gênero coerentes com a narrativa
- Proibições visuais (sem ambientes de pobreza extrema, sem stock genérico, sem telas de outros apps)
- Práticas OWASP aplicáveis: sem exposição de secrets, validação de inputs, tokens com escopo mínimo

---

## Infraestrutura recomendada

- **SO:** Linux (Ubuntu/Debian)
- **Runtime:** Python 3.12+, FFmpeg instalado
- **Rede:** Acesso às APIs Google, ElevenLabs, Kling, Meta e Telegram
- **Armazenamento:** Espaço para vídeos em `output_campanha/` e cache de trabalho
- **Deploy:** `git pull origin main` + limpeza de `__pycache__`

---

## Roadmap de integrações

| Integração | Status |
|------------|--------|
| Geração copy + mídia | ✅ Produção |
| Aprovação estória + criativo | ✅ Produção |
| Bot Telegram | ✅ Produção |
| Publicação Instagram | ✅ Opcional (requer tokens Meta) |
| Estrutura Meta Ads | ✅ Dry-run / JSON de segmentação |
| Publicação TikTok (Content Posting API) | 🔜 Em configuração (domínio + tokens) |
| YouTube Shorts API | 📋 Planejado |

---

## Proposta de valor para o negócio

O MKT Guardian AI transforma uma operação de marketing que exigiria **equipe multidisciplinar e dias por criativo** em um **pipeline automatizado de minutos**, com:

- Escala para **3–5 peças por dia** (meta editorial do plano de 90 dias)
- **Custo previsível** por API, com checkpoint de aprovação antes de gastos maiores
- **Consistência de marca** Guardian AI em todos os touchpoints visuais
- **Adaptação por segmento** sem perder a voz autoritária e urgente da marca

Ideal para **lançamento e escala do Guardian AI** em Meta Ads, Reels, TikTok e YouTube Shorts, com foco em conversão para instalação do app ([guardian-ai.app](https://guardian-ai.app)).

---

## Contato e links

- **Produto:** [https://guardian-ai.app](https://guardian-ai.app)
- **Repositório:** MKT.Guardian-AI (GitHub)
- **Documentação técnica complementar:** `README.md` (pipeline e stack detalhado)

---

*Documento gerado para apresentação institucional e base de conteúdo para site corporativo. Atualizar conforme evolução das versões do orquestrador e da fábrica de mídia.*
