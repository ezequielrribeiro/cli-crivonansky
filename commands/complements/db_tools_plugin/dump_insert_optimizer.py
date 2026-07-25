import os
from typing import Optional
from .sql_to_csv import SQLToCSV

class MySQLDumpOptimizer:
    def __init__(self, dump_file_path: str, output_dir: str='__same__'):
        self.dump_file_path = dump_file_path
        self.input_dump_size = os.path.getsize(dump_file_path)
        
        if output_dir == '__same__':
            output_dir = os.path.dirname(dump_file_path)

        self.output_dir = output_dir

        if not os.path.exists(self.output_dir): 
            os.makedirs(self.output_dir, exist_ok=True)

        output_dump_file_name = os.path.basename(dump_file_path).removesuffix('.sql')
        self.structure_file = os.path.join(self.output_dir, f"{output_dump_file_name}_optimized.sql")
        self.table_csv_files = {}  # table_name: csv_path

        # create, at output directory, a subdirectory with sql file name, filterin invalid characters
        output_dump_file_name = os.path.basename(dump_file_path)
        valid_dir_name = ''.join(c for c in output_dump_file_name if c.isalnum() or c in ('_')).rstrip() + '_optimized_csv'
        self.output_dir_csv = os.path.join(output_dir, valid_dir_name)
        if not os.path.exists(self.output_dir_csv): 
            os.makedirs(self.output_dir_csv, exist_ok=True)

    def process(self, progress_callback=None):
        sql_to_csv = SQLToCSV()
        sql_to_csv.set_output_dir(self.output_dir_csv)

        output_dump_file_name = os.path.basename(self.dump_file_path)
        inside_create_table = False

        print(f"Processing dump file: {output_dump_file_name}\n")

        with open(self.dump_file_path, 'r', encoding='latin-1') as infile, \
            open(self.structure_file, 'w', encoding='latin-1') as struct_out:

            current_table = ''
            table_field_names = []
            table_just_created = True

            struct_out.write('SET GLOBAL local_infile = 1;\n\n')

            while True:
                line = infile.readline()
                if not line:
                    break

                encoded_size = len(line.encode('latin-1')) + 1

                # ✅ callback de progresso
                if progress_callback:
                    progress_callback(encoded_size)

                line = line.strip()

                if line.startswith('CREATE TABLE'):
                    table_field_names = []
                    current_table = self._extract_table_name(line)
                    inside_create_table = True
                    struct_out.write(line + '\n')
                    table_just_created = True

                elif inside_create_table:
                    if line.startswith(')'):
                        inside_create_table = False
                    else:
                        current_field = self._extract_field_names(line)
                        if current_field:
                            table_field_names.append(current_field)

                    struct_out.write(line + '\n')

                elif line.startswith('INSERT INTO `'):
                    csv_file = sql_to_csv.write_sql_insert(line, table_field_names)

                    if table_just_created:
                        relative_csv_path = os.path.relpath(csv_file, self.output_dir).replace('\\', '/')

                        struct_out.write(f"\n-- Bulk insert for {current_table}\n")
                        struct_out.write(
                            f"LOAD DATA LOCAL INFILE '{relative_csv_path}' INTO TABLE "
                            f"`{current_table}` "
                            "FIELDS TERMINATED BY '~' "
                            "OPTIONALLY ENCLOSED BY '\"' "
                            "LINES TERMINATED BY '\\r\\n' "
                            "IGNORE 1 LINES;\n"
                        )

                        table_just_created = False

                else:
                    struct_out.write(line + '\n')


    def _extract_table_name(self, line: str, sql_prefix: str = 'CREATE TABLE', sql_suffix: str = '(') -> str:
        '''
        Extract table name from a SQL line.
        :param string line: SQL line
        :param string sql_prefix: SQL prefix to search for (optional)
        :param string sql_suffix: SQL suffix to search for (optional)
        :return: table name
        '''
        # Extract table name
        table_start = line.index(sql_prefix) + len(sql_prefix) + 1
        table_end = line.index(sql_suffix, table_start)
        table_name = line[table_start:table_end].strip().strip('`')
        return table_name
    
    def _extract_field_names(self, line: str) -> Optional[str]:
        '''
        Extract field name from a SQL line.
        :param string line: SQL line
        :return: field name or None
        '''
        line = line.strip().rstrip(',')
        if line.startswith('`'):
            field_end = line.index('`', 1)
            field_name = line[1:field_end]
            return field_name
        return None

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(
        prog="dump insert optimizer",
        description="Otimizador de dumps MySQL convertendo inserts em CSVs e usando LOAD DATA INFILE"
    )

    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_dir", default="__same__")

    args = parser.parse_args()

    optimizer = MySQLDumpOptimizer(
        args.input_file,
        args.output_dir
    )

    total = optimizer.input_dump_size

    state = {
        "processed": 0,
        "start_time": time.time()
    }

    def cli_progress(chunk_size: int):
        state["processed"] += chunk_size

        processed = state["processed"]
        percent = processed / total
        percent_display = int(percent * 100)

        bar_length = 40
        filled = int(bar_length * percent)
        bar = "█" * filled + "-" * (bar_length - filled)

        elapsed = time.time() - state["start_time"]
        speed = processed / elapsed if elapsed > 0 else 0
        speed_mb = speed / (1024 * 1024)

        print(
            f"\r[{bar}] {percent_display}% "
            f"({processed}/{total} bytes) "
            f"{speed_mb:.2f} MB/s",
            end="",
            flush=True
        )

    optimizer.process(progress_callback=cli_progress)

    print("\n[OK] Dump otimizado com sucesso")


# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(
#         prog="dump insert optimizer",
#         description="Otimizador de dumps MySQL convertendo inserts em CSVs e usando LOAD DATA INFILE"
#     )
#     parser.add_argument("--input_file", help="Dump SQL de entrada a ser otimizado", required=True)
#     parser.add_argument("--output_dir", help="Diretório de saída para o dump otimizado", required=False, default='__same__')

#     args = parser.parse_args()

#     optimizer = MySQLDumpOptimizer(args.input_file, args.output_dir)
#     optimizer.process()
