# Execution Plan

## Objetivo

Construir, com **Google ADK (série 2, ≥ 2.2.0, versão exata fixada)**, o assistente virtual do **Residencial Aurora**, exposto por uma **API Python em `http://localhost:8000`** que segue exatamente o contrato do enunciado. O morador conversa com um **agente principal** que distribui o trabalho entre **pelo menos dois especialistas**, para reservar/cancelar áreas comuns, autorizar visitantes e tirar dúvidas do regulamento. As **cinco garantias** (confirmação para cobrança/acesso, sessão presa ao apartamento, persistência no reinício, regulamento consultado e não carregado, exclusividade de reserva sob concorrência) devem ser implementadas **em código**, não no prompt. Entrega: fork público com tudo na `main`, comando de subida, comando de restauração de dados e um `README.md` novo (Arquitetura, Garantias, Como rodar).

> Filosofia do desafio: "o modelo decide o caminho, o código decide o que é permitido".

## Contexto

- **Estado inicial do repositório** (commit `be87e1d`): apenas `README.md` (enunciado), `.gitignore` (`.env`, `.venv/`, `__pycache__/`) e `dados/`. Não há código algum. Remoto `origin` aponta para o repositório base `devfullcycle/mba-ia-desafio-criacao-agente` (o fork público ainda precisa ser criado pelo usuário).
- **O `README.md` atual é o enunciado e será substituído na última fase.** Depois disso, o enunciado original continua disponível via `git show be87e1d:README.md`. Sessões futuras devem ler o enunciado por esse comando se o README já tiver sido substituído.
- **Dados (imutáveis — nunca editar):**
  - `dados/apartamentos.json`: 101 Helena Prado, 102 Bruno Tavares, 201 Luana Castro, 202 Otávio Mendes, 301 Cecília Rocha, 302 Rafael Moreira.
  - `dados/areas.json`: `salao-de-festas` (taxa 150.0), `churrasqueira` (80.0), `quadra` (0 → sem cobrança).
  - `dados/reservas.json`: `RSV-1377` (101, quadra, 2030-03-09), `RSV-4821` (302, salão, 2030-03-16), `RSV-2950` (201, churrasqueira, 2030-03-23).
  - `dados/visitantes.json`: 302 Marina Duarte 2030-03-16; 201 Paulo Nogueira 2030-03-23.
  - `dados/regulamento.md`: ~45 KB, 14 capítulos com cabeçalhos `## Capítulo <romano>: <tema>` (I Disposições gerais; II Direitos e deveres; III Silêncio; IV Piscina — Art. 22: domingos e feriados 9h às 20h; V Academia...; VI Salão, churrasqueira e quadra; VII Portaria e segurança; VIII Animais; IX Mudanças; X Obras; XI Garagem; XII Lixo; XIII Infrações; XIV Disposições finais).
- **Ambiente local observado:** Windows 11; Python 3.13.1 e 3.12 instalados; **`uv` não está instalado** (precisa ser instalado na Fase 1); Docker disponível.
- **Ponto técnico mais arriscado:** retomar a execução após a confirmação de tool numa API própria. Segundo o enunciado, a retomada só funciona quando a resposta chega ao agente que pediu a confirmação, e o Runner escolhe esse agente conforme topologia, bloqueios de transferência, configuração de retomada do `App` e serviço de sessão. Uma combinação que funcionava em memória falhou com sessão persistida; com SQLite funcionou quando a resposta chegou ao agente certo. **Sempre testar a aprovação com sessão persistida e após reiniciar a API.**

## Requisitos e restrições

**Tecnologia**
- Python ≥ 3.12, projeto gerenciado por `uv` (`pyproject.toml` e `uv.lock` versionados).
- `google-adk` série 2, ≥ 2.2.0, versão **exata** fixada (`==`).
- Modelos Gemini com chave do Google AI Studio; modelo por agente é escolha livre (consultar docs e limites do projeto; o fluxo do avaliador faz algumas dezenas de chamadas).
- Framework web livre (curso usa FastAPI). Armazenamento livre; se depender de serviço externo, ele sobe com comando documentado.
- `.env` fora do Git; `.env.example` versionado só com nomes das variáveis.
- Arquivos de `dados/` idênticos aos do repositório base.

**Regras de negócio**
1. Uma reserva por área por data.
2. Área com taxa > 0 gera cobrança; taxa 0 não.
3. Autorizar visitante libera acesso; registra nome e data.
4. Morador cancela reservas do próprio apartamento sem confirmação.
5. Código de reserva gerado pelo sistema, formato livre, **nunca repete** nenhum código anterior (inclusive de reservas canceladas).

**Garantias (em código)**
- **G1** — Ação com cobrança ou que libera acesso fica pendente até resposta pela rota de confirmações; aparece em `confirmacoes_pendentes` com detalhes; aprovar executa uma única vez; negar não muda nada; ação sem cobrança/acesso não pede confirmação; texto do morador ("já confirmei") não confirma; `id` não pendente na sessão (inclusive já respondido) → `409` sem executar nada.
- **G2** — Apartamento definido só na criação da sessão; tools usam o apartamento da sessão, nunca um valor escolhido pelo modelo sem validação; nada de alterar ou expor reservas/visitantes de outro apartamento; checar disponibilidade revela só "livre/ocupada".
- **G3** — Reiniciar a API não perde sessões, eventos, reservas nem visitantes; a sessão continua aceitando mensagens.
- **G4** — Regulamento consultado sob demanda; nenhum evento da sessão contém trechos de capítulos de outros assuntos; agente principal não recebe o regulamento nas instruções.
- **G5** — Aprovações simultâneas para mesma área/data: uma vence, outra é recusada com resposta normal (`200`); nunca duas reservas ativas para mesma área/data; exclusividade garantida **no instante da gravação**.

**Contrato da API** (JSON; rotas com `{session_id}` → `404` se a sessão não existe)
- `POST /sessoes` `{"apartamento": "101"}` → `201 {"session_id": "..."}`
- `POST /sessoes/{id}/mensagens` `{"texto": "..."}` → `200 {"resposta": "...", "confirmacoes_pendentes": [{"id","acao","detalhes":{...}}]}` (`resposta` pode ser `""` quando parou esperando confirmação; lista contém **todas** as pendências da sessão)
- `POST /sessoes/{id}/confirmacoes` `{"id": "...", "confirmado": true|false}` → `200` (mesmo formato) ou `409`
- `GET /sessoes/{id}/eventos` → `200` lista com todos os eventos, em ordem, conteúdo completo
- `GET /apartamentos/{n}/reservas` → `[{"codigo","area","data"}]`
- `GET /apartamentos/{n}/visitantes` → `[{"nome","data"}]`

**Fora de escopo:** UI, autenticação, pagamento/estorno, regras de antecedência/horário/capacidade, respostas simultâneas à mesma confirmação, apartamento inexistente, nova mensagem com confirmação pendente (livre, desde que nada execute sem confirmação), tom das respostas, testes automatizados/evals/deploy.

**Entregável:** fork público na `main`; `README.md` na raiz substituindo o enunciado, com seções **Arquitetura**, **Garantias** (arquivo + trecho + por que não depende do modelo) e **Como rodar** (pré-requisitos, variáveis do `.env`, comando de subida, comando de restauração).

## Estratégia de execução

O plano segue de baixo para cima, isolando o que é determinístico (dados, regras, API de verificação) do que depende do modelo (agentes, confirmação):

1. **Fundação** (Fases 1–3): ambiente, investigação do ADK e decisões arquiteturais registradas antes de qualquer código de agente.
2. **Camada determinística** (Fases 4–6): esqueleto do projeto, armazenamento com exclusividade garantida no banco e rotas de verificação — tudo validável sem chamar o modelo.
3. **Tools e agentes** (Fases 7–9): tools de domínio amarradas ao apartamento da sessão, tool de regulamento por capítulo e topologia de agentes.
4. **Runtime e API conversacional** (Fases 10–11): sessões persistidas, Runner/App, rotas de conversa e o fluxo de confirmação (maior risco).
5. **Garantias transversais** (Fases 12–13): concorrência e reinício, validadas explicitamente.
6. **Validação e entrega** (Fases 14–16): execução completa do fluxo do avaliador, README final e publicação.

Dependências principais: F2 → F3 (decisões dependem da investigação); F5 é base de F6 e F7; F7+F8 → F9; F9 → F10 → F11; F11 → F12/F13; F12+F13 → F14 → F15 → F16. A Fase 6 pode ser feita em paralelo com F7/F8 após F5.

