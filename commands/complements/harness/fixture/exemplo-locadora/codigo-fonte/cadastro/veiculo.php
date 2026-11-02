<?php
// Cadastro de veículos.

require_once __DIR__ . '/../includes/conexao.php';
require_once __DIR__ . '/../includes/funcoes.php';

$conn = conectar();
$mensagem = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $placa = strtoupper(limpar($_POST['placa'] ?? ''));
    $marca = limpar($_POST['marca'] ?? '');
    $modelo = limpar($_POST['modelo'] ?? '');
    $ano = (int) ($_POST['ano'] ?? 0);
    $idCat = (int) ($_POST['id_cat'] ?? 0);

    $sql = "INSERT INTO tb_veiculos (placa, marca, modelo, ano, id_cat, st)
            VALUES ('$placa', '$marca', '$modelo', $ano, $idCat, 1)";

    if ($conn->query($sql)) {
        $mensagem = 'Veículo cadastrado com sucesso.';
    } else {
        $mensagem = 'Erro ao cadastrar veículo.';
    }
}

$categorias = $conn->query("SELECT id_cat, nome FROM tb_categorias WHERE st = 1");
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Cadastro de veículos</title></head>
<body>
    <h1>Cadastro de veículos</h1>
    <?php if ($mensagem): ?><p><?= $mensagem ?></p><?php endif; ?>
    <form method="post">
        <label>Placa: <input type="text" name="placa"></label><br>
        <label>Marca: <input type="text" name="marca"></label><br>
        <label>Modelo: <input type="text" name="modelo"></label><br>
        <label>Ano: <input type="number" name="ano"></label><br>
        <label>Categoria:
            <select name="id_cat">
                <?php while ($c = $categorias->fetch_assoc()): ?>
                    <option value="<?= $c['id_cat'] ?>"><?= $c['nome'] ?></option>
                <?php endwhile; ?>
            </select>
        </label><br>
        <button type="submit">Salvar</button>
    </form>
</body>
</html>
