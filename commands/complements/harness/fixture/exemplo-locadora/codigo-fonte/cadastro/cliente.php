<?php
// Cadastro de clientes.

require_once __DIR__ . '/../includes/conexao.php';
require_once __DIR__ . '/../includes/funcoes.php';

$conn = conectar();
$mensagem = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $nome = limpar($_POST['nome'] ?? '');
    $cpf = preg_replace('/\D/', '', $_POST['cpf'] ?? '');
    $email = limpar($_POST['email'] ?? '');
    $telefone = limpar($_POST['telefone'] ?? '');
    $endereco = limpar($_POST['endereco'] ?? '');

    $sql = "INSERT INTO tb_clientes (nome, cpf, email, telefone, endereco, st)
            VALUES ('$nome', '$cpf', '$email', '$telefone', '$endereco', 1)";

    if ($conn->query($sql)) {
        $mensagem = 'Cliente cadastrado com sucesso.';
    } else {
        $mensagem = 'Erro ao cadastrar cliente.';
    }
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Cadastro de clientes</title></head>
<body>
    <h1>Cadastro de clientes</h1>
    <?php if ($mensagem): ?><p><?= $mensagem ?></p><?php endif; ?>
    <form method="post">
        <label>Nome: <input type="text" name="nome"></label><br>
        <label>CPF: <input type="text" name="cpf"></label><br>
        <label>E-mail: <input type="text" name="email"></label><br>
        <label>Telefone: <input type="text" name="telefone"></label><br>
        <label>Endereço: <input type="text" name="endereco"></label><br>
        <button type="submit">Salvar</button>
    </form>
</body>
</html>
