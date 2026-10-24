"""Music analysis: beats, downbeats, onsets by band, energy and sections.

Always analyse the exact file that goes on the USB stick (the 44.1 kHz WAV made
by `prepare_audio`). MP3s carry encoder delay (the uploaded test track starts
25 ms late), so timings measured on a different decode can be off by a frame.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

SR = 22050
HOP = 256  # ~11.6 ms resolution


def prepare_audio(src: str | Path, dst_wav: str | Path) -> Path:
    """Decode anything ffmpeg reads to 44.1 kHz 16-bit stereo WAV (what the car wants)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required")
    dst = Path(dst_wav)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-map", "0:a:0",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", "-map_metadata", "-1", str(dst)],
        check=True,
    )
    return dst


@dataclass
class Section:
    start: float
    end: float
    label: str          # A, B, C ... (same letter = similar music)
    energy: float       # 0..1, mean loudness relative to the song
    level: str          # low | mid | high


@dataclass
class Analysis:
    duration: float
    tempo: float
    beats: list[float]
    downbeats: list[float]
    beat_strength: list[float]          # 0..1 per beat
    kicks: list[float]                  # low-band accents (< 150 Hz), on the 16th grid
    snares: list[float]                 # 1.5-5 kHz accents
    hats: list[float]                   # > 6 kHz accents
    onsets: list[float]                 # broadband accents
    onset_strength: list[float]         # 0..1 per accent
    sections: list[Section]
    energy_hop: float
    energy: list[float] = field(repr=False)  # 0..1 loudness curve, one value per energy_hop s

    def energy_at(self, t: float) -> float:
        i = int(t / self.energy_hop)
        return self.energy[min(max(i, 0), len(self.energy) - 1)]

    def section_at(self, t: float) -> Section:
        for s in self.sections:
            if s.start <= t < s.end:
                return s
        return self.sections[-1]

    def beats_between(self, t0: float, t1: float) -> list[float]:
        return [b for b in self.beats if t0 <= b < t1]

    def save(self, path: str | Path) -> None:
        d = asdict(self)
        Path(path).write_text(json.dumps(d, separators=(",", ":")))

    @classmethod
    def load(cls, path: str | Path) -> "Analysis":
        d = json.loads(Path(path).read_text())
        d["sections"] = [Section(**s) for s in d["sections"]]
        return cls(**d)


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    hi = np.percentile(x, 98) if x.size else 1.0
    return np.clip(x / (hi or 1.0), 0, 1)


def _grid(beats: np.ndarray, div: int = 4) -> np.ndarray:
    """Beat grid subdivided into `div` steps (16th notes for div=4)."""
    if len(beats) < 2:
        return np.asarray(beats, dtype=float)
    pts = [np.linspace(b0, b1, div, endpoint=False) for b0, b1 in zip(beats[:-1], beats[1:])]
    return np.concatenate(pts + [beats[-1:]])


