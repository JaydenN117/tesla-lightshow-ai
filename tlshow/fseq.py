"""Read and write FSEQ v2 files (the format the car plays).

The car only accepts V2 *uncompressed* with 48 or 200 channels and a step time of
15-100 ms. The reader also handles zstd-compressed files so community shows
saved with the wrong xLights setting can still be analysed.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Fseq:
    frames: np.ndarray            # (n_frames, n_channels) uint8
    step_ms: int = 20
    version: tuple[int, int] = (2, 0)
    compression: int = 0
    headers: dict[str, bytes] = field(default_factory=dict)

    @property
    def n_frames(self) -> int:
        return self.frames.shape[0]

    @property
    def n_channels(self) -> int:
        return self.frames.shape[1]

    @property
    def duration_s(self) -> float:
        return self.n_frames * self.step_ms / 1000

    def channel(self, ch: int) -> np.ndarray:
        """1-based channel column."""
        return self.frames[:, ch - 1]


def read(path: str | Path) -> Fseq:
    b = Path(path).read_bytes()
    if b[:4] != b"PSEQ":
        raise ValueError(f"{path}: not an FSEQ file")
    data_off, minor, major = struct.unpack("<HBB", b[4:8])
    if major != 2:
        raise ValueError(f"{path}: FSEQ v{major}.{minor} not supported (need v2)")
    var_off, = struct.unpack("<H", b[8:10])
    n_ch, n_fr, step = struct.unpack("<IIB", b[10:19])
    comp = b[20] & 0x0F
    n_blocks = b[21] | ((b[20] & 0xF0) << 4)
    n_sparse = b[22]
    blocks = [struct.unpack("<II", b[32 + 8 * i: 40 + 8 * i]) for i in range(n_blocks)]

    headers: dict[str, bytes] = {}
    i = var_off if var_off >= 32 else 32
    i = max(i, 32 + 8 * n_blocks + 6 * n_sparse)
    while i + 4 <= data_off:
        length, = struct.unpack("<H", b[i:i + 2])
        if length < 4:
            break
        headers[b[i + 2:i + 4].decode("latin-1")] = b[i + 4:i + length].rstrip(b"\0")
        i += length

    if comp == 0:
        raw = b[data_off:data_off + n_ch * n_fr]
    elif comp == 1:
        import zstandard

        dctx = zstandard.ZstdDecompressor()
        out, pos = [], data_off
        for _first, size in blocks:
            if size == 0:
                continue
            out.append(dctx.decompressobj().decompress(b[pos:pos + size]))
            pos += size
        raw = b"".join(out)
    else:
        raise ValueError(f"{path}: compression type {comp} (zlib) not supported")
    arr = np.frombuffer(raw[: n_ch * n_fr], dtype=np.uint8)
    if arr.size < n_ch * n_fr:
        arr = np.pad(arr, (0, n_ch * n_fr - arr.size))
    return Fseq(arr.reshape(n_fr, n_ch).copy(), step, (major, minor), comp, headers)


def _var_header(code: str, value: str) -> bytes:
    payload = value.encode("utf-8") + b"\0"
    return struct.pack("<H", 4 + len(payload)) + code.encode("ascii") + payload


def write(path: str | Path, seq: Fseq, media_file: str = "lightshow.wav") -> None:
    """Write V2.0 uncompressed, the exact layout xLights produces."""
    n_fr, n_ch = seq.frames.shape
    if n_ch not in (48, 200):
        raise ValueError("Tesla requires 48 or 200 channels")
    if not 15 <= seq.step_ms <= 100:
        raise ValueError("step time must be 15-100 ms")
    var = _var_header("mf", media_file) + _var_header("sp", "tlshow (teslaLightShow repo)")
    data_off = 32 + len(var)
    data_off += (-data_off) % 4
    header = bytearray(32)
    header[0:4] = b"PSEQ"
    struct.pack_into("<HBBH", header, 4, data_off, 0, 2, 32)
    struct.pack_into("<IIB", header, 10, n_ch, n_fr, seq.step_ms)
    # bytes 19-23: flags, compression (0), block count, sparse count, reserved = 0
    struct.pack_into("<Q", header, 24, int(time.time() * 1e6))
    body = bytes(header) + var
    body += b"\0" * (data_off - len(body))
    Path(path).write_bytes(body + np.ascontiguousarray(seq.frames, dtype=np.uint8).tobytes())
