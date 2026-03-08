def parse_user_input(text: str):
    result = {}

    lines = text.split("\n")

    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip().lower()] = value.strip()

    return result