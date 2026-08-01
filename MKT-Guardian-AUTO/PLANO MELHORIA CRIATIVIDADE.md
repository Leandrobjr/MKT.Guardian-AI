# Plano de Melhoria da Criatividade — MKT Guardian AUTO

**Objetivo:** elevar qualidade, diversidade e coerência dos posts — memória real de campanhas, headlines variadas, casting visual aspiracional (sem elitismo), golpes reais do dia a dia, e feedback que respeite a intenção do operador.

**Status:** Proposta — aguardando aprovação para implementação por fases.

**Referências:** `agent_memory.py`, `visual_variety.py`, `campaign_context_engine.py`, `campaign_orchestrator.py`, `feedback_router.py`, `contexto_negocio/GOLPES WHATSAPP.md`, `campanha_context_matrix.json`, `guardian_base.json`.

---

## 1. Diagnóstico (problemas confirmados no código)

### 1.1 Memória fraca — campanhas se repetem

| O que existe | Limitação |
|---|---|
| `correcoes_admin.jsonl` | Últimas 8 correções globais, sem filtro por combo |
| `aprovados.jsonl` | 3 headlines como “inspiração” — **não** blocklist |
| `rejeitados.jsonl` | Motivo genérico, sem extrair padrões |
| `imagens_prompts.jsonl` | Só fallback Gemini; **Kling ignora** |

**Efeito:** cada campanha “esquece” headlines, cenas, personagens e ângulos já usados.

### 1.2 Feedback não muda o tipo de estória

- Combo `publico_slug` + `golpe_id` é fixado no **menu** e nunca re-resolvido.
- Feedback (“quero estória de escola, não de mãe”) vira texto livre no prompt Gemini, **conflitando** com `campanha_context_matrix.json` (ex.: combo `pais+grooming` força narrativa parental).
- `feedback_router.py` não tem categoria **narrativa / ICP / troca de golpe**.

### 1.3 Headlines repetitivas

- Ganchos são listas **estáticas** por combo (3–5 frases fixas).
- `_sanitize_headline()` substitui headline “quebrada” por **`ganchos[0]`** — sempre a mesma manchete de fallback.
- Gemini recebe ganchos como “inspire-se, não copie” com `temperature=0.45` — tende a variações mínimas (só troca sujeito).
- Sem rotação: não há `headline_index` nem deduplicação de manchetes aprovadas.

### 1.4 Imagens com aparência “muito humilde”

Causas combinadas:

1. **`DIRETRIZES_VISUAIS`** fala em “working-class comfort” — LLMs de imagem interpretam como estética pobre.
2. **`PERSONAS_EXEMPLO`** pequeno (8 personas), profissões genéricas (“Dona de casa”, “Pai de família”).
3. **`_build_ambiente()`** enfatiza “not luxury, not poverty” mas modelos priorizam o primeiro sinal social.
4. Anti-repeat visual **não cobre Kling** (path principal de vídeo).
5. Cenas hardcoded em `campanha_context_matrix.json` repetem “mother checking daughter's phone, clean tidy home”.

**Direção desejada:** brasileiros relatable, **bem apresentados** — roupa casual limpa, casa organizada, aparência cuidada; classe média baixa/média; **sem** choque de pobreza **e sem** luxo.

### 1.5 Golpes reais subutilizados

- `GOLPES WHATSAPP.md` documenta **20 golpes**; o sistema opera **6** (`grooming`, `pix_fantasma`, `falso_parente`, etc.).
- Mensagens típicas do markdown **não estão indexadas** para rotação de `frase_golpista` e cards.
- Campanhas não sorteiam “variante do golpe #7 falso emprego” dentro do mesmo ICP.

---

## 2. Visão alvo (modelo de agência)

