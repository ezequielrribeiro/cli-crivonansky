# Harness — plugin autocontido do Crivonansky

Ponto de entrada único do harness de desenvolvimento assistido para o sistema legado
(PHP/MySQL/JS). Recebe blocos `crivonansky` (colados do LLM), executa tarefas do catálogo
e devolve um bloco `crivonansky-result` (no terminal e no clipboard).

A troca com o LLM é **manual**: você copia o bloco do chat, cola na TUI (ou usa
`exec --clip`) e copia o resultado de volta.

## Tudo dentro do plugin

A partir desta versão, o harness não depende de scripts em `C:\projetos`:

```text
commands/complements/harness/
├── install.ps1                  # instalador (venvs + clones + config)
├── requirements.txt             # deps Python do plugin
├── harness.example.yaml         # template da configuração
├── fixture/exemplo-locadora/    # fixture RotaCar (versionada)
├── workspace/                   # harness.yaml + knowledge/ + runs/ (gitignored)
├── vendor/                      # local-rag-system + codeknow (gitignored)
└── .venv/                       # deps do plugin + codeknow (gitignored)
```

O `install.ps1` clona `local-rag-system` e `codeknow` em `vendor/`, cria o venv do
plugin e o venv do RAG, e gera `workspace/harness.yaml` com caminhos absolutos.
O pacote `bootstrap.py` adiciona o site-packages do plugin ao `sys.path` do
crivonansky quando o venv do host não tem as dependências.

> **Módulos do plugin não podem ter nome de módulo da stdlib.** O plugin já teve um
> `types.py`, que sombreava o `types` da biblioteca padrão quando a pasta do harness
> entrava no `sys.path` (subprocessos do pip, execução a partir da pasta) e quebrava
> a instalação. O arquivo hoje é `task_types.py` e
> `tests/harness/test_package_layout.py` impede a reincidência.

## Instalação

O plugin é instalado por `/harness install` (TUI) ou pelo comando equivalente:

```powershell
python crivonansky.py harness install
```

Também é possível executar o instalador diretamente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File commands\complements\harness\install.ps1
```

### O que o `install` faz

1. localiza o Python 3.13+ (ver abaixo) e valida Git e Docker (este último é opcional
   com `--skip-docker`);
2. confere `requirements.txt` e a fixture e testa a escrita em `vendor/` e `workspace/`;
3. clona/atualiza `local-rag-system` e `codeknow` em `vendor/`;
4. cria `commands/complements/harness/.venv` e instala `requirements.txt`;
5. instala `codeknow` em modo editável nesse venv;
6. cria/reaproveita o venv do RAG em `vendor/local-rag-system/.venv`, instala
   `requirements.txt` e extras (`scikit-learn`, `requests`, `pytest`, `httpx`);
7. gera `workspace/harness.yaml` a partir de `harness.example.yaml`, substituindo o
   marcador de raiz do plugin pelo caminho absoluto.

O comando é idempotente e **retomável**: cada etapa que toca o disco tem retry (3
tentativas), venv pela metade e clone interrompido são detectados e refeitos, e o
stderr de `git`/`pip` não aborta mais o script (gotcha do PowerShell 5.1 com
`$ErrorActionPreference = "Stop"`). Rodar de novo após uma falha retoma do ponto
problemático. Ele **não** sobe contêiner nem inicia a API do RAG.

### Descoberta do Python

O instalador procura, nesta ordem: `-PythonExe`, `HARNESS_PYTHON`, `py -0p`,
`C:\Python3*`, `%LOCALAPPDATA%\Programs\Python`, `%LOCALAPPDATA%\Python`, o registro
(`HKLM`/`HKCU\SOFTWARE\Python\PythonCore`) e o `PATH` (ignorando o atalho da Microsoft
Store). Se houver um 3.13 ele é preferido, porque é a versão em que as dependências do
RAG (`torch`/`sentence-transformers`) são validadas; 3.14+ funciona, mas pode não ter
wheel para alguma dependência — nesse caso o próprio instalador avisa.

Se a detecção falhar, informe o caminho:

```powershell
python crivonansky.py harness install --python C:\Python313\python.exe
# ou: setx HARNESS_PYTHON C:\Python313\python.exe
```

| Flag | Efeito |
|---|---|
| `--check-only` | Só valida pré-requisitos, caminhos e permissão de escrita; não instala |
| `--skip-docker` | Permite instalar em máquina sem Docker |
| `--force` | Regenera `workspace/harness.yaml` mesmo se já existir |
| `--python CAMINHO` | Força o interpretador (3.13+) usado nos venvs |

Para reinstalar dependências do zero, remova `vendor/` e/ou `.venv/` e rode
`/harness install` novamente.

## Operação

| Subcomando | O que faz | Flags |
|---|---|---|
| `start` | Sobe MySQL/PHP da fixture e a API do RAG | `--no-rag`, `--no-docker` |
| `stop` | Para o RAG e derruba a fixture | `--purge` |
| `prepare` | `start` + coleta completa + `rag:sync` | `--full`, `--no-rag` |
| `preprocess` | codeknow (cópia + grafo + relatório + wiki) | `--sync`, `--full`, `--no-codeknow`, `--no-wiki` |
| `config` | Mostra caminhos do plugin/workspace/vendor/fixture/venv | — |

```text
/harness start                # MySQL/PHP + API do RAG
/harness start --no-rag       # só a fixture
/harness start --no-docker    # só a API do RAG (não inicia a fixture)
/harness stop                 # para o RAG e a fixture
/harness stop --purge         # e remove o volume do MySQL
/harness prepare              # start + db:snapshot, db:links, docs:import, code:preprocess, rag:sync
/harness prepare --full       # ingestão completa do RAG
/harness preprocess --sync    # code:preprocess + rag:sync
/harness preprocess --no-codeknow  # só copia as fontes
/harness config               # mostra caminhos usados
```

**`start`** verifica o daemon do Docker, executa `fixture/exemplo-locadora/setup.ps1`
(`docker compose up -d --build`, aguarda os `healthcheck` e cria os usuários MySQL) e
define `HARNESS_DB_USER=rotacar_read` / `HARNESS_DB_PASSWORD=readpass` se ainda não
existirem. Se `--no-rag` não for passado, inicia a API em `http://127.0.0.1:8000`.

