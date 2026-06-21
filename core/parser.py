class CommandParser:
    @staticmethod
    def parse(input_line: str):
        parts = input_line.strip().split()

        if not parts:
            return None, []

        if parts[0].startswith("/"):
            return parts[0], parts[1:]

        # if len(parts) >= 1:
            # return f"{parts[0]} {parts[1]}", parts[2:]

        return parts[0], parts[1:]