def _grid_hits(S: np.ndarray, freqs: np.ndarray, lo: float, hi: float, grid: np.ndarray,
               sr: int, ratio: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Accents in one band, measured on the beat grid.

    Dense rock/pop mixes defeat plain onset detection, so measure log-energy flux
    at each grid point and keep points that stand well above the local median.
    Returns (times, strength 0..1).
    """
    import librosa
    from scipy.ndimage import median_filter

    sub = S[(freqs >= lo) & (freqs < hi)].sum(axis=0)
    flux = np.maximum(0, np.diff(np.log1p(sub * 1e3), prepend=0))
    fr = librosa.time_to_frames(grid, sr=sr, hop_length=HOP)
    v = np.array([flux[max(0, x - 2):x + 3].max() if x < len(flux) else 0 for x in fr])
    med = median_filter(v, size=33, mode="nearest") + 1e-9
    hit = (v > ratio * med) & (v > np.percentile(v, 50))
    strength = _norm(v / med)
    return grid[hit], strength[hit]


def analyze(path: str | Path, n_sections: int | None = None, bpm: float | None = None) -> Analysis:
    """bpm: tempo hint when the tracker locks to the wrong multiple (check with your ears)."""
    import librosa

    y, sr = librosa.load(str(path), sr=SR, mono=True)
    duration = len(y) / sr

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    hint = {"start_bpm": bpm, "tightness": 400} if bpm else {}
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr,
                                                 hop_length=HOP, trim=False, **hint)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    grid = _grid(beats)
    kicks, _ = _grid_hits(S, freqs, 20, 150, grid, sr)
    snares, _ = _grid_hits(S, freqs, 1500, 5000, grid, sr)
    hats, _ = _grid_hits(S, freqs, 6000, sr / 2, grid, sr)
    accents, accent_str = _grid_hits(S, freqs, 20, sr / 2, grid, sr, ratio=1.8)


    # loudness curve at 50 ms
    e_hop = 0.05
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=int(sr * e_hop))[0]
    energy = _norm(librosa.amplitude_to_db(rms, ref=np.max) + 60)

    # beat strength & downbeat phase (bars of 4)
    bstr = _norm(onset_env[np.minimum(beat_frames, len(onset_env) - 1)]) if len(beat_frames) else np.array([])
    low_env = librosa.onset.onset_strength(S=librosa.power_to_db(S[freqs < 150]), sr=sr, hop_length=HOP)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    downbeats = beats[::4]
    if len(beat_frames) >= 8:
        bf = np.minimum(beat_frames, chroma.shape[1] - 1)
        cs = librosa.util.sync(chroma, bf, aggregate=np.median)
        novelty = np.r_[0, np.linalg.norm(np.diff(cs, axis=1), axis=0)][: len(bf)]
        kick_at = low_env[np.minimum(bf, len(low_env) - 1)]
        score = _norm(kick_at) + _norm(novelty)
        phase = int(np.argmax([score[p::4].mean() for p in range(4)]))
        downbeats = beats[phase::4]

    sections = _sections(y, sr, beats, downbeats, energy, e_hop, duration, n_sections)

    return Analysis(
        duration=round(duration, 3), tempo=round(tempo, 2),
        beats=_r(beats), downbeats=_r(downbeats), beat_strength=_r(bstr),
        kicks=_r(kicks), snares=_r(snares), hats=_r(hats),
        onsets=_r(accents), onset_strength=_r(accent_str),
        sections=sections, energy_hop=e_hop, energy=_r(energy),
    )


def _r(a) -> list[float]:
    return [round(float(x), 3) for x in a]


def _sections(y, sr, beats, downbeats, energy, e_hop, duration, k) -> list[Section]:
    import librosa

    if len(beats) < 16:
        return [Section(0.0, duration, "A", 1.0, "high")]
    k = k or max(3, min(14, round(duration / 18)))
    bf = librosa.time_to_frames(beats, sr=sr, hop_length=HOP)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    rms = librosa.feature.rms(y=y, hop_length=HOP)
    feat = np.vstack([librosa.util.normalize(mfcc, axis=1), chroma, 3 * _norm(rms)])
    bf = np.minimum(bf, feat.shape[1] - 1)
    sync = librosa.util.sync(feat, bf, aggregate=np.mean)
    bounds = librosa.segment.agglomerative(sync, k)
    times = sorted({0.0, *[float(beats[min(b, len(beats) - 1)]) for b in bounds[1:]]})
    # snap to nearest downbeat, drop slivers < 4 s
    db = np.asarray(downbeats)
    snapped = [0.0]
    for t in times[1:]:
        s = float(db[np.argmin(np.abs(db - t))]) if len(db) else t
        if s - snapped[-1] >= 4.0 and duration - s >= 4.0:
            snapped.append(s)
    edges = snapped + [duration]

    e = np.asarray(energy)
    feats, energies = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        i0, i1 = int(a / e_hop), max(int(b / e_hop), int(a / e_hop) + 1)
        energies.append(float(e[i0:i1].mean()))
        j0 = int(np.searchsorted(beats, a)); j1 = max(int(np.searchsorted(beats, b)), j0 + 1)
        feats.append(sync[:, j0:j1].mean(axis=1))
    # label similar sections with the same letter
    labels: list[str] = []
    protos: list[np.ndarray] = []
    for f in feats:
        sims = [float(np.dot(f, p) / (np.linalg.norm(f) * np.linalg.norm(p) + 1e-9)) for p in protos]
        if sims and max(sims) > 0.97:
            labels.append(chr(65 + int(np.argmax(sims))))
        else:
            protos.append(f)
            labels.append(chr(65 + len(protos) - 1))
    en = np.asarray(energies)
    lo, hi = np.percentile(en, 33), np.percentile(en, 66)
    rel = en / (en.max() or 1)
    return [
        Section(round(a, 3), round(b, 3), lab, round(float(r), 3),
                "high" if x >= hi else "low" if x < lo else "mid")
        for a, b, lab, x, r in zip(edges[:-1], edges[1:], labels, en, rel)
    ]
