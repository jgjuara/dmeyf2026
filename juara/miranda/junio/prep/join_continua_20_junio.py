"""Une capas para CONTINUA en junio 2021 con muestra del 20% por foto_mes."""

import os

os.environ.setdefault("MIRANDA_COHORT", "continua_sample")
os.environ.setdefault("MIRANDA_SAMPLE_FRAC", "0.2")

from join_junio import main

if __name__ == "__main__":
    main()
