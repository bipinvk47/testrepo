"""Intentional lazy imports so static analysis can see a module cycle with `cycle_b`."""


def a_val() -> int:
    return 1


def load_b() -> None:
    from . import cycle_b

    _ = cycle_b.b_offset