```
┌─────────────────────────────────────────────────────────────┐
│  OPERADOR (menu + feedback)                                  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CREATIVE BRIEF ENGINE (novo)                                │
│  • combo ICP×golpe + variante do golpe (GOLPES WHATSAPP)     │
│  • brief único: headline angle, cena, tom, proibições        │
│  • consulta histórico → evita repetição                       │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐
│ COPY AGENT       │  │ CASTING DIRECTOR │  │ SCAM LIBRARY  │
│ (Gemini)         │  │ (visual_variety+)│  │ (golpes JSON) │
└────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ CAMPAIGN HISTORY DB │
                    │ (JSONL → SQLite?)   │
                    │ headlines, hashes,  │
                    │ combos, assets      │
                    └─────────────────────┘
```

---

## 3. Melhorias propostas (por pilar)

### Pilar A — Memória de campanhas (anti-repetição)

**Novo módulo:** `campaign_history.py`

Registrar a cada campanha **aprovada ou gerada**:

```json
{
  "basename": "2_pais_imagem_2026-07-30",
  "publico": "pais",
  "golpe": "grooming",
  "headline": "O SEGREDO QUE...",
  "headline_hash": "abc123",
  "copy_hook": "primeiras 200 chars",
  "visual_hash": "sha256 prompt",
  "persona_id": "ana_professora_bh",
  "ambiente": "sala_tv",
  "frase_golpista": "...",
  "asset_path": "..."
}
```

**Injetar no prompt:**

- `HEADLINES JÁ USADAS (NÃO REPETIR): ...` — filtradas por combo
- `CENAS JÁ USADAS: ...` — últimos N visual_hash
- `ROTEIRO: use ângulo diferente dos listados`

**Evolução:** `format_for_prompt(publico, golpe)` em `agent_memory.py` — memória **contextual**, não global.

### Pilar B — Rotação e diversidade de headlines

1. **`HeadlineRotator`** em `creative_brief.py`:
   - Sorteia gancho base do combo **excluindo** os usados nos últimos X dias.
   - Passa ao Gemini: “transforme este gancho mantendo o ângulo, mas com palavras novas”.

2. **Reformular `_sanitize_headline()`:**
   - Em vez de `ganchos[0]`, usar **próximo gancho não usado** ou pedir regeneração ao Gemini.

3. **Expandir ganchos** em `campanha_context_matrix.json`:
   - Mínimo **8–12 ganchos** por combo, derivados de `GOLPES WHATSAPP.md`.

4. **Subir temperature** copy para **0.65–0.75** na geração de headline; manter 0.45 na validação JSON.

### Pilar C — Casting visual (“bem vestidos”, mundo real)

1. **Atualizar `DIRETRIZES_VISUAIS` e prompts:**

```
APPEARANCE STANDARD (mandatory):
- Subjects look neat, groomed, clean casual clothing (pressed t-shirt, simple blouse, 
  clean jeans or chinos) — middle-income Brazilian aesthetic.
- Home: organized, painted walls, decent furniture — NOT luxury, NOT poverty signals 
  (no cracked walls, no visibly worn clothes, no dirty environments).
- Relatable professionals and parents — teacher, nurse, shop owner, office clerk.
```

2. **Expandir `PERSONAS_EXEMPLO`** para **24+ personas** com:
   - `estilo_vestuario`, `ambiente_preferido`, `nivel_socioeconomico: "classe_media_baixa" | "classe_media"`
   - Profissões diversas alinhadas ao ICP

3. **`VisualCastingDirector`** (evolução de `visual_variety.py`):
   - Escolhe persona **não usada** nos últimos 5 runs do mesmo `publico_slug`
   - Registra prompt Kling **e** Gemini em `imagens_prompts.jsonl`
   - Retry automático se hash repetir (até 2 tentativas)

4. **Ambientes rotativos** em `_build_ambiente()`:
   - Lista de 6+ cenários por ICP (sala de TV, varanda, home office simples, cozinha americana limpa) — evitar sempre “cozinha”.

### Pilar D — Biblioteca de golpes (GOLPES WHATSAPP.md)

1. **Converter** `GOLPES WHATSAPP.md` → `contexto_negocio/golpes_whatsapp.json` estruturado:

