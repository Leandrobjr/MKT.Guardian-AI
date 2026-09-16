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

**Implementação v5.25:** ponte operacional concluída com bucket privado,
`mkt_campaigns`, `mkt_campaign_commands`, RLS restritivo e módulo backend
`supabase_campaign_bridge.py`. O worker `campaign_command_worker.py` executa
comandos Meta com dry-run padrão; TikTok permanece manual. A interface
Desktop recebe o cliente seguro `desktop_campaign_client.py` e uma interface
web responsiva em `desktop/`, consumindo o contrato documentado em
`docs/SUPABASE_PONTE_CAMPANHAS.md`.

Tokens nunca deverão ser expostos no navegador.

**Implementação v5.26 — contrato canônico de criatividade:** o catálogo ativo
`contexto_negocio/golpes_catalogo.json` consolida 20 tipos documentados e 26
variantes operacionais. A geração agora rejeita o público genérico `geral`,
filtra variantes incompatíveis e bloqueia campanhas cujo golpe, pretexto,
headline, roteiro, protagonista ou casting visual não estejam coerentes. O
casting é definido antes do redator e a mídia só é produzida após a validação
determinística do contrato.

**Correção v5.27:** mensagens reais do golpista passaram a ser protegidas
contra o saneador de capacidades do produto. Termos como “sua conta será
bloqueada” permanecem no card quando fazem parte da fala criminosa; as
restrições do Guardian AI continuam aplicadas ao roteiro, CTA e card de solução.

**Correção v5.28:** headlines ambíguas de PIX passaram a ser rejeitadas ou
substituídas por frases com sujeito explícito, como “UM GOLPISTA PODE DESVIAR
O PIX PEDIDO NO WHATSAPP”.

**Correção v5.29:** o contrato da variante de falso pedido de PIX passou a
separar transferência autorizada, roubo de credenciais e tomada de conta. No
falso PIX familiar, o roteiro deve informar perda somente do valor enviado,
bloquear afirmações de esvaziamento da conta e alinhar a cena visual ao vínculo
real da mensagem, como “amigo” em vez de “parente”.

**Correção v5.30:** o vocativo do card passou a ser tratado como destinatário
da mensagem recebida. Assim, “Mãe” exige protagonista feminina e “Pai” exige
protagonista masculino; o casting é definido depois da seleção da variante e
o contrato bloqueia combinações incompatíveis.

**Correção v5.31:** headlines de falso PIX passaram a ser validadas como
frases completas. Estruturas como “o PIX que você receber pode fazer você
perder...” são substituídas por “PIX PEDIDO POR FAMILIAR NO WHATSAPP PODE SER
GOLPE”, e a copy não pode afirmar perda das economias, da aposentadoria ou da
conta quando a vítima apenas autorizou uma transferência.

**Correção v5.32:** corrigida a composição visual do logo e da headline. O
wordmark agora possui símbolo visual de escudo e área reservada própria, sem
sobreposição com a primeira linha da manchete. Também foram cobertas as formas
singulares de claims incorretos, como “perder sua economia”, no falso PIX.

**Correção v5.33:** quando o roteiro usa apenas o nome contratado, o motor
passa a explicitar o tratamento correspondente — “Dona Helena” ou “Seu Carlos”.
Isso mantém a identidade do protagonista coerente no roteiro, no resumo e no
casting visual.

**Correção v5.34:** claims absolutos como “o PIX não volta mais” passaram a
ser substituídos por “o PIX pode ser difícil de recuperar”. A consequência
continua limitada ao valor enviado, sem afirmar retorno impossível ou acesso
ao saldo da conta.

**Correção v5.35:** ampliada a proteção contra formas equivalentes de
exagero no falso PIX, como “levar sua economia”, e corrigida a concordância
de headlines que usam “difícil de recuperar”.

**Correção v5.36:** o tratamento “Dona” ou “Seu” agora é aplicado mesmo
quando o roteiro já contém pronomes de gênero, mas apresenta o nome do
protagonista sem marcador explícito.

