"""Compatibilidade para o módulo legacy ``validador_cnab``.

Este arquivo reexporta toda a API pública definida no pacote ``validators``
e mantém o ponto de entrada de linha de comando original.
"""

from validators import *  # noqa: F401,F403
from validators import __all__ as _VALIDATORS_ALL
from validators.cli import main

__all__ = list(_VALIDATORS_ALL) + ["main"]


if __name__ == "__main__":
    main()
