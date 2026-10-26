# Harness — plugin do Crivonansky

Ponto de entrada único do harness de desenvolvimento assistido para o sistema legado
(PHP/MySQL/JS). Recebe blocos `crivonansky` (colados do LLM), executa tarefas do catálogo
e devolve um bloco `crivonansky-result` (no terminal e no clipboard).

A troca com o LLM é **manual**: você copia o bloco do chat, cola na TUI (ou usa
`exec --clip`) e copia o resultado de volta.

## Uso

```text
/harness exec --clip | --file F | --stdin [--yes] [--dry-run]
/harness run <task> [--param k=v ...] [--yes] [--dry-run]
/harness ask "<pergunta>" [--context rag,code,db]
/harness prompt
/harness tasks
/harness runs [--last N]
/harness env:check
```

Opção global: `--config CAMINHO` (ou a variável `HARNESS_CONFIG`).

## Exemplos

```powershell
# lê o bloco que está no clipboard
python crivonansky.py harness exec --clip

# executa uma tarefa direto
python crivonansky.py harness run db:snapshot
python crivonansky.py harness run db:schema --table tb_veiculos
python crivonansky.py harness run db:links
python crivonansky.py harness run docs:import
python crivonansky.py harness run code:index
python crivonansky.py harness run rag:sync
python crivonansky.py harness run rag:search --query "como cadastrar cliente" --source_kind db_schema

# copia o prompt de instrução do LLM para o clipboard
python crivonansky.py harness prompt
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
| `code:query` | read | Consulta o grafo |
| `code:impact` | read | Impacto de alterar um símbolo |
| `db:snapshot` | read | Schema MySQL (docker exec ou dump) |
| `db:schema` | read | Markdown de uma tabela |
| `db:query` | read | SELECT/SHOW/DESCRIBE/EXPLAIN |
| `db:links` | read | SQL embutido + FKs inferidas + includes |
| `docs:import` | read | Manuais e tickets |
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

## Configuração

O `harness.yaml` fica em `C:\projetos\harness-workspace\harness.yaml` (ou no diretório
atual / `HARNESS_CONFIG`). Veja o exemplo em `specs/harness-spec-v1.md` §4.6.

## Testes

```powershell
.venv\Scripts\python.exe -m pytest tests/harness -q
```