**Correção v5.37:** corrigida a validação de nomes compostos no casting e
flexibilizado o nexo do falso PIX para aceitar redações naturais que mantenham
os elementos essenciais: WhatsApp, pedido/transferência de PIX e contexto da
fraude.

**Correção v5.38:** headlines de falso PIX são normalizadas em maiúsculas e
claims como “proteja sua aposentadoria” são ajustados para “proteja o valor
antes de enviar”, evitando sugerir perda da aposentadoria inteira.

**Correção v5.39:** claims equivalentes envolvendo poupança passaram a seguir
a mesma regra: no falso PIX, a copy orienta confirmar o pedido antes de fazer
a transferência, sem sugerir risco sobre toda a poupança.

**Correção v5.40:** expressões como “levar seu dinheiro” são limitadas ao
valor efetivamente enviado, e headlines com complementos artificiais, como
“perdeu o valor transferido agora”, são normalizadas para “PIX ENVIADO AO
GOLPISTA PODE SER DIFÍCIL DE RECUPERAR”.

**Correção v5.41:** corrigido o catálogo operacional de Grooming. A variante
de sextorsão deixou de ser elegível para o golpe `grooming`, e a variante
“Grooming com Falso Filho/Familiar” passou a ser selecionada corretamente
nesse grupo. O tipo de golpe agora permanece coerente com o menu escolhido.

**Correção v5.42:** cenas de Pais passaram a obedecer ao gênero do responsável
contratado — pai com filho ou mãe com filha — mesmo quando a matriz narrativa
fornece uma direção visual fixa. Também foi corrigida a concordância de CTA
como “do seu filho”.

**Correção v5.43:** a variante operacional de Grooming passou a ser elegível
para Pais e Escolas. O menu deixa de rejeitar `Pais + Grooming` após a retirada
das variantes de sextorsão e falso parente desse grupo.

**Correção v5.44:** a seleção de variantes passou a usar o catálogo canônico
antes do `golpe_id` legado. Para o público Pais, frases dirigidas a “Vó”, “Vô”,
“avó” ou “avô” são rejeitadas; esse vocativo continua permitido para Idosos.

**Correção v5.45:** para Pais, também foram bloqueadas mensagens dirigidas a
“Chefe” ou com relação de neto, mantendo o falso parente restrito a relações
familiares compatíveis com o responsável de 35–50 anos.

**Correção v5.46:** criada auditoria automatizada de todas as combinações
público × tipo de golpe. A seleção canônica passou a verificar a existência de
variantes operacionais, relações de destinatário, faixas etárias e públicos
institucionais, evitando misturas como Idoso + “Chefe” e Grooming para Idosos.

**Correção v5.47:** vocativos isolados “Vó” e “Vô” passaram a definir
corretamente o gênero do protagonista, além de “Avó” e “Avô”. Isso evita que
uma mensagem para avó seja apresentada com personagem masculino, ou vice-versa.

**Correção v5.48:** a validação de gênero da headline deixou de interpretar
menções indiretas, como “NÃO CONTA PRO MEU PAI”, como identidade do protagonista.
Somente sujeito explícito ou vocativo inicial define o gênero da manchete.

**Correção v5.49:** a variante de voz clonada que solicita PIX passou a usar
o mesmo mecanismo de transferência autorizada do falso PIX. Claims como
“conta zerada”, “aposentadoria sumiu” e “economia de uma vida inteira” são
normalizados para a perda limitada ao valor enviado.

**Correção v5.50:** fechadas as últimas brechas estruturais da matriz:
`publico_id` divergente é rejeitado, persona de outro público não é usada como
fallback, idades de Empresários e Escolas recebem guardrail, CTA usa o slug
canônico e overrides que mudam público ou golpe não misturam mais contrato,
casting e cena.

**Correção v5.51:** cenas do público Idosos passaram a variar conforme o tipo
de golpe. Falso investimento mostra oferta de investimento/cripto; phishing,
emprego, falsa central, clonagem, link malicioso e PIX recebem descrições
visuais próprias, sem reutilizar automaticamente o contexto de falso parente.

