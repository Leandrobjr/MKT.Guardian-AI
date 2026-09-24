# MKT Guardian AI — Fábrica Automatizada de Campanhas

**Versão atual:** Orquestrador v5.71 · Fábrica de Mídia v18.12
**Produto:** [Guardian AI](https://guardian-ai.app)
**Diretório principal:** `MKT-Guardian-AUTO`

Este README é a documentação técnica operacional do sistema. O mesmo conteúdo
também é mantido no `README.md` da raiz do projeto.

## 1. Objetivo

O sistema produz campanhas para o aplicativo Guardian AI, combinando estratégia,
copy, geração de imagem e vídeo, narração, composição gráfica, QA e aprovação
humana antes de qualquer publicação.

## 2. Arquitetura atual

```text
Desktop ───────┐
               ├─► Supabase: fila de criação ─► Worker Linux
Telegram ──────┘                                      │
                                                      ▼
                                      Orquestrador + IA + Fábrica de mídia
                                                      │
                                                      ▼
                                  Campanha aguardando aprovação humana
                                                      │
                                                      ▼
                              Desktop: aprovar, rejeitar ou solicitar ajuste
                                                      │
                                                      ▼
                              Worker: publicação autorizada ou bloqueada
```

### Componentes principais

| Componente | Responsabilidade |
|---|---|
| `campaign_orchestrator.py` | Coordena contexto, copy, produção, QA e estados |
| `campaign_context_engine.py` | Resolve a matriz público × golpe |
| `campaign_contract.py` e catálogo | Valida combinações, gênero, nexo e consequências |
| `mkt_agent_01.py` | Gera e compõe imagem, vídeo, áudio, cards, CTA e logo |
| `visual_quality_audit.py` | Executa QA visual determinística e multimodal |
| `opencode_client.py` | Usa DeepSeek via OpenCode para estratégia, copy e visão |
| `hybrid_tts.py` | Alterna Google Chirp 3 HD e ElevenLabs |
| `supabase_campaign_bridge.py` | Integração backend com Supabase |
| `campaign_command_worker.py` | Processa criações, decisões editoriais e publicações |
| `desktop/` | Interface autenticada de criação e aprovação |
| `telegram_bot.py` | Wizard móvel `/nova` e notificações |
| `meta_publisher.py` | Publicação opcional no Instagram/Meta |
| `kling_client.py` | Cliente de geração de vídeo Kling |

## 3. Stack tecnológico

- Python 3.12+ em ambiente virtual `venv`;
- Google GenAI SDK;
- DeepSeek V4 Flash Vision Exp via OpenCode como agente primário;
- Gemini 3.6 Flash como fallback para texto e QA;
- Gemini 2.5 Flash Image para geração de imagem;
- Kling AI para vídeo, com fallback para composição estática;
- Google Chirp 3 HD e ElevenLabs para narração híbrida;
- Pillow e FFmpeg para composição, normalização e multiplexação;
- Supabase Auth, PostgreSQL, Storage e RLS;
- JavaScript modular no Desktop, usando somente chave publicável.

O Gemini 3.6 é modelo de texto/visão neste projeto. A geração de imagem usa
`GEMINI_MODEL_IMAGEM=gemini-2.5-flash-image`; não existe
`gemini-3.6-flash-image` configurado.

## 4. Como criar uma campanha

### 4.1 Desktop — fluxo principal

1. Inicie a interface Desktop.
2. Informe URL do Supabase e chave publicável.
3. Faça login com perfil `ACTIVE` e papel `ADMIN`.
4. No painel **Criar campanha**, selecione público, golpe, mídia, canal e
   objetivo.
5. Confirme o envio.
6. A solicitação entra em `mkt_campaign_creation_requests`.
7. O worker Linux gera o criativo e executa a QA.
8. A campanha aparece como `AGUARDANDO_APROVACAO_FINAL`.

O navegador apenas cria uma solicitação ou comando autorizado pela sessão. Ele
não altera diretamente o status da campanha.

### 4.2 Telegram

1. Envie `/nova` ao bot.
2. Siga as seis etapas do wizard.
3. Confirme o resumo.
4. Com `SUPABASE_CAMPAIGN_SYNC=true`, a configuração entra na mesma fila do
   Desktop.
5. O resultado é revisado e aprovado no Desktop.

Sem a ponte Supabase, o modo legado do bot pode executar o pipeline localmente,
conforme o fluxo configurado. Para produção, recomenda-se usar a fila central.

## 5. Seis parâmetros de campanha

| Etapa | Opções principais |
|---|---|
| Público | Idosos, pais, empresários ou escolas |
| Golpe | Falso parente, PIX, falsa central, grooming, phishing, clonagem, link malicioso, falso emprego ou falso investimento |
| Mídia | Imagem estática ou vídeo comercial |
| Canal | Meta Ads ou TikTok/YouTube Shorts |
| Objetivo | Instalação do aplicativo ou geração de leads |
| Pós-geração | Revisão humana pelo Desktop |

Imagem estática quadrada é validada para Meta Ads. Vídeos verticais podem usar
Meta Reels ou TikTok/YouTube Shorts. O upload para TikTok continua manual.

## 6. Pipeline de produção

1. **Contexto:** a matriz canônica define persona, cena, gancho, frase do
   golpista e CTA.
2. **Estratégia e copy:** DeepSeek via OpenCode gera ou revisa a estrutura;
   Gemini 3.6 assume quando necessário.
3. **Guardrails:** o sistema corrige gênero, nexo, mecanismo financeiro,
   consequência, vocativo e promessas incompatíveis com o produto.
4. **Imagem:** Gemini Image produz uma base sem texto essencial incorporado.
5. **Vídeo:** Kling produz o movimento quando solicitado.
6. **Narração:** Chirp 3 HD e ElevenLabs são roteados por canal, com fallback.
7. **Composição:** Pillow/FFmpeg aplicam headline, cards, logo, CTA e URL.
8. **Áudio:** FFmpeg executa normalização EBU R128 e mixagem com trilha.
9. **QA:** a campanha é bloqueada para publicação se houver texto inventado,
   telefone duplicado, mockup ampliado, tela cortada, artefato ou incoerência.
10. **Aprovação:** somente um humano pode liberar a campanha.

## 7. Estados e publicação

Estados relevantes:

`GERANDO` · `PRODUZIDA` · `AGUARDANDO_APROVACAO_FINAL` ·
`AJUSTE_SOLICITADO` · `APROVADA` · `REJEITADA` · `PUBLICANDO` ·
`PUBLICADA` · `ERRO_PUBLICACAO`.

Uma publicação só é aceita quando há:

- status remoto `APROVADA`;
- `aprovado_por` preenchido;
- QA multimodal aprovada;
- asset local válido;
- comando `PUBLISH` confirmado pelo usuário.

Campanhas TikTok não recebem publicação automática; são exportadas para upload
manual.

## 8. Supabase e segurança

A integração utiliza:

- `mkt_campaign_creation_requests` para novas campanhas;
- `mkt_campaigns` para campanhas e assets;
- `mkt_campaign_commands` para decisões e publicação;
- bucket privado `mkt-campaign-assets`;
- RLS para usuários autenticados com perfil administrativo.

Regras obrigatórias:

- o navegador usa somente `SUPABASE_PUBLISHABLE_KEY`;
- `SUPABASE_SERVICE_ROLE_KEY` fica exclusivamente no Linux/worker;
- tokens não são salvos em tabelas, logs ou código;
- o `.env` oficial fica na raiz do projeto;
- não publique `.env` nem arquivos gerados no Git;
- em produção, hospede o Desktop com HTTPS;
- valide tipo, tamanho e caminho dos assets.

## 9. Execução local

```bash
cd ~/Documentos/Guardian-AI/MKT_Guardian-AI/MKT-Guardian-AUTO
source venv/bin/activate
```

Para abrir o Desktop:

```bash
python3 -m http.server 8081 --bind 127.0.0.1 --directory desktop
```

Abra `http://127.0.0.1:8081`. Se a porta estiver ocupada, escolha outra livre.

Para iniciar o bot:

```bash
python3 telegram_bot.py
```

Para executar o orquestrador pelo terminal:

```bash
python3 campaign_orchestrator.py
```

## 10. Worker Linux contínuo

```bash
mkdir -p ~/.config/systemd/user
cp deploy/guardian-campaign-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now guardian-campaign-worker.service
```

Verificação:

```bash
systemctl --user status guardian-campaign-worker.service
journalctl --user -u guardian-campaign-worker.service -f
```

O worker usa lock contra concorrência, recupera solicitações abandonadas após
30 minutos e consulta a fila a cada 15 segundos.

Para simular comandos sem executar:

```bash
python3 campaign_command_worker.py
```

O modo contínuo exige `--execute`. Isso processa a fila, mas não publica
automaticamente: a publicação depende de aprovação humana e de um comando
`PUBLISH`.

## 11. Testes e diagnóstico

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile campaign_orchestrator.py campaign_command_worker.py
python3 validate_criatividade.py
```

Diagnósticos auxiliares:

```bash
python3 elevenlabs_check.py
python3 kling_diagnostico.py
python3 descobrir_chat_id.py
```

## 12. Estrutura resumida

```text
MKT-Guardian-AUTO/
├── campaign_orchestrator.py
├── campaign_command_worker.py
├── campaign_catalog.py
├── campaign_revision_service.py
├── desktop/
├── deploy/
├── supabase/migrations/
├── tests/
├── contexto_negocio/
├── trilhas_sonoras/
└── .env.example
```

## 13. Próxima etapa planejada

O próximo item funcional é criar anúncios Meta com CTA realmente clicável e
destino `https://guardian-ai.app` pela Meta Ads API. O texto do card continuará
sendo apenas reforço visual; o destino clicável será configurado no anúncio.