- `--no-rag`: sobe só a fixture.
- `--no-docker`: não inicia a fixture; sobe só a API do RAG. Não exige Docker e não
  toca nos contêineres.
- `--no-docker --no-rag`: não inicia nada (no-op) e retorna `nada a iniciar`.

**`prepare`** para no primeiro erro e informa em qual tarefa parou. A ordem é fixa:
`db:snapshot` → `db:links` → `docs:import` → `code:preprocess` → `rag:sync`.

**`preprocess`** não exige Docker; trabalha sobre `legacy.repo_path`. `--sync` encadeia
o `rag:sync`; `--full` força o codeknow e a ingestão completa; `--no-wiki` gera grafo e
relatório sem exportar a wiki.

## Uso do contrato

```text
/harness exec --clip | --file F | --stdin [--yes] [--dry-run]
/harness run <task> [--param k=v ...] [--k v] [--yes] [--dry-run]
/harness ask "<pergunta>" [--context rag,code,db]
/harness prompt
/harness tasks
/harness runs [--last N]
/harness hooks install|uninstall|status
/harness env:check
```

Opção global: `--config CAMINHO` (ou a variável `HARNESS_CONFIG`).

### `exec`

Lê blocos `crivonansky` de uma das fontes:

- `--clip` (padrão): área de transferência;
- `--file CAMINHO`: arquivo;
- `--stdin`: entrada padrão.

Cada bloco é validado contra o contrato e o catálogo antes de executar. Blocos
inválidos, tarefa desconhecida ou parâmetro fora do schema retornam `error`/`denied`
sem executar nada. Vários blocos são executados em ordem até
`output.max_blocks_per_message` (padrão 5), parando no primeiro status negativo, salvo
`continue_on_failure: true`. `--yes` é ignorado para blocos vindos de resposta do LLM;
`--dry-run` valida bloco e política, mas não executa.

### `run`

Executa uma tarefa do catálogo diretamente. Parâmetros aceitam `--param k=v` ou
`--k v`:

```text
/harness run db:schema --table tb_veiculos
/harness run db:schema --param table=tb_veiculos
/harness run rag:search --query "como cadastrar cliente" --source_kind db_schema
```

