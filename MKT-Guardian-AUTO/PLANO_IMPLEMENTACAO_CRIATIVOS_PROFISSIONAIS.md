# Plano de Implementação — Criativos Profissionais Guardian AI

## 1. Objetivo

Transformar a fábrica de campanhas em um sistema capaz de produzir criativos com qualidade profissional para:

- Instagram Feed;
- Instagram Reels;
- Facebook;
- TikTok;
- YouTube Shorts.

O objetivo não é apenas gerar imagens bonitas. Cada campanha deverá ter:

- uma história clara;
- um personagem adequado ao público;
- uma cena coerente;
- ritmo adequado ao canal;
- texto legível;
- identidade visual consistente;
- áudio compreensível;
- chamada para ação;
- aprovação humana antes da publicação.

## 2. Situação atual

O projeto já possui:

- geração de copy com Gemini;
- geração de imagem com Gemini Image;
- geração de vídeo com Kling;
- narração com ElevenLabs;
- composição com Pillow e FFmpeg;
- presets diferentes para Meta e TikTok;
- aprovação da história;
- aprovação do criativo final via Telegram ou terminal;
- histórico de campanhas;
- biblioteca de golpes;
- rotação de headlines e personagens.

O projeto ainda precisa melhorar:

- qualidade visual percebida;
- consistência dos personagens;
- construção de cenas;
- storyboard;
- avaliação automática;
- variedade real de anúncios;
- templates profissionais;
- catálogo de campanhas;
- aprovação pelo Desktop;
- publicação e registro dos resultados.

## 3. Decisão sobre o stack

Não substituir todo o stack imediatamente.

### Stack principal recomendado

- Gemini 3.6 Flash: estratégia, roteiro, storyboard, análise e controle de qualidade;
- Gemini Image: geração de imagens-base;
- Kling: geração e animação de vídeos;
- ElevenLabs: narração;
- Pillow/FFmpeg: textos, cards, logo, mixagem e acabamento;
- Supabase: catálogo, fila, arquivos e resultados;
- Open Design ou HyperFrames: templates e motion design determinístico.

O Open Design não substitui diretamente Gemini, Kling ou ElevenLabs. Ele deve ser avaliado como uma camada de design, composição e padronização visual.

### Testes futuros

Comparar, com o mesmo brief e as mesmas referências:

- Kling;
- Veo;
- Seedance;
- Gemini Image;
- outros modelos de imagem, se necessário.

Nenhum fornecedor será trocado sem teste comparativo.

## 4. Fluxo final desejado

```text
Configurar campanha
        ↓
Validar público, mídia e canal
        ↓
Criar brief criativo
        ↓
Criar copy e storyboard
        ↓
Aprovar história
        ↓
Gerar imagens, vídeo e áudio
        ↓
Executar controle automático de qualidade
        ↓
Aprovar criativo final
        ↓
Salvar como pronto para publicação
        ↓
Escolher publicação automática ou manual
        ↓
Publicar na rede selecionada
        ↓
Registrar resultado e métricas
```

## 5. Fases de implementação

### Fase 0 — Diagnóstico e medição

Antes de trocar ferramentas:

1. Selecionar 10 campanhas recentes.
2. Avaliar cada uma de 0 a 5.
3. Registrar os motivos das notas baixas.

Critérios:

- qualidade da imagem;
- aparência profissional;
- coerência com o público;
- clareza da história;
- legibilidade;
- qualidade da voz;
- qualidade do movimento;
- força da chamada para ação;
- adequação ao canal;
- potencial comercial.

Resultado: descobrir se o problema principal está no modelo, no prompt, na composição ou no processo.

### Fase 1 — Brief criativo estruturado

Criar um brief único antes da geração.

O brief deverá conter:

- objetivo da campanha;
- público;
- golpe;
- dor principal;
- promessa;
- personagem;
- cenário;
- emoção;
- estilo visual;
- canal;
- duração;
- formato;
- texto que será inserido posteriormente;
- restrições;
- chamada para ação.

O brief será usado por todos os agentes. Copy, imagem, vídeo e voz não deverão receber instruções conflitantes.

### Fase 2 — Validação de mídia e canal

