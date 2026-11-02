-- ============================================================
-- RotaCar — Dump de estrutura (somente DDL, sem dados)
-- MySQL 8.0
-- ============================================================

CREATE DATABASE IF NOT EXISTS `rotacar`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `rotacar`;

-- ------------------------------------------------------------
-- Tabela: tb_categorias
-- ------------------------------------------------------------
CREATE TABLE `tb_categorias` (
  `id_cat` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID da categoria',
  `nome` VARCHAR(60) NOT NULL COMMENT 'Nome da categoria (ex.: Econômico, SUV)',
  `vl_diaria` DECIMAL(10,2) NOT NULL COMMENT 'Valor da diária em reais',
  `st` TINYINT NOT NULL DEFAULT 1 COMMENT 'Status: 1=ativo, 2=inativo',
  PRIMARY KEY (`id_cat`),
  UNIQUE KEY `uk_categorias_nome` (`nome`)
) ENGINE=InnoDB COMMENT='Categorias de veículo e valor da diária';

-- ------------------------------------------------------------
-- Tabela: tb_clientes
-- ------------------------------------------------------------
CREATE TABLE `tb_clientes` (
  `id_cli` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID do cliente',
  `nome` VARCHAR(120) NOT NULL COMMENT 'Nome completo',
  `cpf` CHAR(11) NOT NULL COMMENT 'CPF (somente dígitos)',
  `email` VARCHAR(120) DEFAULT NULL COMMENT 'E-mail de contato',
  `telefone` VARCHAR(20) DEFAULT NULL COMMENT 'Telefone com DDD',
  `endereco` VARCHAR(200) DEFAULT NULL COMMENT 'Endereço residencial',
  `st` TINYINT NOT NULL DEFAULT 1 COMMENT 'Status: 1=ativo, 2=inativo, 3=bloqueado',
  PRIMARY KEY (`id_cli`),
  UNIQUE KEY `uk_clientes_cpf` (`cpf`)
) ENGINE=InnoDB COMMENT='Dados cadastrais de clientes pessoa física';

-- ------------------------------------------------------------
-- Tabela: tb_veiculos
-- ------------------------------------------------------------
CREATE TABLE `tb_veiculos` (
  `id_vei` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID do veículo',
  `placa` CHAR(7) NOT NULL COMMENT 'Placa do veículo',
  `marca` VARCHAR(40) NOT NULL COMMENT 'Marca',
  `modelo` VARCHAR(60) NOT NULL COMMENT 'Modelo',
  `ano` SMALLINT UNSIGNED NOT NULL COMMENT 'Ano de fabricação',
  `id_cat` INT UNSIGNED NOT NULL COMMENT 'Categoria do veículo',
  `st` TINYINT NOT NULL DEFAULT 1 COMMENT 'Status: 1=disponível, 2=alugado, 3=manutenção',
  PRIMARY KEY (`id_vei`),
  UNIQUE KEY `uk_veiculos_placa` (`placa`),
  KEY `idx_veiculos_categoria` (`id_cat`),
  CONSTRAINT `fk_veiculos_categoria` FOREIGN KEY (`id_cat`)
    REFERENCES `tb_categorias` (`id_cat`)
) ENGINE=InnoDB COMMENT='Frota de veículos';

-- ------------------------------------------------------------
-- Tabela: tb_alugueis
-- ------------------------------------------------------------
CREATE TABLE `tb_alugueis` (
  `id_alu` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID do aluguel',
  `id_cli` INT UNSIGNED NOT NULL COMMENT 'Cliente',
  `id_vei` INT UNSIGNED NOT NULL COMMENT 'Veículo alugado',
  `dt_ini` DATE NOT NULL COMMENT 'Data de início',
  `dt_fim` DATE NOT NULL COMMENT 'Data prevista de devolução',
  `dt_dev` DATE DEFAULT NULL COMMENT 'Data real de devolução',
  `vl_total` DECIMAL(10,2) NOT NULL COMMENT 'Valor total do contrato',
  `st` TINYINT NOT NULL DEFAULT 1 COMMENT 'Status: 1=aberto, 2=encerrado, 3=cancelado',
  PRIMARY KEY (`id_alu`),
  KEY `idx_alugueis_cliente` (`id_cli`),
  KEY `idx_alugueis_veiculo` (`id_vei`),
  CONSTRAINT `fk_alugueis_cliente` FOREIGN KEY (`id_cli`)
    REFERENCES `tb_clientes` (`id_cli`),
  CONSTRAINT `fk_alugueis_veiculo` FOREIGN KEY (`id_vei`)
    REFERENCES `tb_veiculos` (`id_vei`)
) ENGINE=InnoDB COMMENT='Contratos de aluguel';

-- ------------------------------------------------------------
-- Tabela: tb_pagamentos
-- ------------------------------------------------------------
CREATE TABLE `tb_pagamentos` (
  `id_pag` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID do pagamento',
  `id_alu` INT UNSIGNED NOT NULL COMMENT 'Aluguel relacionado',
  `vl_pago` DECIMAL(10,2) NOT NULL COMMENT 'Valor pago',
  `dt_pag` DATETIME NOT NULL COMMENT 'Data/hora do pagamento',
  `forma` VARCHAR(20) NOT NULL COMMENT 'Forma: dinheiro, cartao, pix',
  PRIMARY KEY (`id_pag`),
  KEY `idx_pagamentos_aluguel` (`id_alu`),
  CONSTRAINT `fk_pagamentos_aluguel` FOREIGN KEY (`id_alu`)
    REFERENCES `tb_alugueis` (`id_alu`)
) ENGINE=InnoDB COMMENT='Pagamentos vinculados a aluguéis';

-- ------------------------------------------------------------
-- Tabela: tb_usuarios
-- ------------------------------------------------------------
CREATE TABLE `tb_usuarios` (
  `id_usr` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID do usuário',
  `nome` VARCHAR(120) NOT NULL COMMENT 'Nome do operador',
  `email` VARCHAR(120) NOT NULL COMMENT 'E-mail de login',
  `senha_hash` VARCHAR(255) NOT NULL COMMENT 'Hash da senha',
  `perfil` VARCHAR(20) NOT NULL DEFAULT 'atendente' COMMENT 'Perfil: admin, atendente',
  `st` TINYINT NOT NULL DEFAULT 1 COMMENT 'Status: 1=ativo, 2=inativo',
  PRIMARY KEY (`id_usr`),
  UNIQUE KEY `uk_usuarios_email` (`email`)
) ENGINE=InnoDB COMMENT='Operadores do sistema';

-- ------------------------------------------------------------
-- View: vw_alugueis_abertos
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `vw_alugueis_abertos` AS
SELECT
  a.`id_alu`,
  c.`nome` AS `cliente`,
  v.`placa`,
  v.`modelo`,
  a.`dt_ini`,
  a.`dt_fim`,
  a.`vl_total`
FROM `tb_alugueis` a
JOIN `tb_clientes` c ON c.`id_cli` = a.`id_cli`
JOIN `tb_veiculos` v ON v.`id_vei` = a.`id_vei`
WHERE a.`st` = 1;
