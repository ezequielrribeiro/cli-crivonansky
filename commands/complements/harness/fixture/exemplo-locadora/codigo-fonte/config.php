<?php
// RotaCar — Configuração do sistema
// ATENÇÃO: não versionar credenciais reais.

define('DB_HOST', getenv('ROTACAR_DB_HOST') ?: 'rotacar_mysql');
define('DB_NAME', getenv('ROTACAR_DB_NAME') ?: 'rotacar');
define('DB_USER', getenv('ROTACAR_DB_USER') ?: 'rotacar_app');
define('DB_PASS', getenv('ROTACAR_DB_PASS') ?: '');

define('APP_NAME', 'RotaCar');
define('APP_VERSION', '1.0.0');