Tarefas de leitura rodam sem confirmação. Tarefas de escrita pedem `y/N`; `--yes` pula a
confirmação somente na linha de comando. `--dry-run` valida a tarefa e a política, mas
não executa.

### `ask` / `prompt`

`ask` monta um prompt com a pergunta e, conforme `--context`, inclui:

- `rag`: trechos de `rag:search` (requer a API do RAG no ar);
- `code`: trechos de `code:query` (requer o grafo gerado);
- `db`: resumo de tabelas/colunas de `workspace/knowledge/db/schema-catalog.json`
  (requer `db:snapshot`).

O padrão é `rag,code`. O texto é copiado para o clipboard e impresso. `prompt` copia
apenas o prompt de instrução do LLM (contrato + regras + catálogo).

### `tasks` / `runs` / `hooks` / `env:check`

- `tasks`: lista `tarefa`, `intent` (`read`/`write`) e descrição.
- `runs --last N`: lista as últimas execuções de `workspace/runs/runs.jsonl`.
- `hooks install|uninstall|status`: instala/remove hooks `post-commit` e `post-merge` no
  repositório legado; `status` mostra o log em `workspace/runs/hooks.log`.
- `env:check`: verifica `git`, `docker info`, `codeknow --version` e `GET /health` do
  RAG. Retorna `failure` se algum item falhar.

## Flags comuns

| Flag | Aplicação | Efeito |
|---|---|---|
| `--config CAMINHO` | qualquer subcomando | Usa outro `harness.yaml` |
| `--yes` | `run`, `exec` | Pula confirmação de escrita (não vale para blocos do LLM) |
| `--dry-run` | `run`, `exec` | Valida tarefa/bloco e política, sem executar |
| `--param k=v` | `run` | Parâmetro da tarefa |
| `--clip` / `--file F` / `--stdin` | `exec` | Fonte dos blocos |
| `--last N` | `runs` | Quantidade listada (padrão 10) |
| `--context rag,code,db` | `ask` | Contextos do prompt |
| `--no-rag` | `start`, `prepare` | Não inicia a API do RAG |
| `--no-docker` | `start` | Não inicia a fixture; sobe somente o RAG |
| `--purge` | `stop` | Remove o volume do MySQL |
| `--full` | `prepare`, `preprocess` | Força codeknow/ingestão completa |
| `--force` | `install` | Regenera o `harness.yaml` |
| `--skip-docker` | `install` | Não exige Docker |
| `--check-only` | `install` | Só valida |
| `--no-codeknow` | `preprocess` | Só copia as fontes |
| `--no-wiki` | `preprocess` | Não exporta a wiki |

## Status e artefatos

| Status | Significado |
|---|---|
| `success` | Tarefa concluída; exit code 0 |
| `failure` | Rodou, mas o resultado foi negativo (ex.: teste falhou) |
| `error` | Erro de bloco, parâmetro ou do harness |
| `denied` | Barrado pela política ou pelo usuário |
| `timeout` | O prazo expirou; o processo foi encerrado |

O `exec` só retorna sucesso se todos os blocos executados tiverem `status: success`.
Cada execução grava `workspace/runs/<id>/command.yaml`, `result.md` e `full.log`, além
de uma linha em `workspace/runs/runs.jsonl`. O clipboard recebe o bloco truncado por
`output.max_chars.clipboard` (padrão 12.000 caracteres); o log completo fica em disco.

A API do RAG grava PID e logs em `workspace/runs/rag-api.pid`, `rag-api.log` e
`rag-api.err.log`.

## Exemplos

```powershell
python crivonansky.py harness run db:snapshot
python crivonansky.py harness run db:schema --table tb_veiculos
python crivonansky.py harness run db:links
python crivonansky.py harness run docs:import
python crivonansky.py harness run code:index
python crivonansky.py harness run code:preprocess
python crivonansky.py harness run rag:serve --action start
python crivonansky.py harness run rag:sync
python crivonansky.py harness run rag:search --query "como cadastrar cliente" --source_kind db_schema
```

## Contrato

Entrada (um bloco por ação):

```crivonansky
harness: 1
task: db:schema
params:
  table: tb_veiculos
return: auto
```