Bloquear combinações inadequadas antes de consumir APIs.

Regras iniciais:

- imagem quadrada: Instagram/Facebook Feed;
- vídeo vertical: Instagram Reels;
- vídeo vertical: TikTok;
- vídeo vertical: YouTube Shorts.

Se o usuário escolher uma combinação inadequada, o sistema deverá explicar o motivo e solicitar uma nova escolha.

Também deverá salvar no registro:

- preset usado;
- resolução;
- proporção;
- duração;
- ritmo;
- tipo de trilha;
- velocidade da narração.

### Fase 3 — Storyboard profissional

Para vídeos, gerar de 3 a 5 cenas.

Exemplo:

1. situação de risco;
2. mensagem suspeita no WhatsApp;
3. reação do personagem;
4. alerta do Guardian AI;
5. chamada para ação.

Cada cena deverá conter:

- duração;
- enquadramento;
- movimento;
- ação;
- emoção;
- texto permitido;
- transição;
- objetivo narrativo.

### Fase 4 — Casting e referências visuais

Criar uma biblioteca de referências aprovadas:

- personagens;
- roupas;
- ambientes;
- iluminação;
- enquadramentos;
- paleta;
- estilo fotográfico;
- exemplos aceitos;
- exemplos rejeitados.

As imagens devem mostrar brasileiros bem apresentados e realistas, sem estética de pobreza e sem luxo artificial.

O sistema deverá evitar:

- repetição de personagem;
- repetição de cenário;
- rostos deformados;
- mãos erradas;
- ambientes incoerentes;
- personagem incompatível com o roteiro.

### Fase 5 — Geração em múltiplas etapas

O sistema não deverá aceitar automaticamente a primeira geração.

Processo:

1. gerar brief;
2. gerar copy;
3. gerar storyboard;
4. gerar duas ou três imagens-base;
5. avaliar as imagens;
6. selecionar a melhor;
7. gerar o vídeo;
8. gerar áudio;
9. compor o criativo;
10. avaliar o resultado final.

Vídeo Kling deverá receber uma imagem aprovada e instruções de movimento específicas, em vez de depender apenas de texto.

### Fase 6 — Templates de composição

Criar templates específicos para cada canal.

Cada template deverá controlar:

- área segura;
- posição do logo;
- tamanho do texto;
- hierarquia visual;
- cards;
- CTA;
- cores;
- animações;
- duração;
- proporção.

Textos importantes não deverão ser gerados dentro da imagem ou do vídeo por IA. Eles deverão ser inseridos depois por Pillow, HTML/Canvas ou FFmpeg.

Open Design ou HyperFrames poderá ser usado nesta fase para motion design e templates reproduzíveis.

### Fase 7 — Controle automático de qualidade

Usar Gemini 3.6 Flash para analisar imagens e vídeos finais.

O auditor deverá verificar:

- rosto;
- mãos;
- celular;
- texto;
- logo;
- contraste;
- personagem;
- cenário;
- coerência com o público;
- coerência com o roteiro;
- qualidade do CTA;
- adequação ao canal.

Se a nota ficar abaixo do mínimo, o criativo deverá voltar para uma etapa específica:

- copy;
- imagem;
- áudio;
- layout;
- vídeo.

Não gerar novamente tudo quando apenas uma parte estiver ruim.

### Fase 8 — Aprovação humana

Manter duas aprovações:

1. aprovação da história antes da produção;
2. aprovação do criativo final antes do Gestor de Tráfego.

Implementar a segunda aprovação também no Desktop, com:

- preview;
- roteiro;
- legenda;
- canal;
- pedido de ajuste;
- aprovação;
- rejeição;
- histórico de versões.

### Fase 9 — Catálogo de campanhas

Criar um registro oficial para cada campanha.

Campos mínimos:

- campaign_id;
- público;
- golpe;
- canal;
- mídia;
- caminho do arquivo;
- legenda;
- roteiro;
- preset;
- status;
- data de criação;
- data de aprovação;
- data de publicação;
- plataforma;
- ID retornado;
- mensagem de erro.

Status:

