# Narração híbrida: Google Chirp 3 HD e ElevenLabs

## Comportamento padrão

Com `AUDIO_TTS_MODE=auto`:

- Feed, Reels e Meta Ads usam Google Chirp 3 HD primeiro;
- TikTok e YouTube Shorts usam ElevenLabs primeiro;
- se o provedor principal falhar, o sistema tenta o segundo;
- nenhuma publicação é realizada durante a geração da locução.

Também é possível fixar um provedor:

```dotenv
AUDIO_TTS_MODE=chirp
```

ou:

```dotenv
AUDIO_TTS_MODE=elevenlabs
```

Com `AUDIO_TTS_FALLBACK=true`, o modo fixo define o provedor principal, mas
ainda permite usar o outro em caso de falha. Para proibir essa troca, configure
`AUDIO_TTS_FALLBACK=false`.

## Configuração do Google Chirp

1. Acesse `https://console.cloud.google.com/`.
2. Selecione o projeto que será usado pelo Guardian AI.
3. Abra **APIs e serviços → Biblioteca**.
4. Procure por **Cloud Text-to-Speech API**.
5. Clique em **Ativar**.
6. Abra **APIs e serviços → Credenciais**.
7. Crie uma chave de API exclusiva para o TTS.
8. Restrinja a chave à **Cloud Text-to-Speech API**.
9. Quando possível, restrinja também por IP do servidor.
10. Adicione ao arquivo oficial `.env` na raiz de `MKT_Guardian-AI`:

```dotenv
GOOGLE_CLOUD_TTS_API_KEY=cole_a_chave_aqui
GOOGLE_CLOUD_TTS_VOICE=pt-BR-Chirp3-HD-Aoede
```

Não envie a chave por chat, não a grave em documentação e não faça commit do
arquivo `.env`.

## Configuração da ElevenLabs

1. Acesse `https://elevenlabs.io/app/settings/api-keys`.
2. Revogue a chave que está retornando HTTP 401.
3. Crie uma chave exclusiva para o Guardian AI.
4. Limite a permissão ao Text-to-Speech, se o painel oferecer essa opção.
5. Adicione ao arquivo oficial `.env` na raiz de `MKT_Guardian-AI`:

```dotenv
ELEVENLABS_API_KEY=cole_a_nova_chave_aqui
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_VOICE_ID=id_da_voz_pt_br
```

O modelo `eleven_v3` deve ser ativado somente após teste de pronúncia e
compatibilidade com a voz escolhida.

## Configuração recomendada

```dotenv
AUDIO_TTS_MODE=auto
AUDIO_TTS_FALLBACK=true
AUDIO_TTS_MAX_CHARS=5000
```

O limite de caracteres evita chamadas inesperadamente grandes. O sistema não
inclui chaves em mensagens de erro e envia a chave Google em cabeçalho HTTPS.

## Validação

Depois de configurar pelo menos uma chave:

```bash
python3 -m unittest tests.test_hybrid_tts
python3 validate_criatividade.py
```

Em seguida, gere uma campanha sem publicação. O terminal mostrará a ordem dos
provedores e qual deles produziu a narração.