Saída:

```crivonansky-result
harness: 1
id: c-0007
task: db:schema
status: success
exit_code: 0
duration_ms: 12
summary: "schema da tabela tb_veiculos"
truncated: false
details: |
  # Tabela: tb_veiculos
  ...
```

`status`: `success` | `failure` | `error` | `denied` | `timeout`.

## Tarefas

| Tarefa | Intent | Descrição |
|---|---|---|
| `env:check` | read | Verifica git, docker, codeknow e RAG |
| `context:pack` | read | Empacota arquivos em Markdown |
| `file:read` | read | Lê arquivo com números de linha |
| `code:index` | read | Gera o grafo com codeknow |
| `code:preprocess` | read | Copia fontes + grafo + wiki do codeknow p/ o RAG |
| `code:query` | read | Consulta o grafo |
| `code:impact` | read | Impacto de alterar um símbolo |
| `db:snapshot` | read | Schema MySQL (docker exec ou dump) |
| `db:schema` | read | Markdown de uma tabela |
| `db:query` | read | SELECT/SHOW/DESCRIBE/EXPLAIN |
| `db:links` | read | SQL embutido + FKs inferidas + includes + visões `tables/*.md` |
| `docs:import` | read | Manuais e tickets |
| `rag:serve` | read | Inicia/para/consulta a API local do RAG |
| `rag:sync` | read | Publica no RAG e ingere |
| `rag:search` | read | Busca no RAG |
| `git:run` | read/write | Comando git |
| `shell:run` | write | Shell do Windows |
| `py:run` | write | Script/módulo Python |
| `docker:exec` | write | Comando no contêiner |
| `logs:tail` | read | Logs de contêiner |
| `patch:apply` | write | Aplica diff e verifica |
| `test:run` / `verify` / `lint` | read | Pipelines do `harness.yaml` |
| `prompt` | read | Prompt do LLM no clipboard |

Tarefas `write` pedem confirmação. Blocos vindos do LLM nunca aceitam `--yes`.

## Progresso das tarefas longas

`db:links`, `code:preprocess` e `install` publicam o andamento em tempo real, porque o
`CommandExecutor` captura o `stdout` (um `print` só apareceria no fim):

- **TUI:** as linhas aparecem no painel de saída enquanto a tarefa roda (a execução
  acontece em um worker, então a interface não trava);
- **CLI** (`python crivonansky.py harness run db:links`): as linhas vão para o `stderr`
  quando ele é um terminal;
- **log:** sempre gravado em `<run_dir>/progress.log` (ou
  `workspace/install.log`/`workspace/prepare.log`), útil quando a saída é capturada.

Exemplo de linha:

```text
[db:links] 1234/9876 arquivo(s) (12.5%) — 210.4 MB lidos — 18.2 MB/s — ETA 08:12 — 5120 vínculo(s)
```

`HARNESS_PROGRESS` controla o canal: `auto` (padrão), `log`, `stderr` ou `off`.

O `db:links` foi otimizado para repositórios grandes: cada instrução SQL é parseada uma
única vez (o parse alimenta vínculos e FKs) e o resultado é memoizado (o mesmo SQL
costuma se repetir no legado); a linha de cada ocorrência usa índice em vez de varrer o
arquivo; bundles `*.min.js`/`*.bundle.js`/`*.pack.js` são ignorados. Para limitar o custo
em arquivos gigantes, use `--max_file_mb N`:

```text
/harness run db:links --max_file_mb 8
```

## Configuração

Gerada em `workspace/harness.yaml` pelo `install.ps1`. O template
(`harness.example.yaml`) usa caminhos relativos ao plugin; o instalador troca o
marcador `{{PLUGIN_ROOT}}` pelo caminho absoluto. Também é possível apontar para
outro arquivo com `--config` ou `HARNESS_CONFIG`.

## Adicionar um projeto real

A fixture `exemplo-locadora` é só referência. Para usar o harness com um projeto real,
aponte o `harness.yaml` para ele. Durante a coleta, o harness não escreve no repositório
legado; ações de escrita (`patch:apply`, `shell:run` etc.) passam pela política de
confirmação.

### 1. Configuração

