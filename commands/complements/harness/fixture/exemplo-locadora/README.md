# Locadora Rota Livre Ltda — Sistema RotaCar

> Estrutura fictícia de referência para validar o harness. Nenhum dado é real.

## A empresa

**Locadora Rota Livre Ltda** é uma pequena locadora de veículos com uma única unidade.
A equipe de TI é interna e mantém um sistema próprio de gestão de aluguel de carros,
desenvolvido em **PHP + MySQL** (arquitetura procedural, sem framework), hospedado em um
contêiner Docker.

## O sistema: RotaCar

Sistema simples de gestão de aluguel de carros, com formulários para:

- cadastro de **clientes**;
- cadastro de **veículos** (e categorias);
- **aluguel** e **devolução** de veículos;
- registro de **pagamentos**.

## Ativos disponíveis para o harness

| Ativo | Local | Formato |
|---|---|---|
| Código-fonte | `codigo-fonte/` | PHP |
| Dump do banco (só estrutura) | `banco/dump-estrutura.sql` | SQL (DDL, sem dados) |
| Manual do usuário | `manuais/manual-usuario.md` | Markdown |
| Manual de instalação | `manuais/manual-instalacao.md` | Markdown |
| Tickets de tarefas | `tickets/tickets.json` | JSON |

## Estrutura de diretórios

```text
exemplo-locadora/
├── README.md
├── codigo-fonte/
│   ├── config.php
│   ├── index.php
│   ├── includes/
│   │   ├── conexao.php
│   │   └── funcoes.php
│   ├── cadastro/
│   │   ├── cliente.php
│   │   └── veiculo.php
│   └── aluguel/
│       ├── alugar.php
│       └── devolver.php
├── banco/
│   └── dump-estrutura.sql
├── manuais/
│   ├── manual-usuario.md
│   └── manual-instalacao.md
└── tickets/
    └── tickets.json
```

## Modelo de dados (resumo)

- `categorias` — categorias de veículo e valor da diária.
- `clientes` — dados cadastrais de pessoa física.
- `veiculos` — frota, vinculada a uma categoria.
- `alugueis` — contrato de aluguel (cliente + veículo + período + status).
- `pagamentos` — pagamentos vinculados a um aluguel.
- `usuarios` — operadores do sistema (perfis: admin / atendente).

## Convenções do legado (relevantes para o harness)

- Tabelas com prefixo `tb_` e colunas abreviadas (`id_cli`, `dt_ini`, `vl_total`).
- `status` numérico com significado em dicionário (ex.: `1 = ativo`, `2 = inativo`).
- SQL embutido em strings PHP (sem ORM), o que o extrator de vínculos (`db:links`) deve capturar.
- Algumas FKs não são declaradas no banco (só existem nos `JOIN`s do código).
