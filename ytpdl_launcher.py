"""Frozen-app entry point (PyInstaller).

`ytpdl/__main__.py` uses a relative import that only resolves under
`python -m ytpdl`; this module uses an absolute import so it also works as a
plain script inside a bundle.
"""

from ytpdl.app import main

if __name__ == "__main__":
    raise SystemExit(main())