Edite `workspace/harness.yaml` (ou crie um config por projeto e use `--config` /
`HARNESS_CONFIG`). Se quiser versionar a configuração, mantenha o YAML fora do
`workspace/` (que é gitignored) e aponte `HARNESS_CONFIG` para ele. Exemplo:

```yaml
harness_version: 1
workspace: C:/projetos/harness-configs/meu-legado/workspace

legacy:
  repo_path: C:/projetos/meu-legado
  app_container: meu_php
  db_container: meu_mysql
  db_name: meu_banco
  db_user_env: HARNESS_DB_USER
  db_password_env: HARNESS_DB_PASSWORD
  manuals_path: C:/projetos/meu-legado/docs/manuais
  tickets_path: C:/projetos/meu-legado/docs/tickets
  schema_dump: C:/projetos/meu-legado/banco/dump-estrutura.sql

tools:
  codeknow: C:/projetos/cli-crivonansky/commands/complements/harness/.venv/Scripts/codeknow.exe
  python: C:/projetos/cli-crivonansky/commands/complements/harness/.venv/Scripts/python.exe
  rag:
    path: C:/projetos/cli-crivonansky/commands/complements/harness/vendor/local-rag-system
    python: C:/projetos/cli-crivonansky/commands/complements/harness/vendor/local-rag-system/.venv/Scripts/python.exe
    api: http://127.0.0.1:8000

policy:
  allowed_roots:
    - C:/projetos/meu-legado
    - C:/projetos/harness-configs/meu-legado/workspace

pipelines:
  verify:
    - docker:exec: { container: meu_php, command: "php -l index.php" }
  test:run:
    - docker:exec: { container: meu_php, command: "vendor/bin/phpunit --colors=never {filter}" }
```

Campos essenciais:

| Campo | Usado por | Observação |
|---|---|---|
| `legacy.repo_path` | `code:preprocess`, `db:links`, `git:run`, hooks | Repositório legado |
| `legacy.app_container` | `docker:exec`, `logs:tail`, pipelines | Contêiner da aplicação |
| `legacy.db_container` | `db:snapshot` live, `db:query` | Contêiner MySQL |
| `legacy.db_name` | `db:snapshot`, `db:query` | Banco consultado |
| `legacy.manuals_path` | `docs:import` | Aceita `.pdf`, `.md`, `.txt` |
| `legacy.tickets_path` | `docs:import` | Lê `.json` de tickets |
| `legacy.schema_dump` | `db:snapshot` fallback | Estrutura sem dados |
| `policy.allowed_roots` | `file:read`, `shell:run`, `git:run`, `patch:apply` | Inclua repo e workspace; restringe `cwd`/caminhos, não é um sandbox de comandos |

Credenciais sempre por ambiente:

```powershell
$env:HARNESS_DB_USER = "harness_read"
$env:HARNESS_DB_PASSWORD = "sua-senha"
```

> Não rode `install --force` depois de personalizar o config: ele regenera o
> `harness.yaml` a partir do template.

### 2. Documentação

```text
meu-legado/docs/
├── manuais/
│   ├── manual-usuario.pdf
│   └── manual-tecnico.md
└── tickets/
    └── tickets.json
```

- Manuais `.pdf/.md/.txt` são copiados para `knowledge/docs/manuals/` (RAG `user`).
- Tickets em JSON viram Markdown em `knowledge/docs/tickets/` (RAG `support`); anexos
  citados em `anexos` são copiados para `tickets/anexos/`.
- Outros formatos de ticket não são convertidos: coloque-os em `manuais/` ou converta
  para o JSON.

Formato do `tickets.json`:

```json
{
  "tickets": [
    {
      "id": "T-001",
      "titulo": "Erro ao cadastrar cliente",
      "descricao": "Ao salvar, o sistema exibe erro 500.",
      "testadores": ["qa@empresa.com"],
      "desenvolvedores": ["dev@empresa.com"],
      "anexos": ["evidencias/erro.png"],
      "comentarios": [
        { "autor": "dev@empresa.com", "data": "2026-10-30", "texto": "Corrigido." }
      ],
      "tags": ["cadastro", "cliente"]
    }
  ]
}
```

O `docs:import` também grava `knowledge/docs/manifest.json`.

### 3. Ambiente do projeto