```text
GERANDO
AGUARDANDO_APROVACAO_HISTORIA
PRODUZIDA
AGUARDANDO_APROVACAO_FINAL
APROVADA
PRONTA_PARA_PUBLICAR
PUBLICANDO
PUBLICADA
ERRO_PUBLICACAO
REJEITADA
```

### Fase 10 — Publicação

#### Meta

Primeiro testar a publicação real no Instagram com uma conta controlada.

Validar:

- token;
- permissões;
- conta profissional;
- upload;
- processamento;
- publicação;
- ID retornado;
- registro no histórico.

O código atual publica no Instagram, mas o Gestor de Tráfego ainda não cria campanhas pagas no Facebook Ads. Essa será uma etapa separada.

#### TikTok

Enquanto a publicação direta não estiver autorizada:

- gerar vídeo;
- gerar legenda;
- mostrar campanhas aprovadas no Desktop;
- permitir download;
- abrir o TikTok Studio;
- publicar manualmente.

A publicação automática direta no TikTok dependerá da aprovação do aplicativo.

### Fase 11 — Integração Desktop e Linux

Usar Supabase como ponte:

1. Linux gera a campanha.
2. Linux envia o arquivo para o Storage.
3. Linux grava os metadados.
4. Desktop mostra a campanha.
5. Desktop cria comando de publicação.
6. Linux executa o comando.
7. Linux grava o resultado.
8. Desktop mostra sucesso ou erro.

Tokens nunca deverão ser expostos no navegador.

## 6. Segurança obrigatória

- remover a exibição de tokens completos no Desktop;
- armazenar tokens apenas no backend;
- não registrar tokens em logs;
- não enviar `.env` para o Git;
- usar RLS restritivo no Supabase;
- validar todos os caminhos de arquivos;
- permitir publicação somente para usuário autorizado;
- registrar quem aprovou e quem publicou;
- impedir publicação duplicada;
- exigir confirmação antes da publicação;
- limitar tamanho e tipo de arquivo;
- usar HTTPS;
- manter aprovações de comandos do Cursor ativadas.

## 7. Critérios de sucesso

Uma campanha só será considerada pronta quando:

- história e criativo forem coerentes;
- canal e formato estiverem corretos;
- imagem estiver profissional;
- texto estiver legível;
- áudio estiver compreensível;
- personagem estiver correto;
- CTA estiver visível;
- auditoria automática atingir a nota mínima;
- usuário aprovar o resultado final.

Metas iniciais:

- zero combinação inválida de canal e mídia;
- zero texto essencial cortado;
- zero publicação sem aprovação;
- zero token exposto na interface;
- redução progressiva dos pedidos de “melhorar imagem”;
- redução progressiva de campanhas rejeitadas por incoerência;
- registro de 100% das campanhas e publicações.

## 8. Ordem prática de execução

1. Confirmar o ambiente remoto no Cursor.
2. Fazer backup e verificar o Git.
3. Executar a auditoria de 10 criativos.
4. Implementar validação de canal e mídia.
5. Implementar o brief estruturado.
6. Implementar storyboard.
7. Melhorar referências visuais e casting.
8. Criar templates.
9. Criar auditoria automática.
10. Implementar catálogo de campanhas.
11. Implementar aprovação no Desktop.
12. Testar publicação Meta.
13. Implementar publicação manual TikTok.
14. Criar fila Desktop ↔ Linux.
15. Avaliar fornecedores alternativos.
16. Só então decidir se algum modelo será substituído.

## 9. Primeiro trabalho no Cursor remoto

A primeira solicitação ao Agent deverá ser:

```text
Analise este repositório sem alterar arquivos. Leia campaign_orchestrator.py,
mkt_agent_01.py, channel_presets.py, campaign_history.py, traffic_manager.py,
meta_publisher.py, tiktok_publisher.py e a documentação de melhoria criativa.

Compare o código atual com o documento
PLANO_IMPLEMENTACAO_CRIATIVOS_PROFISSIONAIS.md.

Retorne:
1. o que já está implementado;
2. o que está parcialmente implementado;
3. o que ainda falta;
4. a menor primeira tarefa segura para iniciar.
```

Não iniciar várias fases ao mesmo tempo. Cada fase deverá ser implementada, testada e aprovada antes da próxima.