## Estratégia de versionamento

Decidida em 2026-09-27, a pedido do usuário: commits por contexto durante a execução; abertura dos PRs e merge só na Fase 16.

- **Branches empilhadas por contexto**, cada uma criada a partir da anterior (as fases dependem umas das outras):

  | Ordem | Branch | Fases | Conteúdo |
  | ----- | ------ | ----- | -------- |
  | 1 | `feat/fundacao` | 1–4 | `PLAN_EXECUTION.MD`, esqueleto do projeto (`pyproject.toml`, `uv.lock`, `aurora/` inicial) |
  | 2 | `feat/camada-dados` | 5–6 | banco SQLite, restauração, rotas de verificação |
  | 3 | `feat/tools-agentes` | 7–9 | tools de domínio, regulamento, agentes |
  | 4 | `feat/runtime-confirmacoes` | 10–11 | Runner/App, sessões, rotas de conversa e de confirmação |
  | 5 | `feat/garantias` | 12–14 | ajustes de concorrência, reinício e do fluxo completo do avaliador |
  | 6 | `docs/readme` | 15 | README final |

- **Commits:** mensagens no padrão já usado no repositório (`tipo: descrição` em português: `feat`, `fix`, `chore`, `docs`), um ou mais por fase. A atualização do `PLAN_EXECUTION.MD` vai no commit da própria fase.
- **Sem push** até a Fase 16.
- **PRs sempre no fork**: `gh pr create --repo tomxdev/mba-ia-desafio-criacao-agente --base main --head <branch>`. Nunca abrir PR no `upstream` (o `gh` pode sugerir o repositório base por causa do remoto `upstream`).
- **Merge em ordem** (1 → 6): cada PR é aberto contra `main` depois que o anterior foi mergeado (ou contra a branch anterior, com retarget após o merge). Usar merge commit, sem squash, para preservar o histórico e evitar conflitos entre branches empilhadas.
- Se uma fase posterior exigir correção em código de uma branch anterior, a correção é commitada na branch atual (`fix: ...`), sem reescrever branches anteriores.

---

# Fase 1 — Preparação do ambiente

## Objetivo

Deixar a máquina pronta para desenvolver: `uv` instalado, Python ≥ 3.12 disponível via `uv`, chave do Google AI Studio obtida e fork público criado.

## Dependências

Nenhuma.

## Arquivos envolvidos

- Nenhum arquivo do projeto é criado nesta fase (exceto, opcionalmente, `.env` local, que é ignorado pelo Git).

## Tarefas

