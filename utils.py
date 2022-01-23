def split_text(text: str, max_line_length: int = 32) -> list[str]:
    # Split in words removing multiple consecutive whitespaces
    words = filter(None, text.split())
    lines = ['']

    for word in words:
        # Truncate words longer than max_line_length to max_line_length
        word = word[0:max_line_length]
        last_line = lines[-1]

        if len(last_line) + 1 + len(word) <= max_line_length:
            lines[-1] = (last_line + ' ' + word) if last_line else word
        else:
            lines.append(word)

    return list(filter(None, lines))
