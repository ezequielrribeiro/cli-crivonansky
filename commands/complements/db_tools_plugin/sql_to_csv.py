
import csv
import os

class SQLToCSV:
    
    def __init__(self):
        pass

    def set_output_dir(self, output_dir):
        self.output_dir = output_dir

    def write_sql_insert(self, sql_insert, table_field_names=None):
        '''
        Write SQL INSERT statement to CSV file.

        :param string sql_insert: SQL INSERT statement
        :param array table_field_names: list of field names for the table (optional)
        '''
        table_name, field_names, row_data = self.__parse_sql_insert(sql_insert, table_field_names)
        csv_path = self.__write_csv_rows(table_name, row_data, field_names, self.output_dir)
        return csv_path

    def __last_index(self, str, value):
        """
        Returns the index of the last occurrence of `value` in `str`.
        If not found, returns -1.
        """
        try:
            # Reverse search: find from the end
            return len(str) - 1 - str[::-1].index(value)
        except ValueError:
            return -1  # Value not found

    def __parse_sql_insert(self, sql_insert, table_field_names=None):
        '''
        Parse an SQL INSERT statement and return table name, field names, and row data.
        
        :param string sql_insert: SQL INSERT statement
        :param array table_field_names: list of field names for the table (optional)
        :return: tuple (table_name, field_names, row_data)
        '''
        # Replace unicode characters
        unicode_chars = {
            "\u2013": "-"
        }

        for old, new in unicode_chars.items():
            sql_insert = sql_insert.replace(old, new)

        # Extract table name
        table_start = sql_insert.index('INTO') + 5
        str_end = '(' if table_field_names is None else 'VALUES'
        table_end = sql_insert.index(str_end, table_start)
        table_name = sql_insert[table_start:table_end].strip().strip('`')

        if table_field_names is None:
            field_names = sql_insert.split("(")[1].split(")")[0]
            field_names = [field.replace("`", "").strip() for field in field_names.split(',')]
        else: 
            field_names = table_field_names

        # Extract row data
        tuples_str = sql_insert.split('VALUES (')[1].strip()
        row_values = []
        # parse char by char to handle multiple tuples
        rows = []
        tuple_start_index = 0
        tuple_end_index = 0
        inside_quote = False
        quote_char = ''
        last_char = ''
        for index, char in enumerate(tuples_str):

            if (char == "'" or char == '"') and inside_quote == False:
                inside_quote = True
                quote_char = char
                continue

            if inside_quote:
                if char == '\\':
                    last_char = char
                # Handle escaped characters
                elif last_char == '\\':
                    last_char = ''
                elif char == quote_char and last_char != '\\':
                    inside_quote = False
                    quote_char = ''
                continue

            if char == '(':
                tuple_start_index = index + 1

            if char == ')':
                tuple_end_index = index
                values_str = tuples_str[tuple_start_index:tuple_end_index]
                row_values = self.__parse_row_values(values_str)
                # Create a dictionary mapping field names to row values
                row_data = dict(zip(field_names, row_values))
                rows.append(row_data)

        return table_name, field_names, rows
    
    def __parse_row_values(self, values_str):
        '''
        Parse row values from a string.

        :param string values_str: string containing row values
        :return: list of row values
        '''
        row_values = []
        current_value = ''
        inside_quote = False
        quote_char = ''
        last_char = ''
        values_str = values_str.strip()
        for char in values_str:
            if (char == "'" or char == '"') and not inside_quote:
                inside_quote = True
                quote_char = char
                current_value += char
                continue

            if inside_quote:
                current_value += char
                if char == '\\':
                    last_char = char
                # Handle escaped characters
                elif last_char == '\\':
                    last_char = ''
                elif char == quote_char and last_char != '\\':
                    inside_quote = False
                    quote_char = ''
                continue

            if char == ',' and not inside_quote:
                row_values.append(self.__handle_values(current_value.strip()))
                current_value = ''
            else:
                current_value += char

        # Append the last value
        if len(current_value.strip()) > 0:
            row_values.append(self.__handle_values(current_value.strip()))

        return row_values
    
    def __handle_values(self, value):
        '''
        Handle NULL values in SQL.

        :param string value: value to check
        :return: processed value
        '''
        if value.upper() == "'NULL'":
            return 'NULL'
        elif value.upper() == 'NULL':
            return '\\N'

        return value.strip("'")

    def __write_csv_rows(self, table_name, rows, field_names, output_dir):
        '''
        Write rows to a CSV file.

        :param string table_name: table name
        :param array rows: array with row data
        :param array field_names: array with field names
        :param string output_dir: output directory path
        '''
        csv_path = os.path.join(output_dir, f'{table_name}.csv')
        # if the output directory does not exist, create it
        os.makedirs(output_dir, exist_ok=True)
        # if the csv file already exists, append to it; otherwise, create a new one
        csv_mode = 'a' if os.path.exists(csv_path) else 'w'

        with open(csv_path, csv_mode, newline='', encoding='latin-1') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names, quotechar='"', 
                                    quoting=csv.QUOTE_MINIMAL, delimiter='~')
            if csv_mode == 'w':
                writer.writeheader()

            writer.writerows(rows)
        return csv_path
    
