
# app/utils/dxf_blocks.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import ezdxf
from ezdxf.addons import Importer


Drawing = ezdxf.document.Drawing  # type alias for clarity


def _as_path(path_like: str | Path) -> Path:
    p = Path(path_like)
    return p.expanduser().resolve() if not p.is_absolute() else p


def import_dxf_as_block(
    target_doc: Drawing,
    dxf_path: str | Path,
    block_name: Optional[str] = None,
) -> Optional[str]:
    """
    Import block definitions from an external DXF into `target_doc`.
    Returns the block name that now exists in target_doc (or None on failure).

    Notes:
      - If `block_name` is provided, we will import all blocks from the source file,
        then return `block_name` if it exists; otherwise try the source file's first block.
      - If the source DXF has no block definitions, we return None (we do not synthesize a block).
    """
    try:
        src_path = _as_path(dxf_path)
        if not src_path.exists():
            return None

        # Early exit if caller wants a specific name and it already exists.
        if block_name and block_name in target_doc.blocks:
            return block_name

        src_doc: Drawing = ezdxf.readfile(str(src_path))

        # Import all BLOCK definitions into the target.
        imp = Importer(src_doc, target_doc)
        names = list(src_doc.blocks.names())
        if names:
            imp.import_blocks(names)
            imp.finalize()
        else:
            # No block definitions present in source DXF
            return None

        # Decide which name to return/prioritize
        if block_name and block_name in target_doc.blocks:
            return block_name

        # Fallbacks: first imported name; or stem of filename if that block exists
        if names:
            if names[0] in target_doc.blocks:
                return names[0]

        stem = src_path.stem
        if stem in target_doc.blocks:
            return stem

        # Could not determine a usable block name
        return None

    except Exception:
        # We keep this non-fatal for the calling code.
        return None


def insert_block(
    msp,
    block_name: str,
    insert: Tuple[float, float] | Tuple[float, float, float] = (0.0, 0.0),
    layer: str = "0",
    rotation: float = 0.0,
    xscale: float = 1.0,
    yscale: float = 1.0,
) -> bool:
    """
    Insert an existing block reference into the modelspace.

    Returns True on success, False if the block does not exist or insertion fails.
    """
    try:
        doc: Drawing = msp.doc  # type: ignore[attr-defined]
        if block_name not in doc.blocks:
            return False

        # Allow 2D (x, y) or 3D (x, y, z) tuples
        if len(insert) == 2:
            insert = (insert[0], insert[1], 0.0)

        msp.add_blockref(
            name=block_name,
            insert=insert,  # (x, y, z)
            dxfattribs={"layer": layer, "rotation": rotation, "xscale": xscale, "yscale": yscale},
        )
        return True
    except Exception:
        return False


def ensure_block_from_file(
    target_doc: Drawing,
    dxf_path: str | Path,
    preferred_name: Optional[str] = None,
) -> Optional[str]:
    """
    Convenience: ensure a block from `dxf_path` exists in `target_doc` and return its name.
    If `preferred_name` already exists in the doc, it is returned as-is.
    Otherwise we try to import and return whichever name is available.
    """
    if preferred_name and preferred_name in target_doc.blocks:
        return preferred_name
    return import_dxf_as_block(target_doc, dxf_path, block_name=preferred_name)