# Encoding: UTF-8


def intword(num: int) -> str:
    """Display a number in a more human readable format.

    Args:
        num (int): The number to display.

    Returns:
        str: The human readable number.
    """
    postfix = ["", "K", "M", "B", "T", "Q"]
    fix = 0

    def _intword(num: int) -> str:
        nonlocal fix
        if num >= 1_000:
            fix += 1
            return _intword(num / 1_000)
        try:
            return f"{num:.2f}{postfix[fix]}"
        except IndexError:
            return "∞"

    return _intword(num)
