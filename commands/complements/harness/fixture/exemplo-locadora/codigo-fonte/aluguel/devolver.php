<?php
// Devolução de veículo.

require_once __DIR__ . '/../includes/conexao.php';
require_once __DIR__ . '/../includes/funcoes.php';

$conn = conectar();
$mensagem = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $idAlu = (int) ($_POST['id_alu'] ?? 0);
    $dtDev = $_POST['dt_dev'] ?? '';
    $vlPago = (float) ($_POST['vl_pago'] ?? 0);
    $forma = limpar($_POST['forma'] ?? 'dinheiro');

    $conn->query("UPDATE tb_alugueis SET dt_dev = '$dtDev', st = 2 WHERE id_alu = $idAlu");

    $sql = "INSERT INTO tb_pagamentos (id_alu, vl_pago, dt_pag, forma)
            VALUES ($idAlu, $vlPago, NOW(), '$forma')";
    $conn->query($sql);

    $conn->query("UPDATE tb_veiculos v
                  JOIN tb_alugueis a ON a.id_vei = v.id_vei
                  SET v.st = 1
                  WHERE a.id_alu = $idAlu");

    $mensagem = 'Devolução registrada.';
}

$abertos = $conn->query("SELECT id_alu, id_cli, id_vei, dt_ini, dt_fim
                         FROM tb_alugueis WHERE st = 1");
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Devolução</title></head>
<body>
    <h1>Devolução</h1>
    <?php if ($mensagem): ?><p><?= $mensagem ?></p><?php endif; ?>
    <form method="post">
        <label>Aluguel:
            <select name="id_alu">
                <?php while ($a = $abertos->fetch_assoc()): ?>
                    <option value="<?= $a['id_alu'] ?>">#<?= $a['id_alu'] ?> — <?= $a['dt_ini'] ?> a <?= $a['dt_fim'] ?></option>
                <?php endwhile; ?>
            </select>
        </label><br>
        <label>Data de devolução: <input type="date" name="dt_dev"></label><br>
        <label>Valor pago: <input type="text" name="vl_pago"></label><br>
        <label>Forma:
            <select name="forma">
                <option value="dinheiro">Dinheiro</option>
                <option value="cartao">Cartão</option>
                <option value="pix">Pix</option>
            </select>
        </label><br>
        <button type="submit">Encerrar</button>
    </form>
</body>
</html>
