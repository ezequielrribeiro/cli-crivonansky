<?php
// Conexão com o banco de dados (mysqli).

require_once __DIR__ . '/../config.php';

function conectar(): mysqli
{
    $conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    if ($conn->connect_error) {
        die('Falha na conexão: ' . $conn->connect_error);
    }
    $conn->set_charset('utf8mb4');
    return $conn;
}