```json
{
  "id": "falso_pedido_pix",
  "titulo": "Falso Pedido de PIX",
  "mensagens_tipicas": ["Troquei de número...", "..."],
  "publicos_ideais": ["pais", "idosos", "massa"],
  "icp_tags": ["familiar", "urgencia"],
  "direcao_visual": "..."
}
```

2. **Mapear** golpes atuais (`golpe_id`) → entradas do JSON (1:N).

3. **Por campanha:** sortear `variante_golpe` dentro do tipo (ex.: grooming → mensagem A vs B do doc).

4. **Injetar no prompt:** trecho literal “mensagem real observada no Brasil” + link conceitual ao item do markdown.

### Pilar E — Feedback inteligente (respeitar intenção do operador)

1. **Estender `feedback_router.py`:**

| Intenção detectada | Ação |
|---|---|
| `narrativa` / “outra estória”, “escola”, “idoso” | Re-resolve contexto ou sugere trocar menu |
| `headline` / “manchete”, “título” | Regera só headline + overlay |
| `visual` / “aparência”, “roupa”, “pobre” | Regera casting + prompt visual |
| `golpe` / “outro golpe”, “PIX”, “link” | Troca `variante_golpe` ou alerta para mudar menu |

2. **Modo “override narrativo”** (Etapa melhoria):
   - Se operador escreve “QUERO ESTÓRIA DE ESCOLA”: setar flag `narrative_override` temporário que **sobrescreve** matriz por 1 geração (não conflitar prompts).

3. **Registrar correção** com tags: `[visual]`, `[headline]`, `[narrativa]` para memória filtrada.

### Pilar F — Orquestração criativa (evitar monotonia)

1. **Sugestão pós-campanha:** “Próximo combo recomendado: idosos + falsa_central (não usado há 12 dias)”.

2. **Dashboard terminal** (simples): últimas 10 campanhas com combo + headline.

3. **Opcional futuro:** fila de campanhas com rotação automática ICP×golpe.

---

## 4. Fases de implementação

### Fase 0 — Quick wins (1–2 dias) ⚡ ✅ Concluída (2026-07-30)

| # | Tarefa | Arquivo(s) | Status |
|---|---|---|---|
| 0.1 | Reforçar diretriz visual “bem apresentado, sem pobreza” | `guardian_base.json`, `_build_ambiente()`, `visual_variety.py` | ✅ |
| 0.2 | Registrar prompts Kling em `imagens_prompts.jsonl` | `mkt_agent_01.py` | ✅ |
| 0.3 | `format_for_prompt(publico, golpe)` filtrado | `agent_memory.py`, orchestrator | ✅ |
| 0.4 | Headline fallback: rotação `ganchos[i]` + gancho prioritário | `campaign_orchestrator.py` | ✅ |
| 0.5 | Temperature copy 0.7 | `campaign_orchestrator.py` | ✅ |

**Versão:** Orquestrador v4.7 | Fábrica v18.5

---

### Fase 1 — Histórico de campanhas (3–4 dias) ✅ Concluída (2026-08-01)

| # | Tarefa | Entregável | Status |
|---|---|---|---|
| 1.1 | Criar `campaign_history.py` | JSONL `campanhas_historico.jsonl` | ✅ |
| 1.2 | Registrar ao aprovar + ao gerar asset | hooks em orchestrator | ✅ |
| 1.3 | API `get_recent(combo, limit)` + `is_headline_used()` | consultas | ✅ |
| 1.4 | Bloco prompt `ANTI-REPETIÇÃO` | injeção automática | ✅ |
| 1.5 | Testes unitários dedup headline/hash | `tests/test_campaign_history.py` | ✅ |

**Versão:** Orquestrador v5.0 | Fábrica v18.8

---

### Fase 2 — Headlines e ganchos (2–3 dias) ✅ Concluída (2026-08-01)

