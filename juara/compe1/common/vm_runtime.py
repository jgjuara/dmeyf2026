"""Activa modo VM (--vm): I/O con GCS vía common.gcs_upload."""

from __future__ import annotations

import os
import sys


def vm_mode() -> bool:
    return os.environ.get("COMPE1_VM", "").strip() == "1"


def activate_vm_from_argv() -> None:
    if "--vm" not in sys.argv:
        return
    sys.argv = [a for a in sys.argv if a != "--vm"]
    os.environ["COMPE1_VM"] = "1"


activate_vm_from_argv()
