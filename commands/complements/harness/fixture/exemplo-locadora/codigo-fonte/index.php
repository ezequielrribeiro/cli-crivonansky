<?php
// Página inicial do RotaCar.

require_once __DIR__ . '/includes/conexao.php';

$conn = conectar();

$sql = "SELECT COUNT(*) AS total FROM tb_alugueis WHERE st = 1";
$res = $conn->query($sql);
$abertos = $res->fetch_assoc()['total'];
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title><?= APP_NAME ?></title>
</head>
<body>
    <h1><?= APP_NAME ?></h1>
    <p>Aluguéis em aberto: <strong><?= $abertos ?></strong></p>
    <ul>
        <li><a href="cadastro/cliente.php">Cadastro de clientes</a></li>
        <li><a href="cadastro/veiculo.php">Cadastro de veículos</a></li>
        <li><a href="aluguel/alugar.php">Novo aluguel</a></li>
        <li><a href="aluguel/devolver.php">Devolução</a></li>
    </ul>
</body>
</html>
