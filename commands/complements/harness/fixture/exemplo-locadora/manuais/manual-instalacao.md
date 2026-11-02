# Manual de Instalação — RotaCar

## 1. Requisitos

- Docker e Docker Compose.
- PHP 8.1+ (imagem `php:8.1-apache`).
- MySQL 8.0.

## 2. Estrutura de contêineres

O sistema roda em dois contêineres:

| Contêiner | Imagem | Porta |
|---|---|---|
| `rotacar_php` | `php:8.1-apache` | 8081 → 80 |
| `rotacar_mysql` | `mysql:8.0` | 3306 |

## 3. Passo a passo

1. Clone o repositório do código-fonte.
2. Suba os contêineres:

   ```bash
   docker compose up -d
   ```

3. Importe a estrutura do banco (sem dados):

   ```bash
   docker exec -i rotacar_mysql mysql -uroot -p rotacar < banco/dump-estrutura.sql
   ```

4. Configure as credenciais no arquivo `config.php`.
5. Acesse `http://localhost:8081`.

## 4. Configuração do banco

- Banco: `rotacar`.
- Usuário da aplicação: `rotacar_app` (somente leitura/escrita nas tabelas).
- O harness deve usar um usuário **somente leitura** (`rotacar_read`).

## 5. Observações

- O dump de estrutura **não contém dados**; apenas DDL.
- As credenciais não devem ser versionadas.