| # | Tarefa | Entregável | Status |
|---|---|---|---|
| 2.1 | Expandir ganchos (8+ por combo) de GOLPES WHATSAPP | `campanha_context_matrix.json` | ✅ |
| 2.2 | `HeadlineRotator` | `creative_brief.py` | ✅ |
| 2.3 | Pós-validação: rejeitar headline >70% similar à última | Jaccard em `apply_headline_diversity` | ✅ |
| 2.4 | Log `headline_escolhida` no histórico | `campaign_history.py` | ✅ |

**Versão:** Orquestrador v5.1 | Fábrica v18.9

---

### Fase 3 — Casting visual (3–4 dias)

| # | Tarefa | Entregável |
|---|---|---|
| 3.1 | 24 personas enriquecidas | `guardian_base.json` |
| 3.2 | `VisualCastingDirector.pick_persona()` anti-repeat | `visual_variety.py` |
| 3.3 | 6 ambientes rotativos por ICP | `campaign_orchestrator.py` |
| 3.4 | Retry Kling/Gemini se hash duplicado | `mkt_agent_01.py` |
| 3.5 | QA visual: checklist terminal pós-geração | log opcional |

---

### Fase 4 — Biblioteca de golpes (4–5 dias)

| # | Tarefa | Entregável |
|---|---|---|
| 4.1 | Parser MD → `golpes_whatsapp.json` | script ou manual curado |
| 4.2 | `ScamLibrary.pick_variant(golpe_id, publico)` | `scam_library.py` |
| 4.3 | Integrar mensagens no card + phone clause | orchestrator |
| 4.4 | Novos `golpe_id` prioritários: link malicioso, falso emprego, investimento | menu + matriz |

---

### Fase 5 — Feedback e override narrativo (3 dias)

| # | Tarefa | Entregável |
|---|---|---|
| 5.1 | Categorias narrativa/golpe/visual/headline | `feedback_router.py` |
| 5.2 | `narrative_override` temporário | orchestrator |
| 5.3 | Correções tagueadas na memória | `agent_memory.py` |
| 5.4 | Mensagem clara quando pedido conflita com menu | UX terminal |

---

### Fase 6 — Inteligência contínua (opcional, 5+ dias)

- SQLite local para histórico + queries
- Sugestão automática próximo combo
- Métricas: taxa de MELHORAR por motivo
- A/B de headlines (futuro, com tráfego)

---

## 5. Priorização recomendada

```
Fase 0 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 4 ──► Fase 5 ──► Fase 6
  ⚡           🔥         🔥         🎨         📚         💬         📊
```

**MVP criativo (2 semanas):** Fases 0 + 1 + 2 + 3  
**Completude narrativa/golpes:** + Fase 4 + 5

---

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Gemini ignora anti-repeat | Validação pós-geração + retry com seed diferente |
| Kling cara em retries | Máx. 1 retry; fallback Gemini still |
| Prompt muito longo | Resumir histórico (últimos 5, não 50) |
| Override narrativo quebra produto | Guardrails `PRODUTO_E_POSICIONAMENTO` sempre injetados |
| Mais golpes = menu complexo | Sub-variantes automáticas; menu continua 6 tipos |

---

## 7. Critérios de sucesso (KPIs criativos)

| Métrica | Meta |
|---|---|
| Headlines idênticas em 5 campanhas mesmo combo | 0 |
| Similaridade headline >70% vs anterior | <20% dos casos |
| Feedback “estória errada” após MELHORAR | <10% |
| Operador pede troca de aparência/pobreza | <5% |
| Campanhas usando mesma frase_golpista seguidas | 0 em 3+ runs |
| Tempo extra por campanha | +≤30s (memória local) |

---

## 8. Próximo passo

1. **Aprovar** este plano e ordem das fases.
2. **Implementar Fase 0** (quick wins) — menor risco, ganho imediato.
3. Validar com **3 campanhas** `pais+grooming` e **3** `idosos+falso_parente`.
4. Iterar Fase 1 com base nos testes.

---

*Documento criado em 2026-07-30 — complementa `MELHORIAS FUTURAS.md`.*
