# Melhorias Futuras — MKT Guardian AUTO

Arquivo de lembrete para evoluções **não urgentes** da Fábrica de Campanhas.
Anote aqui ideias, justificativas e passos de implementação para retomar depois.

**Formato sugerido por item:**
- Status (Pendente / Em andamento / Concluído)
- Contexto e justificativa
- Quando implementar
- Como fazer (passos técnicos)
- Arquivos e variáveis envolvidas

---

## 1. Publicação de imagem estática (JPEG) no Feed do Instagram

**Status:** Pendente

### Contexto

Hoje, ao escolher **"[1] Imagem Estática Premium"** no orquestrador, o fluxo:

1. Gera a imagem com Gemini
2. Aplica layout Pillow → `.jpg`
3. Monta **MP4** (imagem + áudio + overlay) via FFmpeg
4. Na publicação, `_resolve_primary_asset()` **prioriza o `.mp4`** sobre o `.jpg`
5. O `meta_publisher.py` publica o MP4 como **Reel** (upload resumável)

Ou seja: **imagem estática no pipeline vira Reel**, não post de foto no Feed.

A publicação de **JPEG puro no Feed** só ocorre se:
- o MP4 **não** for gerado (`commercial_video_file` = `"Não solicitado"` ou ausente), **e**
- existir `static_image_file` com `.jpg` válido.

Nesse caso, o `meta_publisher.postar_imagem()` exige hospedar a imagem em URL pública via **ImgBB** (`IMGBB_API_KEY`), pois a Meta Graph API não aceita upload direto de arquivo local para imagens — apenas `image_url` pública.

### Justificativa para implementar depois

| Motivo | Detalhe |
|---|---|
| Fluxo atual funciona | Imagem estática → MP4 → Reel publicado com sucesso (testado jul/2026) |
| IMGBB é dependência extra | Conta, API key e serviço externo só necessários para Feed com JPEG |
| Caso de uso distinto | Feed (foto quadrada) vs Reels (vídeo vertical/narrado) — nem toda campanha precisa dos dois |
| Fallback natural | Se FFmpeg falhar, o `.jpg` já existe; falta só configurar IMGBB |

**Implementar quando:** houver campanha que exija **post de foto no Feed** (sem Reel), ou quando quiser escolher explicitamente "publicar JPG" vs "publicar MP4/Reel".

### Como fazer

#### Passo 1 — Obter chave ImgBB

1. Criar conta em [https://api.imgbb.com/](https://api.imgbb.com/)
2. Copiar a **API Key**
3. Adicionar no `.env` da Fábrica (`MKT-Guardian-AUTO/.env` ou raiz do clone):

```env
IMGBB_API_KEY=sua_chave_aqui
```

#### Passo 2 — Testar publicação manual de JPEG

```bash
cd ~/Documentos/Guardian-AI/MKT_Guardian-AI/MKT-Guardian-AUTO
python3 << 'PY'
from meta_publisher import MetaPublisher
p = MetaPublisher()
r = p.postar_imagem(
    "output_campanha/NOME_DA_CAMPANHA.jpg",  # .jpg final com layout, não _base.jpg
    "Legenda de teste #guardianai"
)
print(r)
PY
```

Esperado: `✅ [ImgBB] Imagem hospedada: ...` → `✅ [Meta] Imagem publicada! ID: ...`

#### Passo 3 (opcional) — Escolha Feed vs Reel no orquestrador

Hoje `_resolve_primary_asset()` em `campaign_orchestrator.py` sempre prefere vídeo:

```python
# Ordem atual: vídeo → imagem
video = assets.get("commercial_video_file", "")
...
imagem = assets.get("static_image_file", "")
```

**Opções de evolução:**

- **A)** Nova opção na Etapa 6: `[5] Publicar JPG no Feed (sem Reel)` — força `static_image_file`
- **B)** Flag em config da campanha: `publicar_como: "reel" | "feed" | "auto"`
- **C)** Se canal = Meta Feed Ads, preferir JPG; se Reels, preferir MP4

#### Passo 4 — Validar na conta

- Confirmar post em **@guardian_ai.app** → aba **Feed** (não Reels)
- Verificar permalink via Graph API:

```bash
curl -s "https://graph.facebook.com/v21.0/IG_MEDIA_ID?fields=permalink,media_type&access_token=$META_ACCESS_TOKEN"
```

### Arquivos envolvidos

| Arquivo | Papel |
|---|---|
| `meta_publisher.py` | `postar_imagem()` + `_upload_para_imgbb()` — **já implementado** |
| `campaign_orchestrator.py` | `_resolve_primary_asset()` — **decide o que publicar** |
| `mkt_agent_01.py` | Gera `_base.jpg`, layout final `.jpg` e MP4 estático |
| `.env.example` | Documentar `IMGBB_API_KEY` (já existe) |

### Pré-requisitos Meta (mesmos do Reel)

```env
META_ACCESS_TOKEN=...
META_IG_USER_ID=17841446969970987
```

Token com `instagram_content_publish` e `instagram_basic`.

---

## 2. Melhoria da criatividade e memória de campanhas (macro)

**Status:** Planejado — ver documento completo

**Arquivo:** [`PLANO MELHORIA CRIATIVIDADE.md`](PLANO%20MELHORIA%20CRIATIVIDADE.md)

**Resumo:** memória anti-repetição, rotação de headlines, casting visual (aparência bem apresentada), biblioteca de golpes reais (`GOLPES WHATSAPP.md`), feedback que respeita tipo de estória. Implementação em 6 fases (0–6); MVP em ~2 semanas (Fases 0–3).

---

*Última atualização: 2026-07-30*
