#!/usr/bin/env python3
"""Patch MetaHook gamedata so it matches the local engine DLL.

MetaHook picks the engine snapshot by the CRC64 of the loaded engine module:

    MH_LoadEngine_DetermineEngineType -> look up crc64 in gamedata/index.json
    -> load hl-<build>.json -> resolve every symbol by RVA

Retail catalogs only ship CRCs for the builds the maintainers own, so any
repack/patched hw.dll falls through with

    MH_LoadEngine: Unable to determine engine version
    Reason: the engine module CRC64 is not present in the gamedata catalog

This tool rewrites binaries.engine.windows.crc64 in the snapshot that really
belongs to the local engine and refreshes its sha256/size in index.json
(GameData verifies both).

The snapshot is chosen by matching the byte signatures (func_sig / gv_sig)
stored in every record against the local engine binary. An RVA-bounds check is
done first, but it is not enough on its own: a "blob host" engine (small .text,
60 MB .data, code loaded at runtime) accepts every snapshot by bounds and still
matches none of them.

Usage:
    python patch_gamedata_crc.py "D:\\Counter-Strike Build 4554"
    python patch_gamedata_crc.py "D:\\game" --gamedata hl-4554.json
    python patch_gamedata_crc.py "D:\\game" --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

POLY = 0xC96C5795D7870F42

# A snapshot must reproduce at least this share of its own signatures on the
# local binary. Correct builds score 100%; unrelated builds score < 10%.
MIN_SIGNATURE_MATCH = 0.8


def _crc64_table() -> list[int]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ (POLY if crc & 1 else 0)
        table.append(crc)
    return table


_TABLE = _crc64_table()


def crc64(data: bytes) -> int:
    crc = 0xFFFFFFFFFFFFFFFF
    for b in data:
        crc = _TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFFFFFFFFFF


def pe_image_info(path: Path) -> tuple[int, int]:
    """Return (ImageBase, SizeOfImage) from a PE32 file."""
    data = path.read_bytes()[:0x400]
    if data[:2] != b"MZ":
        raise ValueError(f"{path} is not a PE file")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise ValueError(f"{path} has no PE signature")
    opt = e_lfanew + 24  # after COFF header
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic != 0x10B:
        raise ValueError(f"{path} is not PE32 (magic 0x{magic:x})")
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    return image_base, size_of_image


def max_symbol_rva(doc: dict) -> int:
    top = 0
    for rec in doc.get("records", []):
        payload = rec.get("payload", {})
        raw = payload.get("func_rva") or payload.get("gv_rva") or "0"
        top = max(top, int(raw, 16))
    return top


def find_engine_dll(game_dir: Path) -> Path:
    for name in ("hw.dll", "sw.dll"):
        candidate = game_dir / name
        if candidate.is_file():
            return candidate
    raise SystemExit(f"[error] no hw.dll/sw.dll in {game_dir}")


def _sig_regex(sig: str) -> re.Pattern[bytes] | None:
    parts = sig.split()
    if not parts:
        return None
    out = bytearray()
    for part in parts:
        if part in ("??", "?"):
            out += b"."
        else:
            try:
                out += re.escape(bytes([int(part, 16)]))
            except ValueError:
                return None
    return re.compile(bytes(out), re.DOTALL)


def signature_score(doc: dict, image: bytes) -> tuple[int, int]:
    """How many of the snapshot's byte signatures occur in the image."""
    found = total = 0
    for rec in doc.get("records", []):
        payload = rec.get("payload", {})
        sig = payload.get("func_sig") or payload.get("gv_sig")
        if not sig:
            continue
        regex = _sig_regex(sig)
        if regex is None:
            continue
        total += 1
        if regex.search(image):
            found += 1
    return found, total