* [x] instalar `uv` (ex.: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`) e confirmar `uv --version`
* [x] confirmar que `uv python list` enxerga Python 3.12+ (instalar com `uv python install 3.12` se necessário)
* [x] obter chave no Google AI Studio e anotar os limites ativos (RPM/RPD) dos modelos candidatos (chave válida; limites não anotados — substituído por teste real, ver F2-9)
* [x] **(ação do usuário)** criar o fork público do repositório base no GitHub
* [x] **(ação do usuário)** reconfigurar remotos: `origin` → fork, `upstream` → repositório base
* [x] registrar na seção "Decisões registradas" o nome do fork e a versão do `uv`

## Critérios de aceite

- `uv --version` funciona no terminal usado para o projeto;
- Python ≥ 3.12 disponível para o `uv`;
- chave do AI Studio disponível (não versionada);
- `git remote -v` mostra o fork como `origin`.

## Validação

- Manual: `uv --version`, `uv python list`, `git remote -v`.

## Resultado esperado

Ambiente pronto; nenhuma mudança versionada no repositório.

---

# Fase 2 — Investigação técnica do Google ADK

## Objetivo

Responder, com base na documentação oficial (Context7 / docs do ADK) e no código-fonte do pacote instalado, as questões técnicas que determinam a arquitetura. **Somente investigação — nada de código de produção.**

## Dependências

- Fase 1 (uv e Python).

## Arquivos envolvidos

- Leitura: código-fonte de `google-adk` instalado em um ambiente descartável (ex.: `uv run --with google-adk==<versão> python -c "import google.adk, os; print(os.path.dirname(google.adk.__file__))"`).
- Escrita: somente a seção "Decisões registradas" deste plano.

## Tarefas

* [x] identificar a versão mais recente do `google-adk` série 2 (≥ 2.2.0) e decidir qual fixar
* [x] ler a página oficial de **confirmação de ações de tools** (tool confirmation) e anotar: `FunctionTool(require_confirmation=...)` (bool ou função), `tool_context.request_confirmation(...)`, formato do evento de pedido (`adk_request_confirmation`), campos do payload (hint, payload, id da function call)
* [x] localizar no código-fonte do ADK como um cliente responde a uma confirmação pendente (formato do `FunctionResponse` com `ToolConfirmation`, qual `id` usar) e como o Runner retoma a execução
* [x] localizar no código-fonte como o Runner escolhe o agente que recebe a resposta (ex.: lógica de "find agent to run" / último autor de evento com function call) e como transferências e `disallow_transfer_to_parent/peers` afetam isso
* [x] investigar `App` e a configuração de retomada (ex.: `ResumabilityConfig`) e seu efeito na confirmação
* [x] investigar `DatabaseSessionService` com SQLite (URL, driver async necessário, criação de tabelas) e se os eventos de confirmação são persistidos e recuperados corretamente
* [x] investigar como gravar state inicial na criação da sessão (`create_session(state=...)`) e como as tools leem via `tool_context.state`; verificar se prefixos (`app:`, `user:`, `temp:`) afetam persistência
* [x] investigar o comportamento de `AgentTool` vs `sub_agents` (transferência): quais eventos do especialista vão para a sessão principal, se o state (apartamento) é propagado para o especialista e se confirmação funciona dentro de `AgentTool`
* [x] investigar como serializar `Event` para JSON completo (ex.: `event.model_dump(mode="json")`) para a rota de eventos
* [x] consultar a documentação de modelos Gemini disponíveis e escolher candidato(s) compatível(is) com os limites anotados na Fase 1
* [x] (opcional, descartável) escrever um protótipo mínimo **fora do repositório** (scratchpad) com um agente + uma tool com `require_confirmation`, `DatabaseSessionService` SQLite e resposta programática à confirmação, incluindo teste após reiniciar o processo
* [x] registrar todas as conclusões, com links/trechos de referência, em "Decisões registradas"

## Critérios de aceite

- Cada pergunta acima tem resposta registrada no plano, com fonte (doc ou arquivo/função do ADK);
- versão exata do ADK escolhida;
- formato exato da resposta de confirmação conhecido;
- combinação topologia + App + session service candidata identificada (idealmente validada pelo protótipo).

## Validação

- Revisão da seção "Decisões registradas": nenhuma questão desta fase sem resposta;
- se o protótipo foi feito: aprovação executa a tool uma vez, negação não executa, e funciona após reinício do processo.

## Resultado esperado

Conhecimento técnico suficiente para tomar as decisões da Fase 3 sem suposições.

---

# Fase 3 — Decisões arquiteturais

## Objetivo

Tomar e registrar as decisões de arquitetura necessárias antes da implementação.

## Dependências

- Fase 2 concluída.

## Arquivos envolvidos

- Seção "Decisões registradas" deste plano.

## Tarefas

* [x] **D1 — Framework web:** decidir (recomendado: FastAPI + Uvicorn, como no curso)
* [x] **D2 — Armazenamento de domínio:** decidir (recomendado: SQLite local, sem serviço externo; exclusividade via índice único parcial `UNIQUE(area, data) WHERE status = 'ativa'` ou tabela de reservas ativas com `UNIQUE(area, data)`)
* [x] **D3 — Armazenamento de sessões:** decidir (recomendado: `DatabaseSessionService` em SQLite, arquivo separado ou o mesmo do domínio)
* [x] **D4 — Unicidade de códigos:** decidir estratégia que nunca repete código, inclusive de canceladas (ex.: cancelamento lógico mantendo a linha com `codigo UNIQUE`, ou tabela de códigos emitidos; gerador sequencial ou aleatório com retry)
* [x] **D5 — Topologia de agentes:** definir agente principal e especialistas (ex.: `reservas`, `visitantes`, `regulamento`), e o modo de acionamento de cada um (`sub_agents` com transferência vs `AgentTool`), justificando com as conclusões da Fase 2 sobre retomada da confirmação
* [x] **D6 — Mapeamento de confirmações:** definir como extrair pendências dos eventos (`id`, `acao`, `detalhes`) e como validar que um `id` está pendente na sessão (derivado dos eventos persistidos e/ou registro próprio)
* [x] **D7 — Estratégia do regulamento:** definir divisão em trechos (por capítulo e/ou artigo) e como a tool devolve somente o trecho do assunto consultado
* [x] **D8 — Modelo(s) Gemini** por agente
* [x] **D9 — Estrutura de diretórios e comandos** de subida e restauração (ex.: `uv run aurora-api` / `uv run aurora-restore`, ou `uv run uvicorn ...` / `uv run python -m ...`)
* [x] **D10 — Restauração:** decidir se o comando de restauração também apaga as sessões
* [x] registrar cada decisão com motivo (serão reaproveitados no README)

## Critérios de aceite

- D1 a D10 registradas com motivo;
- nenhuma decisão contradiz requisitos do enunciado.

## Validação

- Revisão cruzada: cada garantia (G1–G5) tem pelo menos uma decisão que a sustenta explicitamente.

## Resultado esperado

Arquitetura definida; implementação pode começar sem decisões em aberto.

---

# Fase 4 — Esqueleto do projeto

## Objetivo

Criar a estrutura do projeto Python gerenciado por `uv`, com dependências fixadas e configuração de ambiente, sem lógica de negócio.

## Dependências

- Fase 3 (D1, D8, D9).

## Arquivos envolvidos

- `pyproject.toml`, `uv.lock`, `.python-version` (opcional)
- `.env.example`
- `.gitignore` (acrescentar arquivos de banco local, ex.: `*.db`, `*.sqlite`, se aplicável)
- pacote da aplicação (ex.: `src/aurora/` ou `app/`) com `__init__.py` e módulo de configuração

## Tarefas

* [x] executar `uv init` (ou criar `pyproject.toml` manualmente) com `requires-python = ">=3.12"`
* [x] adicionar `google-adk==<versão exata>` e dependências web/DB decididas (ex.: `fastapi`, `uvicorn`, driver async SQLite se exigido)
* [x] gerar `uv.lock`
* [x] criar `.env.example` com os nomes das variáveis (ex.: `GOOGLE_API_KEY=`, `GOOGLE_GENAI_USE_VERTEXAI=`, variáveis de modelo/caminho do banco, se houver) — sem valores
* [x] criar módulo de configuração que carrega o `.env` (ex.: `python-dotenv` ou mecanismo do ADK)
* [x] atualizar `.gitignore` para arquivos de banco local
* [x] definir entry points/comandos de subida e restauração (ainda como stubs)

## Critérios de aceite

- `uv sync` roda sem erro em ambiente limpo;
- `google-adk` fixado com `==` na série 2, ≥ 2.2.0;
- `.env.example` versionado sem valores; `.env` ignorado.

## Validação

- `uv sync` e `uv run python -c "import google.adk; print(google.adk.__version__)"`;
- `git status` não mostra `.env`;
- `git diff be87e1d -- dados/` vazio.

## Resultado esperado

Projeto instalável, sem funcionalidades.

---

# Fase 5 — Camada de dados e comando de restauração

## Objetivo

Implementar o armazenamento de reservas e visitantes, o carregamento/restauração a partir de `dados/*.json` e as operações de repositório com as regras de negócio 1, 4 e 5 garantidas pelo banco.

## Dependências

- Fase 4; decisões D2, D4, D10.

## Arquivos envolvidos

- módulo de banco/repositório (ex.: `src/aurora/db.py`, `src/aurora/repositorio.py`)
- módulo/comando de restauração (ex.: `src/aurora/restore.py`)
- leitura: `dados/apartamentos.json`, `dados/areas.json`, `dados/reservas.json`, `dados/visitantes.json`

## Tarefas

* [x] criar schema: `reservas` (codigo UNIQUE, apartamento, area, data, status/ativa), estrutura de exclusividade `(area, data)` para reservas ativas, `visitantes` (apartamento, nome, data), e estrutura que preserve códigos já emitidos
* [x] configurar a conexão para concorrência (ex.: modo WAL, `busy_timeout`, transação curta)
* [x] implementar comando de restauração: recria/limpa reservas e visitantes e recarrega de `dados/` (e sessões, conforme D10), mantendo os códigos iniciais registrados como emitidos
* [x] implementar leitura de áreas e apartamentos a partir de `dados/` (somente leitura)
* [x] implementar `listar_reservas(apartamento)` e `listar_visitantes(apartamento)` (retornando só campos do contrato)
* [x] implementar `area_disponivel(area, data) -> bool` sem expor dono da reserva
* [x] implementar gerador de código único (nunca repete códigos existentes ou cancelados)
* [x] implementar `criar_reserva(apartamento, area, data)` com gravação atômica: conflito de unicidade vira resultado de negócio ("data ocupada"), não exceção não tratada
* [x] implementar `cancelar_reserva(apartamento, ...)` que só afeta reservas do próprio apartamento e mantém o código como emitido
* [x] implementar `autorizar_visitante(apartamento, nome, data)`

## Critérios de aceite

- restauração deixa o banco igual aos JSONs de `dados/`;
- inserir duas reservas ativas para mesma área/data é impossível no nível do banco;
- cancelar reserva de outro apartamento não altera nada;
- códigos gerados nunca colidem com `RSV-1377`, `RSV-4821`, `RSV-2950` nem com códigos cancelados;
- arquivos de `dados/` inalterados.

## Validação

- script manual descartável (fora do repositório ou no scratchpad) chamando as funções: restaurar → listar 101/302 → criar reserva → tentar duplicar → cancelar → criar de novo e comparar códigos;
- teste de concorrência simples: duas threads/processos chamando `criar_reserva` na mesma área/data; exatamente um sucesso;
- `git diff be87e1d -- dados/` vazio.

## Resultado esperado

Camada de dados confiável e independente do modelo, pronta para ser usada por tools e rotas.

---

# Fase 6 — API base e rotas de verificação

## Objetivo

Subir a API em `http://localhost:8000` com as rotas de verificação funcionando sobre a camada de dados, sem agentes.

## Dependências

- Fase 5.

## Arquivos envolvidos

- módulo da API (ex.: `src/aurora/api.py` / `main.py`)
- comando de subida definido na Fase 4

## Tarefas

* [x] criar app web (D1) e o comando de subida na porta 8000
* [x] implementar `GET /apartamentos/{numero}/reservas` → `[{"codigo","area","data"}]` (somente reservas ativas)
* [x] implementar `GET /apartamentos/{numero}/visitantes` → `[{"nome","data"}]`
* [x] garantir respostas JSON e códigos de status do contrato

## Critérios de aceite

- após restauração, `GET /apartamentos/101/reservas` lista `RSV-1377` (quadra, 2030-03-09);
- `GET /apartamentos/302/visitantes` lista Marina Duarte (2030-03-16);
- formato idêntico ao do contrato.

## Validação

- executar restauração + subida; `curl http://localhost:8000/apartamentos/101/reservas` e `.../302/visitantes`;
- passo 1 do fluxo do avaliador (parte de verificação).

## Resultado esperado

API respondendo com dados iniciais; base para as rotas de conversa.

---

# Fase 7 — Tools de reservas e visitantes (Garantia 2)

## Objetivo

Implementar as tools ADK de domínio, amarradas ao apartamento da sessão, sem expor dados de outros apartamentos, e com marcação de confirmação para ações com cobrança/acesso.

## Dependências

- Fase 5; decisões D5, D6 (formato das confirmações) e conclusões da Fase 2 sobre `tool_context.state` e `require_confirmation`.

## Arquivos envolvidos

- módulo de tools (ex.: `src/aurora/tools/reservas.py`, `src/aurora/tools/visitantes.py`)

## Tarefas

* [x] implementar helper que obtém o apartamento **exclusivamente** de `tool_context.state` (chave definida na criação da sessão) e falha de forma segura se ausente
* [x] garantir que **nenhuma** tool receba parâmetro `apartamento` escolhido pelo modelo (ou, se receber, que seja validado contra o da sessão)
* [x] tool `listar_minhas_reservas`
* [x] tool `verificar_disponibilidade(area, data)` → retorna só `livre`/`ocupada`
* [x] tool `reservar_area(area, data)`: validar área existente; decidir confirmação pela **taxa lida do `areas.json`** (taxa > 0 → exige confirmação; taxa 0 → executa direto); conflito retorna mensagem de "data ocupada" sem código/apartamento do dono
* [x] incluir em `detalhes` da confirmação de reserva: `area` e `data` (e taxa, opcional)
* [x] tool `cancelar_reserva(...)` sem confirmação, só sobre reservas do apartamento da sessão; "não encontrada" sem revelar reservas alheias
* [x] tool `listar_meus_visitantes`
* [x] tool `autorizar_visitante(nome, data)` sempre exigindo confirmação, com `nome` e `data` em `detalhes`
* [x] revisar todos os retornos das tools para que nunca contenham código, apartamento ou nome de outro apartamento

## Critérios de aceite

- nenhuma tool usa apartamento vindo do modelo sem validação;
- reservar quadra não exige confirmação; salão/churrasqueira e visitante exigem;
- retornos nunca trazem `RSV-4821`, `302` ou `Marina Duarte` numa sessão do 101.

## Validação

- inspeção de código das assinaturas das tools;
- script manual chamando as funções das tools com um `ToolContext`/state simulado para 101 e verificando os retornos (incluindo tentativa de cancelar 2030-03-16 salão e reservar salão em 2030-03-16).

## Resultado esperado

Tools de domínio seguras, prontas para serem ligadas aos agentes.

---

# Fase 8 — Tool de regulamento (Garantia 4)

## Objetivo

Permitir consulta ao regulamento sem carregá-lo inteiro: a tool devolve apenas o(s) trecho(s) do assunto perguntado.

## Dependências

- Fase 4; decisão D7.

## Arquivos envolvidos

- módulo do regulamento (ex.: `src/aurora/regulamento.py`, `src/aurora/tools/regulamento.py`)
- leitura: `dados/regulamento.md`

## Tarefas

* [x] implementar parser que divide `dados/regulamento.md` por capítulo (`## Capítulo ...`) e, se útil, por artigo
* [x] implementar tool `listar_capitulos` (apenas títulos) e/ou `consultar_regulamento(capitulo|assunto)` que devolve só o capítulo/artigos solicitados
* [x] garantir que a tool nunca retorne o documento inteiro nem trechos de capítulos de outros assuntos
* [x] garantir que o regulamento não seja incluído em instruções de nenhum agente principal (se o especialista usar algo nas instruções, apenas o índice de capítulos) — verificado na Fase 9

## Critérios de aceite

- consulta sobre "piscina aos domingos" retorna o Capítulo IV (ou Art. 22), contendo "9h às 20h", e nada de outros capítulos;
- nenhum caminho de código retorna o regulamento completo.

## Validação

- script manual chamando a tool com assuntos variados (piscina, mudança, animais) e conferindo que só o capítulo correspondente é devolvido.

## Resultado esperado

Consulta ao regulamento enxuta, pronta para o especialista.

---

# Fase 9 — Agentes: principal e especialistas

## Objetivo

Montar a topologia de agentes definida em D5 e validar o roteamento no `adk web`.

## Dependências

- Fases 7 e 8; decisões D5 e D8.

## Arquivos envolvidos

- módulo de agentes (ex.: `src/aurora/agents/`), com `root_agent` exposto de forma compatível com `adk web`

## Tarefas

* [x] criar especialista(s) de reservas e visitantes com suas tools
* [x] criar especialista de regulamento com a tool do regulamento
* [x] criar agente principal com instruções de roteamento, **sem o regulamento nas instruções**
* [x] configurar o modo de acionamento de cada especialista e bloqueios de transferência conforme D5
* [x] incluir nas instruções orientação para não revelar dados de terceiros e para não considerar confirmações escritas na conversa (reforço — a garantia real está no código)
* [x] rodar `adk web` e verificar: roteamento correto, chamadas de tool, pedido de confirmação para salão e visitante, ausência de confirmação para quadra e cancelamento

## Critérios de aceite

- um agente principal + ≥ 2 especialistas;
- no `adk web`, cada tipo de pedido chega ao especialista correto e a tool certa é chamada;
- confirmação aparece para salão/visitante e não para quadra/cancelamento.

## Validação

- testes manuais no `adk web` com as mensagens dos passos 3–12 do fluxo do avaliador;
- inspeção das instruções do agente principal (sem regulamento).

## Resultado esperado

Agentes funcionando em ambiente de desenvolvimento, prontos para o Runner da API.

---

# Fase 10 — Runtime, sessões persistidas e rotas de conversa

## Objetivo

Ligar os agentes à API via `App` + `Runner` com sessão persistida, implementando criação de sessão, envio de mensagem e listagem de eventos.

## Dependências

- Fases 6 e 9; decisões D3, D6.

## Arquivos envolvidos

- módulo de runtime (ex.: `src/aurora/runtime.py`)
- módulo da API (rotas de sessão)

## Tarefas

* [ ] instanciar `DatabaseSessionService` (SQLite) e `App`/`Runner` conforme conclusões da Fase 2 (incluindo configuração de retomada, se necessária)
* [ ] `POST /sessoes`: criar sessão com o apartamento no state inicial; responder `201 {"session_id"}`
* [ ] `POST /sessoes/{id}/mensagens`: `404` se sessão não existe; rodar o Runner de forma async; concatenar o texto final do modelo em `resposta` (string vazia se parou em confirmação)
* [ ] implementar extração de `confirmacoes_pendentes` a partir dos eventos da sessão (todas as pendências não respondidas), no formato `{id, acao, detalhes}`
* [ ] `GET /sessoes/{id}/eventos`: `404` se não existe; devolver todos os eventos em ordem, serializados por completo
* [ ] garantir que o apartamento no state não possa ser alterado por mensagens (somente leitura pelas tools)

## Critérios de aceite

- criação de sessão retorna `201`; sessão inexistente retorna `404` nas três rotas;
- mensagens retornam `200` no formato do contrato;
- pedido de salão retorna pendência com `area` e `data` em `detalhes`, e nada é gravado;
- eventos incluem chamadas de tool.

## Validação

- `curl` para passos 2 a 7 (até a criação da pendência) e passo 9 (parte do `404`);
- conferir rotas de verificação após cada passo.

## Resultado esperado

Conversa funcionando pela API, com pendências visíveis mas ainda sem rota de confirmação.

---

# Fase 11 — Rota de confirmações e retomada (Garantia 1)

## Objetivo

Implementar `POST /sessoes/{id}/confirmacoes`, devolvendo a resposta do morador ao agente que pediu a confirmação e retomando a execução, com `409` para ids inválidos.

## Dependências

- Fase 10; conclusões da Fase 2 sobre formato da resposta e escolha do agente pelo Runner.

## Arquivos envolvidos

- módulo de runtime e rota de confirmações

## Tarefas

* [ ] validar que o `id` está entre as pendências **atuais** da sessão; caso contrário responder `409` sem executar nada (inclui id inexistente e id já respondido)
* [ ] construir a mensagem de resposta de confirmação no formato esperado pelo ADK (`FunctionResponse` do `adk_request_confirmation` com `confirmed` true/false)
* [ ] enviar pelo Runner e garantir que a execução retoma no agente que pediu a confirmação
* [ ] devolver `200` no mesmo formato da rota de mensagens
* [ ] garantir que negar não grava nada e que aprovar grava exatamente uma vez
* [ ] verificar que texto do morador do tipo "já estou confirmando" não resolve a pendência
* [ ] testar aprovação após reiniciar a API com a pendência criada antes do reinício
* [ ] registrar no plano a combinação final (topologia/App/session service) que funcionou

## Critérios de aceite

- passo 7: negar → nenhuma reserva;
- passo 8: aprovar → exatamente uma reserva; reenvio do mesmo id → `409`, sem nova reserva;
- passo 9: `id-inexistente` → `409`, reservas inalteradas;
- passo 11: visitante com "já estou confirmando" fica pendente com `nome` e `data`; só aparece após aprovação;
- aprovação funciona com sessão persistida e após reinício.

## Validação

- `curl` sequencial dos passos 7, 8, 9 e 11 conferindo rotas de verificação;
- reiniciar a API entre criar a pendência e aprová-la;
- inspeção de `GET /sessoes/{id}/eventos` para confirmar execução única da tool.

## Resultado esperado

Garantia 1 implementada e comprovada via API.

---

# Fase 12 — Concorrência na reserva (Garantia 5)

## Objetivo

Comprovar que aprovações simultâneas para a mesma área/data resultam em exatamente uma reserva e duas respostas `200`.

## Dependências

- Fase 11; camada de dados da Fase 5.

## Arquivos envolvidos

- camada de dados, tool de reserva e rota de confirmações (ajustes se necessário)

## Tarefas

* [ ] reproduzir o passo 14: sessões do 101 e do 201, ambas com pendência de salão em 2030-05-11
* [ ] disparar as duas aprovações simultaneamente (ex.: dois `curl` com `&` no Git Bash ou `Start-Job` no PowerShell)
* [ ] verificar ausência de erro 500 (ex.: `database is locked`) e ajustar timeout/transação se necessário
* [ ] garantir que a perdedora recebe resposta normal informando data ocupada, sem expor dados do outro apartamento
* [ ] repetir o teste várias vezes (datas diferentes) para reduzir chance de sucesso por acaso

## Critérios de aceite

- as duas aprovações respondem `200`;
- `GET /apartamentos/101/reservas` + `GET /apartamentos/201/reservas` somam exatamente uma reserva do salão na data;
- exclusividade garantida por constraint/transação no momento da gravação (inspeção de código).

## Validação

- execução concorrente repetida; inspeção dos logs da API sem exceções não tratadas.

## Resultado esperado

Garantia 5 comprovada.

---

# Fase 13 — Persistência no reinício (Garantia 3)

## Objetivo

Comprovar que parar e subir a API preserva sessões, eventos e dados, e que a sessão continua funcional.

## Dependências

- Fase 11.

## Arquivos envolvidos

- runtime/configuração de persistência (ajustes se necessário)

## Tarefas

* [ ] criar sessão, trocar mensagens com chamadas de tool e anotar a quantidade de eventos
* [ ] parar a API com Ctrl+C e subir novamente com o mesmo comando, sem restaurar dados
* [ ] conferir que `GET /sessoes/{id}/eventos` retorna a mesma quantidade
* [ ] enviar nova mensagem ("Quais são as minhas reservas agora?") e conferir `200` e aumento de eventos
* [ ] conferir reservas, cancelamentos e visitantes nas rotas de verificação
* [ ] conferir que códigos criados são únicos e diferentes de `RSV-1377`, `RSV-4821`, `RSV-2950`

## Critérios de aceite

- critérios do passo 13 do fluxo do avaliador satisfeitos.

## Validação

- execução manual do reinício com `curl` antes e depois.

## Resultado esperado

Garantia 3 comprovada.

---

# Fase 14 — Execução completa do fluxo do avaliador

## Objetivo

Rodar os passos 1 a 15 do fluxo do avaliador de ponta a ponta, em clone limpo, e corrigir desvios.

## Dependências

- Fases 12 e 13.

## Arquivos envolvidos

- nenhum novo (ajustes pontuais nos módulos existentes se houver falhas); opcionalmente um roteiro de verificação em `scripts/` (testes automatizados estão fora de escopo — o roteiro é apenas apoio)

## Tarefas

* [ ] clonar o repositório em pasta temporária, copiar `.env.example` → `.env`, preencher chave, `uv sync`
* [ ] executar comandos de restauração e subida exatamente como estarão no README
* [ ] executar passos 1 a 14 com `curl`, conferindo cada verificação (incluindo buscas por `RSV-4821`, `Marina Duarte` e `302` isolado nas respostas e eventos)
* [ ] no passo 12, conferir que os eventos não contêm trechos de outros capítulos do regulamento e que a resposta traz 20h
* [ ] executar o checklist do passo 15 (versão ADK, `dados/` idênticos, sem chaves, agentes, tools, apartamento da sessão, instruções do principal, exclusividade)
* [ ] repetir o fluxo ao menos uma vez com redação variada das mensagens
* [ ] registrar falhas encontradas e correções aplicadas neste plano

## Critérios de aceite

- todos os critérios de aceite do enunciado atendidos, exceto os de README (Fase 15);
- nenhum erro 500 durante o fluxo;
- consumo de chamadas ao modelo compatível com os limites do projeto.

## Validação

- evidências de cada passo (saídas de `curl`) registradas resumidamente no plano;
- `git diff be87e1d -- dados/` vazio; `git ls-files | grep .env` só mostra `.env.example`.

## Resultado esperado

Implementação validada contra o fluxo do avaliador.

---

# Fase 15 — README final

## Objetivo

Substituir o enunciado por um `README.md` com Arquitetura, Garantias e Como rodar, apontando arquivos e trechos que existem.

## Dependências

- Fase 14.

## Arquivos envolvidos

- `README.md`

## Tarefas

* [ ] seção **Arquitetura**: cada agente, responsabilidade, forma de acionamento e motivo (reaproveitar D5)
* [ ] seção **Garantias**: para G1–G5, arquivo + trecho/função + por que não depende do modelo
* [ ] seção **Como rodar**: pré-requisitos (Python, uv), variáveis do `.env`, `uv sync`, comando de restauração, comando de subida, serviços externos (se houver)
* [ ] conferir que todos os caminhos e nomes citados existem no repositório
* [ ] seguir o README "do zero" em clone limpo para confirmar que os comandos funcionam

## Critérios de aceite

- as três seções existem;
- todos os arquivos/trechos citados existem;
- comandos documentados funcionam em clone limpo.

## Validação

- inspeção manual + execução dos comandos do README em clone limpo.

## Resultado esperado

Documentação de entrega completa.

---

# Fase 16 — Entrega

## Objetivo

Publicar a entrega no fork público, na branch `main`.

## Dependências

- Fase 15; fork criado (Fase 1).

## Arquivos envolvidos

- repositório Git (sem alterações de código)

## Tarefas

* [ ] conferir `git status` limpo, `.env` fora do Git, `uv.lock` versionado
* [ ] conferir `git diff be87e1d -- dados/` vazio
* [ ] **(com autorização do usuário)** fazer push das branches de contexto para o fork (`origin`)
* [ ] abrir os PRs no fork, na ordem da seção "Estratégia de versionamento", com `--repo tomxdev/mba-ia-desafio-criacao-agente`
* [ ] mergear os PRs em ordem (merge commit), conferindo que cada um fica sem conflito antes do próximo
* [ ] conferir que `main` do fork contém toda a entrega (`git log origin/main`)
* [ ] conferir no GitHub que o fork é público e que o README renderiza corretamente

## Critérios de aceite

- `main` do fork público contém toda a entrega;
- critérios de "Execução e entrega" do enunciado atendidos.

## Validação

- clone do fork via HTTPS em pasta nova + `uv sync` + passo 1 do fluxo.

## Resultado esperado

Desafio entregue.

---

# Decisões registradas

> Preencher durante a execução (Fases 1–3 e qualquer descoberta posterior). Formato: **ID — decisão — motivo — fonte/data**.

- **F1 — Ambiente** — uv 0.12.19 instalado em `~/.local/bin` (adicionar ao PATH se o terminal não enxergar); Python disponíveis: 3.12.10 e 3.13.1 — 2026-09-27
- **F1 — Fork** — https://github.com/tomxdev/mba-ia-desafio-criacao-agente (público); `origin` = fork, `upstream` = repositório base — 2026-09-27
- **F1 — .env** — `.env` local criado com `GOOGLE_GENAI_USE_VERTEXAI=FALSE` e `GOOGLE_API_KEY=` vazio, chave preenchida pelo usuário e validada (listagem de modelos OK) — 2026-09-27

### Achados da Fase 2 (investigação do ADK — 2026-09-27)

Fonte: código-fonte de `google-adk==2.10.0` + protótipo descartável (scratchpad, fora do repo) com agente principal → especialista `chat` via `sub_agents`, tool com confirmação, `DatabaseSessionService` SQLite e resposta à confirmação **em processo novo** (simula reinício).

- **F2-1 — Versão:** série 2 vai até `2.10.0` (PyPI, 2026-09-27). Protótipo validado com **`google-adk[db]==2.10.0`** → candidata a fixar.
- **F2-2 — Dependências extras:** `DatabaseSessionService` exige `google-adk[db]` (SQLAlchemy), driver async `aiosqlite` e `greenlet` (`sqlalchemy[asyncio]`); sem `greenlet` o erro é genérico ("Failed to create database engine").
- **F2-3 — URL SQLite:** `sqlite+aiosqlite:///./<arquivo>.db` (relativo ao diretório de execução) funcionou. Caminho absoluto no Windows não foi validado (a falha inicial era a falta do `greenlet`, F2-2) — preferir relativo à raiz do projeto ou montar a partir de `Path(...).as_posix()` e testar.
- **F2-4 — Pedido de confirmação:** na tool, `tool_context.request_confirmation(hint=..., payload={...})` (ou `FunctionTool(func, require_confirmation=bool|callable)`); na segunda passada `tool_context.tool_confirmation.confirmed` diz se aprovou. ADK gera evento do autor do especialista com `FunctionCall(name="adk_request_confirmation", id="adk-<uuid>", args={"originalFunctionCall": {id,name,args}, "toolConfirmation": {hint,confirmed,payload}})` e `long_running_tool_ids`. Fonte: `flows/llm_flows/tools/_functions.py::generate_request_confirmation_event`, `agents/context.py::request_confirmation`.
- **F2-5 — Resposta do cliente:** `types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(id=<id adk-...>, name="adk_request_confirmation", response={"confirmed": true|false}))])` enviado via `runner.run_async(new_message=...)`. Fonte: `cli/cli.py` (~l.692) e `tools/tool_confirmation.py::from_response_dict`.
- **F2-6 — Escolha do agente na retomada:** `agents/_agent_router.py::find_agent_to_run`. Com `ResumabilityConfig(is_resumable=True)`, o Runner roteia a function response ao **autor da function call correspondente**. Sem resumability, cai no último agente "transferível" (ou no root). No protótipo, ambos funcionaram (especialista `chat` sem bloqueio de transferência), mas `is_resumable=True` é o caminho determinístico → **recomendado**. Bloquear transferência do especialista (`disallow_transfer_to_parent/peers`) sem resumability tende a devolver a resposta ao root (causa da armadilha citada no enunciado).
- **F2-7 — Resultado do protótipo (SQLite + processo novo):** aprovar → tool executou 1 vez no especialista, com `apartamento` lido do state; negar → nada gravado; pendência some após resposta. `state` inicial passado em `create_session(state={"apartamento": ...})` persiste e chega a `tool_context.state`.
- **F2-8 — ⚠️ Reenvio do mesmo id RE-EXECUTA a tool:** o ADK não barra resposta duplicada (log mostrou 2 execuções). Logo: (a) a API deve validar que o `id` está pendente **antes** de chamar o Runner (409 caso contrário); (b) a gravação deve ser idempotente (ex.: registrar o `id` da function call/confirmação executada com `UNIQUE` no banco). `ResumabilityConfig` também documenta "at-least-once".
- **F2-9 — Modelos:** `gemini-2.5-flash` retorna 404 "no longer available to new users". Disponíveis: `gemini-3.5-flash`, `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.5-flash-lite` etc. **503 "high demand" frequentes** (3.8-flash e 3.5-flash); `gemini-flash-latest` respondeu bem. Usar `Gemini(model=..., retry_options=types.HttpRetryOptions(initial_delay=2, attempts=6, http_status_codes=[429,500,503]))` e modelo configurável por `.env`.
- **F2-10 — AgentTool:** roda o especialista numa sessão **`InMemorySessionService` separada** (copia o state do pai, exceto chaves `_adk*`); só o retorno final entra na sessão principal. ⇒ **não usar AgentTool para especialista que pede confirmação** (pendência não seria persistida); é **adequado para o regulamento** (eventos internos com o capítulo não entram na sessão principal — reforça G4). Modos novos `task`/`single_turn` de `LlmAgent.mode` usam o runtime de nodes do ADK 2 — evitar (risco de comportamento diferente na retomada).
- **F2-11 — Eventos e sessão:** `event.model_dump(mode="json", exclude_none=True, by_alias=True)` serializa o evento completo (JSON válido). `session_service.get_session(...)` retorna `None` para sessão inexistente → base para o `404`. Pendências = function calls `adk_request_confirmation` sem function response correspondente com mesmo `id` na sessão.

### Decisões arquiteturais da Fase 3 (2026-09-27)

- **D1 — Framework web:** FastAPI + Uvicorn em `127.0.0.1:8000`. **Motivo:** é o do curso, é async nativo (combina com `runner.run_async`) e os modelos Pydantic facilitam seguir o contrato à risca.
- **D2 — Armazenamento de domínio:** SQLite local (`var/aurora.db`) via `sqlite3` da biblioteca padrão, sem serviço externo. Schema:
  - `reservas(codigo TEXT PRIMARY KEY, apartamento, area, data, ativa INTEGER NOT NULL DEFAULT 1, operacao_id TEXT UNIQUE)`;
  - **índice único parcial `CREATE UNIQUE INDEX ux_reserva_ativa ON reservas(area, data) WHERE ativa = 1`** → exclusividade garantida no instante do `INSERT` (G5, regra 1);
  - `visitantes(id INTEGER PRIMARY KEY, apartamento, nome, data, operacao_id TEXT UNIQUE)`;
  - conexão curta por operação, `PRAGMA journal_mode=WAL`, `busy_timeout=5000`; o `IntegrityError` do índice vira resultado de negócio `{"status": "ocupada"}` (resposta normal, sem 500);
  - áreas e apartamentos são lidos direto de `dados/*.json` (somente leitura).
  **Motivo:** zero infraestrutura para o avaliador, e a constraint do banco é o que faz a exclusividade valer "no instante da gravação".
- **D3 — Sessões:** `DatabaseSessionService` com SQLite em `var/sessoes.db`, **arquivo separado** do domínio. **Motivo:** persistência exigida por G3 e validada no protótipo (F2-7); arquivos separados evitam disputa de lock entre `aiosqlite` (sessões) e `sqlite3` (domínio). A URL deve ser montada de forma que funcione no Windows (F2-3) — validar na Fase 4.
- **D4 — Códigos de reserva:** `RSV-` + 6 caracteres alfanuméricos maiúsculos aleatórios (`secrets`), com nova tentativa se colidir com a `PRIMARY KEY`. Cancelamento é **lógico** (`ativa = 0`): a linha e o código permanecem e **nunca são reutilizados** (regra 5), inclusive `RSV-1377/4821/2950`. **Motivo:** a unicidade é garantida pelo banco, não pelo gerador.
- **D5 — Topologia de agentes** (App com `ResumabilityConfig(is_resumable=True)`, F2-6):
  - `assistente_aurora` (**principal**, `LlmAgent` modo chat): conversa e roteia; **sem regulamento e sem tools de dados**;
  - `especialista_reservas` (`sub_agents`, transferência): reservar, cancelar, listar, disponibilidade;
  - `especialista_visitantes` (`sub_agents`, transferência): autorizar e listar visitantes;
  - `especialista_regulamento` (**`AgentTool`** no principal): consulta por capítulo;
  - reservas/visitantes **podem** transferir de volta ao principal (sem `disallow_transfer_*`).
  **Motivo:** quem pede confirmação precisa estar na sessão persistida e ser o autor da function call, para a retomada chegar a ele (F2-6, F2-7). `AgentTool` isola os eventos do regulamento numa sessão em memória, e só a resposta final entra na sessão principal (F2-10, reforça G4). Não usar os modos `task`/`single_turn` (F2-10).
- **D6 — Confirmações:**
  - **Pedido em código:** a tool chama `tool_context.request_confirmation(hint, payload=detalhes)`. Reserva: só quando `taxa > 0` em `dados/areas.json`, `detalhes = {"area", "data", "taxa"}`. Visitante: sempre, `detalhes = {"nome", "data"}`. Antes de pedir confirmação de reserva, a tool checa disponibilidade; se ocupada, responde "ocupada" sem criar pendência.
  - **Na API:** `id` = id da function call `adk_request_confirmation` (`adk-<uuid>`); `acao` = nome da tool original (`reservar_area` / `autorizar_visitante`); `detalhes` = `toolConfirmation.payload`.
  - **Pendentes** = `adk_request_confirmation` sem `FunctionResponse` de mesmo `id` nos eventos persistidos, sempre recalculadas da sessão (F2-11).
  - **409 antes do Runner:** se o `id` não está entre as pendentes, `409` sem chamar o Runner (F2-8). Um `asyncio.Lock` por `session_id` serializa mensagens e confirmações da mesma sessão.
  - **Idempotência:** a gravação usa `operacao_id = tool_context.function_call_id` com `UNIQUE`; uma re-execução devolve o resultado já gravado sem duplicar (defesa em profundidade, F2-8).
- **D7 — Regulamento:** o parser divide `dados/regulamento.md` por `## Capítulo <romano>: <tema>` (14 capítulos). Tools do especialista: `listar_capitulos()` (só número + tema) e `consultar_capitulo(capitulo)` (romano ou arábico; devolve **um** capítulo). Nenhuma função devolve o documento inteiro; as instruções não contêm o texto do regulamento. **Motivo:** o capítulo é a unidade de "assunto" do enunciado (G4).
- **D8 — Modelo:** `gemini-flash-latest` para todos os agentes, configurável por `AURORA_MODEL` no `.env`, via `Gemini(model=..., retry_options=HttpRetryOptions(initial_delay=2, attempts=6, http_status_codes=[429, 500, 503]))`. **Motivo:** respondeu estável no protótipo (F2-9); `gemini-2.5-flash` está indisponível para contas novas. Reavaliar na Fase 14.
- **D9 — Estrutura e comandos:**
  ```
  pyproject.toml / uv.lock / .env.example
  aurora/              # pacote; aurora/agent.py expõe root_agent (compatível com `uv run adk web .`)
    config.py          # .env, caminhos, modelo
    dominio.py         # leitura de dados/*.json (áreas, apartamentos)
    banco.py           # schema SQLite + repositório (reservas/visitantes)
    restaurar.py       # comando de restauração
    regulamento.py     # parser por capítulo
    tools/             # _sessao.py, reservas.py, visitantes.py, regulamento.py
    agent.py           # agentes + root_agent
    runtime.py         # App, Runner, session service, extração de pendências
    api.py             # FastAPI (rotas do contrato)
  var/                 # bancos SQLite (ignorado pelo Git)
  ```
  Comandos (`[project.scripts]` + build backend): **`uv run aurora-restaurar`** e **`uv run aurora-api`** (Uvicorn em `127.0.0.1:8000`). **Motivo:** dois comandos curtos, iguais em qualquer SO.
- **D10 — Restauração:** `aurora-restaurar` recria `var/aurora.db` a partir de `dados/` **e apaga `var/sessoes.db`**; executar com a API parada (documentar). **Motivo:** pendências de sessões antigas poderiam ser aprovadas depois da restauração e gravar sobre o estado inicial; começar limpo torna o passo 1 do avaliador determinístico.
- **D11 — Apartamento da sessão (G2):** a chave `apartamento` do state é gravada **só** em `POST /sessoes`. Nenhuma tool recebe `apartamento` como parâmetro; todas usam `aurora/tools/_sessao.py`, que lê `tool_context.state["apartamento"]`, e nenhuma tool escreve essa chave. Os retornos nunca incluem código, apartamento ou nome de terceiros; disponibilidade devolve só `livre`/`ocupada`. `POST /sessoes` com apartamento fora de `dados/apartamentos.json` → `422` (comportamento livre pelo enunciado).

#### Revisão cruzada garantia → decisões

| Garantia | Sustentada por |
| -------- | -------------- |
| G1 confirmação | D5 (resumable + especialista autor), D6 (pedido em código pela taxa/visitante, 409 antes do Runner, idempotência) |
| G2 apartamento | D11 (state gravado só na criação; tools sem parâmetro de apartamento; retornos sanitizados), D6 (disponibilidade sem expor o dono) |
| G3 reinício | D2 + D3 (SQLite em arquivo para domínio e sessões), D5 (resumable validado em processo novo, F2-7) |
| G4 regulamento | D5 (principal sem regulamento; especialista via AgentTool), D7 (um capítulo por consulta) |
| G5 concorrência | D2 (índice único parcial + tratamento de `IntegrityError`), D4 (PK do código) |

### Registro da Fase 4 (2026-09-27)

- **F4-1 — Dependências:** `google-adk[db]==2.10.0` (exato), `fastapi`, `uvicorn`, `aiosqlite`, `greenlet`, `python-dotenv` (mínimas, travadas no `uv.lock`). Build backend `uv_build` com `module-root = ""` (pacote `aurora/` na raiz). `.python-version` = 3.12.
- **F4-2 — F2-3 resolvido:** URL absoluta `sqlite+aiosqlite:///<RAIZ>/var/sessoes.db` (via `Path.as_posix()`) funciona no Windows, inclusive com `@`, espaços e acentos no caminho. Ver `aurora/config.py::url_banco_sessoes`. A API não depende do diretório de execução.
- **F4-3 — `.env.example`:** `GOOGLE_API_KEY` e `AURORA_MODEL` (opcional; padrão `gemini-flash-latest` em `aurora/config.py`). `var/` adicionado ao `.gitignore`.

### Registro da Fase 5 (2026-09-27)

- **F5-1 — Arquivos:** `aurora/dominio.py` (áreas, apartamentos, dados iniciais, `data_valida`), `aurora/banco.py` (schema + repositório), `aurora/restaurar.py` (comando). A API do repositório: `listar_reservas`, `listar_visitantes`, `area_ocupada`, `criar_reserva -> ResultadoReserva(status "criada"|"ocupada", codigo)`, `cancelar_reservas(apartamento, *, codigo, area, data)` (exige pelo menos um filtro; sempre filtra pelo apartamento), `autorizar_visitante`.
- **F5-2 — Transações:** conexão em autocommit com `BEGIN IMMEDIATE` explícito nas escritas; `busy_timeout` de 10 s; WAL. O conflito do índice `ux_reserva_ativa` é identificado pela mensagem `UNIQUE constraint failed: reservas.area, reservas.data`; colisão de código (`reservas.codigo`) sorteia outro.
- **F5-3 — Validação executada:** script descartável (scratchpad `valida_fase5.py`) com 22 checagens, todas OK, incluindo INSERT direto duplicado barrado pelo índice, reuso de código cancelado barrado pela PK, idempotência por `operacao_id` e 10 rodadas × 8 processos simultâneos (sempre 1 criada, 7 ocupadas, 1 no banco). `uv run aurora-restaurar` OK; `dados/` sem diff.

### Registro da Fase 6 (2026-09-27)

- **F6-1 — Rotas:** `GET /apartamentos/{numero}/reservas` e `/visitantes` em `aurora/api.py`, com `response_model` Pydantic (só os campos do contrato). Endpoints síncronos (`def`) para o FastAPI rodar o SQLite no threadpool, sem bloquear o loop async do Runner.
- **F6-2 — Startup:** `lifespan` chama `banco.criar_schema()` (idempotente); a carga dos dados iniciais continua sendo papel de `aurora-restaurar`.
- **F6-3 — Validação:** `aurora-restaurar` + `aurora-api` + `curl`: 101 → `[{"codigo":"RSV-1377","area":"quadra","data":"2030-03-09"}]`; 302 visitantes → `[{"nome":"Marina Duarte","data":"2030-03-16"}]`; apartamento inexistente → `[]` (comportamento livre pelo enunciado). Sem erros no log.

### Registro da Fase 7 (2026-09-27)

- **F7-1 — Arquivos:** `aurora/tools/_sessao.py` (`apartamento_da_sessao`: única fonte do apartamento; valida contra `dados/apartamentos.json`), `aurora/tools/_confirmacao.py` (`exigir_confirmacao`: único ponto da Garantia 1 nas tools), `aurora/tools/reservas.py` (`listar_areas`, `listar_minhas_reservas`, `verificar_disponibilidade`, `reservar_area`, `cancelar_reserva`) e `aurora/tools/visitantes.py` (`listar_meus_visitantes`, `autorizar_visitante`).
- **F7-2 — Regras no código:** `reservar_area` decide a confirmação por `Area.gera_cobranca` (taxa de `dados/areas.json`); `autorizar_visitante` sempre exige confirmação. A checagem de ocupação ocorre antes de pedir confirmação (evita pendência inútil), mas a exclusividade real é o INSERT (uma aprovação para data tomada no meio do caminho vira "ocupada"). `operacao_id = tool_context.function_call_id` (a confirmar na Fase 11 que o id é o mesmo na retomada).
- **F7-3 — Cancelamento:** filtros opcionais `codigo`/`area`/`data`, sempre dentro das reservas do próprio apartamento. Com mais de uma candidata, devolve `ambigua` com as opções do próprio apartamento e não cancela nada. Com nenhuma, devolve `nao_encontrada` sem revelar reservas alheias.
- **F7-4 — Declarações no ADK 2:** o schema dos parâmetros fica em `FunctionDeclaration.parameters_json_schema` (e não em `parameters`). Conferido: nenhuma tool expõe `apartamento` ou `tool_context` ao modelo.
- **F7-5 — Validação:** script descartável `valida_fase7.py` com `ToolContext` simulado, 31 checagens OK, cobrindo os cenários dos passos 3–8, 10 e 11 no nível das tools. A varredura de todos os retornos da sessão do 101 não encontrou `RSV-4821`, `Marina Duarte` nem `302` isolado.

### Registro da Fase 8 (2026-09-27)

- **F8-1 — Arquivos:** `aurora/regulamento.py` (`capitulos()` e `buscar_capitulo()`) e `aurora/tools/regulamento.py` (`listar_capitulos`, só número e tema; `consultar_capitulo(capitulo)`, com um capítulo por vez e referência em romano ou arábico, com ou sem "Capítulo").
- **F8-2 — Formato do arquivo:** 14 cabeçalhos `## Capítulo <romano>: <tema>`, sem subtítulos; o arquivo fica com CRLF na cópia de trabalho do Windows (`autocrlf`), então o parser normaliza para LF. Os Arts. 1º–9º usam ordinal (`Art. 1º`) e os demais `Art. 10.`.
- **F8-3 — Validação:** 12 checagens OK. Os capítulos concatenados reproduzem o documento exatamente; cada capítulo tem 1 cabeçalho e artigos exclusivos (Arts. 1–96); o Cap. IV traz "Aos domingos e feriados, a piscina funciona das 9h às 20h"; referência inválida ou texto livre dá erro; o índice tem 963 bytes, sem artigos; o maior retorno de consulta tem ~4,8 mil caracteres, contra ~43 mil do documento.
- **F8-4 — Pendência para a Fase 9:** conferir que nenhuma instrução de agente contém texto do regulamento (o especialista só descobre os capítulos via `listar_capitulos`).

### Registro da Fase 9 (2026-09-27)

- **F9-1 — Implementado:** `aurora/agent.py` com `assistente_aurora` (principal), `especialista_reservas` e `especialista_visitantes` (`sub_agents`), `especialista_regulamento` (`AgentTool`), `root_agent` e `app = App(name="aurora", resumability_config=ResumabilityConfig(is_resumable=True))`. O `adk web` carrega `aurora.agent.app` (prioriza `app` sobre `root_agent`): `uv run adk web .` lista só `aurora`. `.adk/` (sessões locais do adk web) foi adicionado ao `.gitignore`.
- **F9-2 — BLOQUEIO: cota gratuita do Gemini.** Validação com modelo real (scratchpad `valida_fase9.py`): passos 3, 4, 5, 6 e 7 OK (roteamento ao especialista_reservas, cancelamento sem pendência, quadra direto, salão pendente com área/data/taxa, nada gravado, sem vazamento de RSV-4821/Marina). Depois: `429 RESOURCE_EXHAUSTED`, `quotaId=GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue=20`, `model=gemini-3.8-flash` (alvo do alias `gemini-flash-latest`). **20 requisições/dia por modelo não comportam o fluxo do avaliador (dezenas de chamadas).** A documentação (ai.google.dev/gemini-api/docs/rate-limits) não publica os números por modelo; eles ficam em https://aistudio.google.com/rate-limit. O Tier 1 exige vincular uma conta de faturamento (liberado na hora). **Resolvido:** o usuário ativou o faturamento (Tier 1: 1K RPM e 10K RPD para `gemini-3.8-flash` e `gemini-3.5-flash`). No plano gratuito, **todos** os modelos de texto têm 20 RPD, então o avaliador precisa de uma chave com faturamento; registrar isso no README (Fase 15).
- **F9-3 — Validação completa com modelo real (Tier 1):** 20/20 checagens OK, sem 429/503. Trilhas observadas:
  - passo 3: principal → `transfer_to_agent` → `especialista_reservas:listar_minhas_reservas`, sem RSV-4821/Marina em resposta e eventos;
  - passo 4: `cancelar_reserva` → "não há reserva do seu apartamento", com RSV-4821 intacta;
  - passos 5 e 6: sem pendência;
  - passos 7 e 8: pendência `{area, data, taxa}`, negar não grava e aprovar grava 1 (retomada no especialista, sessão SQLite);
  - passo 10 (S2): "já está ocupado", sem pendência, sem 302/RSV-4821;
  - passo 11: `especialista_reservas` → `especialista_visitantes:autorizar_visitante`, pendência `{nome, data}`, grava só após aprovar;
  - passo 12: → `assistente_aurora:especialista_regulamento` (AgentTool), "9h às 20h", eventos sem trechos de outros capítulos. Instruções dos agentes sem texto do regulamento.
- **F9-4 — Idempotência confirmada na retomada:** o `tool_context.function_call_id` na execução retomada é o id da chamada original (ex.: reserva `RSV-UJ36XQ` com `operacao_id=call_74494` = `originalFunctionCall.id` da confirmação `adk-76d75d4e`). Fecha a pendência de F7-2.
- **F9-5 — Observação de UX (não é requisito):** no passo 3, o especialista de reservas respondeu as reservas e ofereceu transferir para visitantes em vez de responder os dois. Avaliar ajuste de instrução na Fase 14 se sobrar tempo.

# Riscos e pontos de atenção

- **Retomada da confirmação (maior risco):** a resposta precisa chegar ao agente que pediu; depende de topologia, bloqueios de transferência, `App` e session service. Testar com SQLite persistido e após reinício.
- **Vazamento de dados de terceiros:** o modelo pode repetir dados que uma tool retornar; por isso as tools nunca devem retornar dados alheios (a proteção está no retorno, não no prompt). Atenção ao `302` isolado no passo 10.
- **Regulamento nos eventos:** qualquer retorno de tool vai para os eventos; a tool deve devolver apenas o capítulo pertinente. Verificar também eventos gerados por especialistas.
- **Concorrência no SQLite:** lock de escrita pode virar erro 500; tratar com timeout/transação e converter conflito em resposta de negócio.
- **Limites de cota do Gemini:** o fluxo faz dezenas de chamadas; escolher modelo compatível e evitar chamadas redundantes.
- **`uv` ausente no ambiente atual:** resolvido na Fase 1.
- **Instabilidade do Gemini (503):** retentativas + modelo configurável; validar o fluxo completo com o modelo escolhido (F2-9).
- **Resposta duplicada re-executa tool no ADK (F2-8):** 409 antes do Runner + gravação idempotente.
- **Substituição do README:** após a Fase 15 o enunciado só existe em `git show be87e1d:README.md`.

# Controle de progresso

| Fase    | Status   | Dependências     | Resultado |
| ------- | -------- | ---------------- | --------- |
| Fase 1  | Concluída | -               | uv 0.12.19, fork público, chave válida no `.env` |
| Fase 2  | Concluída | Fase 1          | Confirmação + SQLite + reinício validados em protótipo; achados F2-1..F2-11 |
| Fase 3  | Concluída | Fase 2          | D1–D11 registradas; cada garantia mapeada para decisões |
| Fase 4  | Concluída | Fase 3          | `uv sync` OK, ADK 2.10.0 fixado, `aurora-api` sobe na 8000, stubs criados |
| Fase 5  | Concluída | Fase 4          | `banco.py`/`dominio.py`/`restaurar.py`; 22/22 checagens, concorrência 10x8 processos OK |
| Fase 6  | Concluída | Fase 5          | Rotas de verificação iguais ao contrato (passo 1 do avaliador OK) |
| Fase 7  | Concluída | Fase 5          | Tools de reservas/visitantes; 31/31 checagens, sem vazamento de dados do 302 |
| Fase 8  | Concluída | Fase 4          | Parser por capítulo + tools; 12/12 checagens (instruções dos agentes conferidas na Fase 9) |
| Fase 9  | Concluída | Fases 7, 8      | Agentes + App resumable; passos 3–12 com modelo real, 20/20 checagens; faturamento Tier 1 ativado |
| Fase 10 | Pendente | Fases 6, 9       |           |
| Fase 11 | Pendente | Fase 10          |           |
| Fase 12 | Pendente | Fase 11          |           |
| Fase 13 | Pendente | Fase 11          |           |
| Fase 14 | Pendente | Fases 12, 13     |           |
| Fase 15 | Pendente | Fase 14          |           |
| Fase 16 | Pendente | Fase 15          |           |

Status possíveis: `Pendente`, `Em andamento`, `Bloqueada`, `Concluída`.

# Instruções para próximas sessões

Durante a execução futura deste plano:

1. Sempre leia `README.md` e `PLAN_EXECUTION.MD` antes de iniciar (se o README já tiver sido substituído na Fase 15, leia o enunciado com `git show be87e1d:README.md`).
2. Consulte o Controle de progresso.
3. Localize a primeira fase ainda não concluída.
4. Execute somente essa fase, salvo quando houver uma dependência explícita.
5. Não refaça fases marcadas como `Concluída`.
6. Atualize os checkboxes conforme as tarefas forem realizadas.
7. Ao terminar uma fase, execute todas as validações previstas.
8. Somente marque a fase como `Concluída` se os critérios de aceite forem satisfeitos.
9. Registre no plano qualquer decisão relevante descoberta durante a execução (seção "Decisões registradas").
10. Atualize o Controle de progresso.
11. Informe claramente qual é a próxima fase a ser executada.
12. Não avance automaticamente para a próxima fase quando houver falhas, dúvidas ou critérios de aceite não atendidos.

