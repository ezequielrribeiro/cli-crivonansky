<?php
// Novo aluguel.

require_once __DIR__ . '/../includes/conexao.php';
require_once __DIR__ . '/../includes/funcoes.php';

$conn = conectar();
$mensagem = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $idCli = (int) ($_POST['id_cli'] ?? 0);
    $idVei = (int) ($_POST['id_vei'] ?? 0);
    $dtIni = $_POST['dt_ini'] ?? '';
    $dtFim = $_POST['dt_fim'] ?? '';

    // Busca a diária da categoria do veículo.
    $sql = "SELECT c.vl_diaria
            FROM tb_veiculos v
            JOIN tb_categorias c ON c.id_cat = v.id_cat
            WHERE v.id_vei = $idVei";
    $res = $conn->query($sql);
    $diaria = (float) $res->fetch_assoc()['vl_diaria'];

    $total = calcular_total($diaria, $dtIni, $dtFim);

    $sql = "INSERT INTO tb_alugueis (id_cli, id_vei, dt_ini, dt_fim, vl_total, st)
            VALUES ($idCli, $idVei, '$dtIni', '$dtFim', $total, 1)";

    if ($conn->query($sql)) {
        $conn->query("UPDATE tb_veiculos SET st = 2 WHERE id_vei = $idVei");
        $mensagem = 'Aluguel confirmado.';
    } else {
        $mensagem = 'Erro ao confirmar aluguel.';
    }
}

$clientes = $conn->query("SELECT id_cli, nome FROM tb_clientes WHERE st = 1");
$veiculos = $conn->query("SELECT id_vei, placa, modelo FROM tb_veiculos WHERE st = 1");
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Novo aluguel</title></head>
<body>
    <h1>Novo aluguel</h1>
    <?php if ($mensagem): ?><p><?= $mensagem ?></p><?php endif; ?>
    <form method="post">
        <label>Cliente:
            <select name="id_cli">
                <?php while ($c = $clientes->fetch_assoc()): ?>
                    <option value="<?= $c['id_cli'] ?>"><?= $c['nome'] ?></option>
                <?php endwhile; ?>
            </select>
        </label><br>
        <label>Veículo:
            <select name="id_vei">
                <?php while ($v = $veiculos->fetch_assoc()): ?>
                    <option value="<?= $v['id_vei'] ?>"><?= $v['placa'] ?> — <?= $v['modelo'] ?></option>
                <?php endwhile; ?>
            </select>
        </label><br>
        <label>Início: <input type="date" name="dt_ini"></label><br>
        <label>Fim: <input type="date" name="dt_fim"></label><br>
        <button type="submit">Confirmar</button>
    </form>
</body>
</html>