def pick_snapshot(
    gamedata_dir: Path,
    image: bytes,
    size_of_image: int,
    forced: str | None,
) -> tuple[Path, dict]:
    if forced:
        path = gamedata_dir / forced
        if not path.is_file():
            raise SystemExit(f"[error] {path} not found")
        doc = json.loads(path.read_text(encoding="utf-8"))
        found, total = signature_score(doc, image)
        if total and found / total < MIN_SIGNATURE_MATCH:
            raise SystemExit(
                f"[error] {forced} matches only {found}/{total} of its own "
                "signatures against this engine;\n"
                "        it belongs to a different build, patching it would "
                "only move the failure to 'symbol rva is out of bounds'."
            )
        return path, doc

    candidates: list[tuple[float, int, int, Path, dict]] = []
    skipped = 0
    for path in sorted(gamedata_dir.glob("hl-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if max_symbol_rva(doc) >= size_of_image:
            skipped += 1
            continue
        found, total = signature_score(doc, image)
        if not total:
            continue
        candidates.append((found / total, found, total, path, doc))

    if not candidates:
        raise SystemExit(
            "[error] no usable hl-*.json snapshot in "
            f"{gamedata_dir} (skipped {skipped} by image bounds)"
        )

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    ratio, found, total, path, doc = candidates[0]

    if ratio < MIN_SIGNATURE_MATCH:
        detail = ", ".join(
            f"{p.name} {f}/{t}" for r, f, t, p, _ in candidates[:4]
        )
        raise SystemExit(
            "[error] this engine build is not covered by the gamedata catalog.\n"
            f"        best signature match: {detail}\n"
            "        A MetaHook snapshot is keyed by the engine's CRC64 and its\n"
            "        RVAs must point at the real code. If the local hw.dll is a\n"
            "        'blob host' (tiny .text, huge .data, engine code loaded at\n"
            "        runtime by a launcher), no catalog snapshot can describe it:\n"
            "        MetaHook would resolve garbage and crash. Use a build that\n"
            "        MetaHook supports (e.g. 4554/8684) for MetaHook plugins."
        )

    return path, doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_dir", type=Path)
    parser.add_argument("--gamedata", help="snapshot file name, e.g. hl-4554.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    game_dir = args.game_dir
    gamedata_dir = game_dir / "cstrike" / "metahook" / "gamedata"
    if not gamedata_dir.is_dir():
        raise SystemExit(f"[error] {gamedata_dir} not found (MetaHookSv not installed?)")

    engine = find_engine_dll(game_dir)
    image = engine.read_bytes()
    image_base, size_of_image = pe_image_info(engine)
    engine_crc = crc64(image)

    snapshot_path, doc = pick_snapshot(
        gamedata_dir, image, size_of_image, args.gamedata
    )
    old_crc = doc.get("binaries", {}).get("engine", {}).get("windows", {}).get("crc64", "")
    found, total = signature_score(doc, image)

    print(f"engine      : {engine}")
    print(f"image base  : 0x{image_base:08x}")
    print(f"image size  : 0x{size_of_image:08x}")
    print(f"crc64       : {engine_crc:016x}")
    print(f"snapshot    : {snapshot_path.name} (old crc64 {old_crc})")
    print(f"signatures  : {found}/{total} found")
    print(f"max symbol  : 0x{max_symbol_rva(doc):08x}")

    if old_crc == f"{engine_crc:016x}":
        print("already up to date")
        return 0

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    backup = snapshot_path.with_suffix(snapshot_path.suffix + ".bak")
    if not backup.exists():
        backup.write_bytes(snapshot_path.read_bytes())

    doc["binaries"]["engine"]["windows"]["crc64"] = f"{engine_crc:016x}"
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    snapshot_path.write_text(text, encoding="utf-8")

    index_path = gamedata_dir / "index.json"
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        raw = snapshot_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        for entry in index.get("versions", []):
            if entry.get("url") == snapshot_path.name or entry.get("gameVersion") == snapshot_path.stem:
                entry["sha256"] = digest
                entry["size"] = len(raw)
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"index.json  : sha256/size updated for {snapshot_path.name}")

    print(f"patched     : {snapshot_path} (backup: {backup.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