**Correção v5.52:** CTAs parentais passaram a manter a caixa alta consistente
em artigos após `PROTEJA`, evitando saídas como `PROTEJA o WhatsApp`.

**Correção v5.53:** a variante `ia_voz_clonada` passou a preservar seu
pretexto na headline (`VOZ CLONADA PODE PEDIR PIX EM SEU NOME`) e recebeu uma
regra de nexo específica para relacionar voz clonada, WhatsApp e pedido de PIX.

**Correção v5.54:** o gerador visual deixou de receber a instrução para escrever
texto legível dentro da tela do celular. A interface passa a ser desfocada e o
texto exato fica sob responsabilidade do compositor determinístico, evitando
artefatos de caracteres gerados por IA.

**Correção v5.55:** para o público Pais, a headline de voz clonada identifica
explicitamente o alvo familiar: `VOZ CLONADA PODE PEDIR PIX EM NOME DE SEU
FILHO!`. Outros públicos mantêm formulação familiar genérica.

**Correção v5.56:** a direção visual e a QA passaram a exigir que o telefone e
sua tela fiquem totalmente dentro do enquadramento, com margem visível e sem
corte nas bordas. O texto da mensagem continua sendo aplicado pelo compositor.

**Correção v5.57:** as variações de enquadramento foram restringidas para manter
o celular inteiro acima do terço inferior, com margem em todas as bordas e sem
mockups ampliados nas extremidades da imagem.

**Correção v5.58:** a direção visual passou a proibir mockup ampliado, segunda
tela e notificações flutuantes; no feed quadrado, a escala tipográfica deixou
de ser reduzida como se fosse vertical, melhorando a leitura dos cards.

**Correção v5.59:** as cenas por público passaram a descrever um único
smartphone físico, inteiro e discretamente desfocado, sem induzir o modelo a
criar uma tela grande nas bordas da composição.

**Correção v5.60:** a mixagem final passou a aplicar normalização FFmpeg em
`-16 LUFS`, `TP -1.5 dB` e `LRA 11`, inclusive quando não há trilha disponível,
eliminando o aviso de áudio baixo na QA.

**Correção v5.61:** a normalização EBU R128 passou a usar duas etapas. A segunda
passagem utiliza as métricas reais medidas na primeira para atingir `-16 LUFS`
com precisão e manter true peak máximo de `-1,5 dBTP`.

**Correção v5.62:** o prompt visual passou a exigir exatamente um smartphone
físico e deixou de enviar o texto do golpe ao gerador de imagens. A QA agora
reprova como falha crítica qualquer segundo aparelho, mockup ampliado, tela
flutuante ou inserção de interface. O criativo problemático foi corretamente
reprovado e sua nova versão, com um único celular, obteve nota 9,6.

**Correção v5.63:** a auditoria permanente passou a cobrir as 27 combinações
válidas de público e golpe, incluindo variantes, vocativos, gênero, idade,
persona, cena e consequência. Headlines fixas foram neutralizadas para não
conflitar com a alternância de gênero. Falsa central, urgência bancária,
boleto, QR Code, cobrança empresarial e falso investimento receberam
mecanismos e consequências explícitos; urgência bancária deixou de ser
classificada como golpe de PIX. Também foi eliminada a contradição entre a
expressão proibida `chat privado` e as instruções positivas da matriz.

**Correção v5.64 / Fábrica v18.11:** o teste integrado de Empresários com QR
Code passou a exigir o mesmo pretexto e o mesmo remetente do card no roteiro,
impedindo misturas entre desconto de fornecedor e estorno solicitado por
cliente. Headlines de QR Code, boleto e cobrança receberam fórmulas específicas,
e claims amplos sobre capital de giro ou faturamento são limitados ao valor
pago. A QA agora prioriza regeneração da imagem quando o celular estiver atrás
dos cards; os enquadramentos reservam os 40% inferiores para o layout. Também
foi corrigida a acentuação de `PROTEÇÃO WHATSAPP` no card da solução.

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