if __name__ == "__main__":
    sql_insert = "INSERT INTO `funcionarios` (`id`, `id_cliente`, `RG`, `nome`, `nome_social`, `id_setor`, `NIT`, `CTPS`, `sexo`, `BRPDH`, `regime_revezamento`, `requisitos_da_funcao`, `descricao_das_atividades`, `tipo_sanguineo`, `observacoes_adicionais`, `endereco`, `e_mail`, `telefone`, `celular`, `bairro`, `cidade`, `estado`, `pais`, `CEP`, `CPF`, `demitido`, `nome_mae`, `orgao_expeditor_RG`, `UF_RG`, `data_emissao_RG`, `UF_CTPS`, `data_emissao_CTPS`, `filiacao_previdencia`, `estado_civil`, `remuneracao_mensal`, `area`, `aposentado`, `jornada`, `afastado`, `complemento`, `numero`, `recomendacoes`, `procecimentos_acidentes`, `resp_empregado`, `observacoes`, `data_cadastro`, `login_cadastro`, `controla_vencimentos`, `matricula`, `data_demissao`, `referencia`, `id_cargo`, `ultima_atualizacao_fat_risco`, `categoria`, `id_evento_drive`, `codigo_rh`, `chapa`, `possui_vinculo`, `CNS`, `foto`, `senha`, `id_ultimo_historico_funcionario`, `ultimo_historico_operacao`, `ultimo_historico_data`, `candidato`, `cadastro_portal_cliente`, `empresa_ativa`, `data_admissao`, `data_nascimento`, `ultima_data_base`, `envia_esocial`, `dataHoraCadastro`, `dataHoraEdicao`, `hash_verificacao`, `CNH`, `CNH_categoria`, `CNH_validade`, `possui_CNH`, `tipo_regime`, `dias_afastado_nos_ultimos_60`, `encaminhar_inss`, `dias_afastado_total`, `dias_desde_ultima_primaria`, `regiao`, `id_grupo`, `grau_de_risco`, `pcd`, `publica_afastamento`, `id_escritorio_contabil`, `raca_etnica`, `acesso_sgg_agendamento`, `acesso_sgg_docs`, `acesso_sgg_exames`, `acesso_sgg_treinamentos`, `acesso_sgg_afastamentos`, `acesso_sgg_riscos`, `acesso_sgg_questionario`, `notificacao_liberacao_acesso`, `notificacao_criacao_acesso`, `login_bloqueado`, `acesso_sgg_login`, `acesso_sgg_senha`, `qtde_acessos_mes`, `qtde_acessos_total`, `data_ultimo_acesso`, `data_hora`, `troca_senha_chave`, `cobrado_taxa_adesao`, `id_cliente_cedido`, `acesso_sgg_reconhecimento_facial`, `id_centro_de_custos`, `atualizaDataHoraEdicao`, `escolaridade`, `ultima_modificacao_senha`) VALUES (52895, 2014, 'RG_52895', 'Funcionario_52895', '', 5747, '205.87018.41-3', 'CTPS_52895', 'F', 'NA', ' X  Horas', '', 'Cuidar da segurança do aluno nas dependências e proximidades da escola e durante o transporte escolar. Inspecionar o comportamento dos alunos no ambiente escolar e durante o transporte escolar. Orientar alunos  sobre regras e procedimentos, regimento escolar, cumprimento de horários; ouvem reclamações e analisam fatos. Prestar apoio às atividades acadêmicas; controlar as atividades livres dos alunos, orientando entrada e saída de alunos, fiscalizando espaços de recreação, definindo limites nas atividades livres. Organizar ambiente escolar e providenciam manutenção predial, além de outras atividades designadas pelo empregador.', 'Desconhecido', '', NULL, NULL, '', '55991952447', NULL, NULL, NULL, NULL, NULL, '807.624.613-06', '1', NULL, '', '', '0000-00-00', '', '0000-00-00', 'Desconhecido', 'Desconhecido', '', 'Desconhecida', 'Não', '', 'N', NULL, NULL, 'Quando aplicável, fazer a correta utilização dos Equipamentos de Proteção Individual indicados nos programas ambientais bem como seguir as recomendações do empregador indicadas em treinamentos/capacitações.', 'Em caso de acidente, comunicar imediatamente sua chefia imediata, para que esse tome as providencias necessárias para o pronto atendimento do funcionário.', '1 – Cumprir as disposições legais e regulamentares sobre Segurança e Medicina do Trabalho, inclusive as Ordens de Serviço expedidas pelo empregador (NR 1 item 1.4.2 e Art. 157 e Art. 158 Capítulo V da CLT);\r\n2 – Usar os EPI nos locais em que houver indicação sinalizada de acordo com as instruções fornecidas pela empresa, através das normas de higiene e segurança do trabalho (ordem de serviço);\r\n3 – Para sua proteção, o uso de EPI é Obrigatório, exigido conforme descrito no PGR da empresa;\r\n4 – Os funcionários devem responsabilizar-se pela guarda e conservação dos EPI;\r\n5 – Somente fazer refeições no refeitório, ficando proibida a realização desta em outro ambiente; \r\n6 – Não executar qualquer trabalho para o qual não tenha sido orientado e autorizado pelo responsável;\r\n7 – Manter postura ergonômica correta a ajudar colegas e terceirizados, quando precisar e levantar peso; \r\n8 – Participar dos treinamentos de conscientização e instrução de segurança do trabalho; \r\n9 – Não correr dentro da empresa;\r\n10 – Criar o hábito/costume de fazer uma Avaliação/Inspeção no local de trabalho antes de iniciar as atividades;\r\n11 – Verificar os materiais e Equipamentos (as condições) a ser utilizado. Verificar o EPI, se realmente é o ideal a ser utilizado para a proteção;\r\n12 – Acompanhar sempre o Procedimento de trabalho conforme a orientação da Chefia, Inspecionar e Avaliar a área de trabalho antes de iniciar as tarefas, pessoas ao redor, produtos, objeto que possa atrapalhar e/ou causar acidente de trabalho;\r\n13 – Não deixar jogado materiais pelo chão da empresa utilizando sempre a lixeira ou entulho;\r\n14 – Em hipótese alguma deve ser feito qualquer procedimento de limpeza com a máquina ligada, mantendo o máximo de cuidado em qualquer operação que promova risco a saúde do trabalhador e possível causador de um acidente de trabalho;\r\n15 – Sempre que retirar uma proteção das partes móveis das máquinas e equipamentos, antes deve ser desligar a máquina e bloquear o sistema que religa a mesma. E jamais retornar ao trabalho e ligar a máquina sem antes recolocar a proteção de segurança das polias, correias e demais partes móveis existentes. Se isto não se proceder à máquina não deve ser ligada.\r\n', 'Penalidades e Advertência\r\n\r\nA recusa, injustificada quanto à utilização de qualquer Equipamento de Proteção Individual, Equipamento de Proteção Coletiva ou descumprimento de algum item constante nesta ordem de Serviço, sujeitará as penalidades, administrativas adotadas pela empresa, a saber:\r\n\r\n- Advertência verbal, no primeiro ato;\r\n- Advertência escrita no caso de reincidência;\r\n- Suspensão disciplinar de um dia;\r\n- Suspensão disciplinar de três dias;\r\n- Dispensa por justa causa.\r\n', '2026-02-18', 'conplan_sgg_cametra_JESSICA', '1', '968', '2026-02-27', NULL, 13583, NULL, NULL, NULL, NULL, NULL, 'S', '', NULL, NULL, 57759, 'admissao', '2026-02-23', 'N', 'N', 'S', '2026-02-23', '1999-03-07', '2026-02-23', 'S', '2026-02-18 16:23:54', '2026-02-27 09:14:45', '', NULL, NULL, NULL, 'nao', 'geral', 0, 'N', 0, 0, 0, NULL, 2, 'Não', 'S', NULL, 'Não informado', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', '0', NULL, NULL, 0, 0, NULL, NULL, NULL, 'N', NULL, 'N', NULL, 1, 'Nenhum', NULL),(52895, 2014, 'RG_52895', 'Funcionario_52895', '', 5747, '205.87018.41-3', 'CTPS_52895', 'F', 'NA', ' X  Horas', '', 'Cuidar da segurança do aluno nas dependências e proximidades da escola e durante o transporte escolar. Inspecionar o comportamento dos alunos no ambiente escolar e durante o transporte escolar. Orientar alunos  sobre regras e procedimentos, regimento escolar, cumprimento de horários; ouvem reclamações e analisam fatos. Prestar apoio às atividades acadêmicas; controlar as atividades livres dos alunos, orientando entrada e saída de alunos, fiscalizando espaços de recreação, definindo limites nas atividades livres. Organizar ambiente escolar e providenciam manutenção predial, além de outras atividades designadas pelo empregador.', 'Desconhecido', '', NULL, NULL, '', '55991952447', NULL, NULL, NULL, NULL, NULL, '807.624.613-06', '1', NULL, '', '', '0000-00-00', '', '0000-00-00', 'Desconhecido', 'Desconhecido', '', 'Desconhecida', 'Não', '', 'N', NULL, NULL, 'Quando aplicável, fazer a correta utilização dos Equipamentos de Proteção Individual indicados nos programas ambientais bem como seguir as recomendações do empregador indicadas em treinamentos/capacitações.', 'Em caso de acidente, comunicar imediatamente sua chefia imediata, para que esse tome as providencias necessárias para o pronto atendimento do funcionário.', '1 – Cumprir as disposições legais e regulamentares sobre Segurança e Medicina do Trabalho, inclusive as Ordens de Serviço expedidas pelo empregador (NR 1 item 1.4.2 e Art. 157 e Art. 158 Capítulo V da CLT);\r\n2 – Usar os EPI nos locais em que houver indicação sinalizada de acordo com as instruções fornecidas pela empresa, através das normas de higiene e segurança do trabalho (ordem de serviço);\r\n3 – Para sua proteção, o uso de EPI é Obrigatório, exigido conforme descrito no PGR da empresa;\r\n4 – Os funcionários devem responsabilizar-se pela guarda e conservação dos EPI;\r\n5 – Somente fazer refeições no refeitório, ficando proibida a realização desta em outro ambiente; \r\n6 – Não executar qualquer trabalho para o qual não tenha sido orientado e autorizado pelo responsável;\r\n7 – Manter postura ergonômica correta a ajudar colegas e terceirizados, quando precisar e levantar peso; \r\n8 – Participar dos treinamentos de conscientização e instrução de segurança do trabalho; \r\n9 – Não correr dentro da empresa;\r\n10 – Criar o hábito/costume de fazer uma Avaliação/Inspeção no local de trabalho antes de iniciar as atividades;\r\n11 – Verificar os materiais e Equipamentos (as condições) a ser utilizado. Verificar o EPI, se realmente é o ideal a ser utilizado para a proteção;\r\n12 – Acompanhar sempre o Procedimento de trabalho conforme a orientação da Chefia, Inspecionar e Avaliar a área de trabalho antes de iniciar as tarefas, pessoas ao redor, produtos, objeto que possa atrapalhar e/ou causar acidente de trabalho;\r\n13 – Não deixar jogado materiais pelo chão da empresa utilizando sempre a lixeira ou entulho;\r\n14 – Em hipótese alguma deve ser feito qualquer procedimento de limpeza com a máquina ligada, mantendo o máximo de cuidado em qualquer operação que promova risco a saúde do trabalhador e possível causador de um acidente de trabalho;\r\n15 – Sempre que retirar uma proteção das partes móveis das máquinas e equipamentos, antes deve ser desligar a máquina e bloquear o sistema que religa a mesma. E jamais retornar ao trabalho e ligar a máquina sem antes recolocar a proteção de segurança das polias, correias e demais partes móveis existentes. Se isto não se proceder à máquina não deve ser ligada.\r\n', 'Penalidades e Advertência\r\n\r\nA recusa, injustificada quanto à utilização de qualquer Equipamento de Proteção Individual, Equipamento de Proteção Coletiva ou descumprimento de algum item constante nesta ordem de Serviço, sujeitará as penalidades, administrativas adotadas pela empresa, a saber:\r\n\r\n- Advertência verbal, no primeiro ato;\r\n- Advertência escrita no caso de reincidência;\r\n- Suspensão disciplinar de um dia;\r\n- Suspensão disciplinar de três dias;\r\n- Dispensa por justa causa.\r\n', '2026-02-18', 'conplan_sgg_cametra_JESSICA', '1', '968', '2026-02-27', NULL, 13583, NULL, NULL, NULL, NULL, NULL, 'S', '', NULL, NULL, 57759, 'admissao', '2026-02-23', 'N', 'N', 'S', '2026-02-23', '1999-03-07', '2026-02-23', 'S', '2026-02-18 16:23:54', '2026-02-27 09:14:45', '', NULL, NULL, NULL, 'nao', 'geral', 0, 'N', 0, 0, 0, NULL, 2, 'Não', 'S', NULL, 'Não informado', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', '0', NULL, NULL, 0, 0, NULL, NULL, NULL, 'N', NULL, 'N', NULL, 1, 'Nenhum', NULL);"
    converter = SQLToCSV()
    converter.set_output_dir('output_csv')
    csv_file_path = converter.write_sql_insert(sql_insert)