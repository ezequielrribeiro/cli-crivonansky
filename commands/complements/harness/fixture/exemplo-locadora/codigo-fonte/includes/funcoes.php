<?php
// Funções auxiliares do RotaCar.

function limpar(string $valor): string
{
    return trim(htmlspecialchars($valor, ENT_QUOTES, 'UTF-8'));
}

function calcular_total(float $diaria, string $dtIni, string $dtFim): float
{
    $inicio = new DateTime($dtIni);
    $fim = new DateTime($dtFim);
    $dias = (int) $inicio->diff($fim)->format('%a');
    return $diaria * max($dias, 1);
}
