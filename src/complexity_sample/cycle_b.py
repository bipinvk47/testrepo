"""Intentional lazy imports so static analysis can see a module cycle with `cycle_a`."""


def b_offset() -> int:
    return 0


def load_a() -> None:
    from . import cycle_a

    _ = cycle_a.a_val