Suba os contêineres pelo `/environment` (cadastre o `docker-compose.yml` em
`environment_conf.json`) ou direto com `docker compose`. **Não use `start`/`prepare`
para um projeto real**, porque eles sobem a fixture RotaCar. Use `start --no-docker`
apenas se quiser iniciar só a API do RAG.

```powershell
docker ps --format "{{.Names}} {{.Status}}"
python crivonansky.py harness run env:check
```

Sem Docker, use `db:snapshot --source dump`; `db:query`, `docker:exec` e `logs:tail`
ficam indisponíveis.

### 4. Coleta e indexação

```powershell
python crivonansky.py harness run db:snapshot
python crivonansky.py harness run db:links
python crivonansky.py harness run docs:import
python crivonansky.py harness run code:preprocess
python crivonansky.py harness run rag:serve --action start
python crivonansky.py harness run rag:sync
```

Rode `code:preprocess` antes de `db:links` para melhorar o campo `symbol` (resolvido pelo
grafo). `rag:sync --full` reindexa tudo; a ingestão não precisa da API, só `rag:search`.

### 5. Validação

```powershell
python crivonansky.py harness run env:check
python crivonansky.py harness run db:schema --table tb_clientes
python crivonansky.py harness run db:query --sql "SELECT COUNT(*) FROM tb_clientes"
python crivonansky.py harness run rag:search --query "como cadastrar cliente" --source_kind db_schema
python crivonansky.py harness run code:query --q "nome_da_funcao"
```

Confira `workspace/knowledge/{db,links,docs,code}` e se `rag:search` retorna conteúdo do
seu projeto (e não da fixture).

### 6. Automação (opcional)

```powershell
python crivonansky.py harness hooks install    # post-commit/post-merge -> rag:sync
python crivonansky.py harness run verify
python crivonansky.py harness run test:run --filter MeuTeste
```

Ajuste `pipelines.verify`, `pipelines.test:run` e `pipelines.lint` para os comandos reais
do projeto.

### Checklist

- [ ] `repo_path` existe e aponta para o projeto;
- [ ] contêineres e `db_name` batem com o ambiente;
- [ ] `HARNESS_DB_USER`/`HARNESS_DB_PASSWORD` definidos;
- [ ] `manuals_path`/`tickets_path` existem;
- [ ] `schema_dump` contém só estrutura;
- [ ] `allowed_roots` inclui repo e workspace;
- [ ] `pipelines` ajustadas;
- [ ] `env:check`, `db:snapshot`, `db:links`, `docs:import`, `code:preprocess` e
  `rag:sync` concluíram;
- [ ] `rag:search` retorna conteúdo do projeto.

O passo a passo completo, com exemplos adicionais, está no `README.md` raiz do
repositório do harness.

## Testes

```powershell
# de dentro de cli-crivonansky
.\.venv\Scripts\python.exe -m pytest tests/harness -q

# ou com o venv do plugin
commands\complements\harness\.venv\Scripts\python.exe -m pytest tests/harness -q
```

## Troubleshooting da instalação

| Sintoma | Causa provável | Ação |
|---|---|---|
| `Python 3.13+ (nao encontrado)` mesmo com Python instalado | o `python` do `PATH` é o atalho da Microsoft Store (sai com 9009) e a instalação está fora dos caminhos varridos | `harness install --python C:\caminho\python.exe` ou defina `HARNESS_PYTHON` |
| Falha no meio do `pip install`/`git clone` que some ao rodar de novo | clone/venv parcial ou arquivo travado (antivírus) | rode de novo: o instalador detecta o estado parcial e refaz a etapa (com retry) |
| `Acesso negado` ao criar `vendor/`/`workspace/` | pasta dentro de `Program Files`/OneDrive ou sem permissão | mova o repositório para uma pasta do usuário; `harness install --check-only` testa a escrita |
| RAG não instala por falta de wheel | Python mais novo que 3.13 (ex.: 3.14) sem wheel de `torch` | instale o 3.13 e rode `harness install --python C:\Python313\python.exe` |
| `db:links` parece travado | saída do comando é capturada até o fim | veja o progresso no painel da TUI, no `stderr` da CLI ou em `<run_dir>/progress.log` |
