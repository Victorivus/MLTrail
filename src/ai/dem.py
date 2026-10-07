"""Ground elevation from a digital elevation model (DEM) for GPX tracks.

GPX ``<ele>`` values are often unreliable: barometric drift, GPS noise, or
sub-metre jitter added by route planners all inflate D+/D-, and the inflation
depends heavily on the smoothing threshold. Re-sampling the course on a
terrain model gives figures much closer to the official ones and far less
sensitive to smoothing. On three Pyrenean courses (25 m resampling, 3 m
threshold) the DEM landed within 2% of the official D+ where the GPX was
3-7% over, and 15-22% over without smoothing.

Source: the AWS Terrain Tiles open dataset ("skadi" format) — 1°x1° SRTM-style
``.hgt`` tiles at 1 arc-second (~30 m), merging EU-DEM, SRTM, NED and other
national models. No API key and no rate limit. Each tile is ~16 MB to download
and ~26 MB on disk; tiles are cached under ``cache_dir`` so a region is only
downloaded once.
"""
from __future__ import annotations

import dataclasses
import gzip
import logging
import math
import os
import shutil
import tempfile
import urllib.error
import urllib.request

import numpy as np

from ai.gpx import GpxTrack, resample_track

logger = logging.getLogger(__name__)

TILE_URL = ("https://s3.amazonaws.com/elevation-tiles-prod/skadi/"
            "{folder}/{name}.hgt.gz")
VOID = -32768            # SRTM no-data value
RESAMPLE_STEP_KM = 0.025  # DEM is sampled every 25 m along the course
MIN_COVERAGE = 0.95       # below this, the DEM profile is not trusted


def tile_name(lat: float, lon: float) -> str:
    """Name of the 1°x1° tile containing ``(lat, lon)``, e.g. ``N42E001``."""
    la, lo = math.floor(lat), math.floor(lon)
    return (f"{'N' if la >= 0 else 'S'}{abs(la):02d}"
            f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}")


def _tile_origin(name: str):
    """South-west corner ``(lat, lon)`` of a tile from its name."""
    lat = int(name[1:3]) * (1 if name[0] == "N" else -1)
    lon = int(name[4:7]) * (1 if name[3] == "E" else -1)
    return lat, lon


def _default_fetch(url: str):
    """Open ``url``; return a readable response, or ``None`` if it is absent."""
    try:
        return urllib.request.urlopen(url, timeout=60)
    except urllib.error.HTTPError as exc:
        # The bucket answers 403/404 for tiles that don't exist (open ocean).
        if exc.code in (403, 404):
            return None
        raise


class TileCache:
    """Loads DEM tiles from disk, downloading missing ones on first use.

    Args:
        cache_dir: directory holding the uncompressed ``.hgt`` tiles.
        fetch: ``url -> file-like | None`` (``None`` = tile does not exist).
            Injectable so tests never touch the network.
    """

    def __init__(self, cache_dir: str, fetch=_default_fetch):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self._tiles = {}

    def get(self, name: str):
        """The tile as a square int16 array, or ``None`` if none exists."""
        if name not in self._tiles:
            self._tiles[name] = self._load(name)
        return self._tiles[name]

    def _load(self, name: str):
        path = os.path.join(self.cache_dir, f"{name}.hgt")
        if not os.path.exists(path) and not self._download(name, path):
            return None
        grid = np.memmap(path, dtype=">i2", mode="r")
        n = int(round(math.sqrt(grid.size)))
        if n * n != grid.size:
            raise ValueError(f"DEM tile {path} is not square ({grid.size} cells)")
        return grid.reshape(n, n)

    def _download(self, name: str, path: str) -> bool:
        url = TILE_URL.format(folder=name[:3], name=name)
        logger.info("Downloading DEM tile %s", url)
        resp = self.fetch(url)
        if resp is None:
            logger.info("No DEM tile for %s", name)
            return False
        os.makedirs(self.cache_dir, exist_ok=True)
        # Decompress to a temp file and rename, so a crash or a concurrent
        # session never leaves a truncated tile behind.
        fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".part")
        try:
            with resp, os.fdopen(fd, "wb") as out, \
                    gzip.GzipFile(fileobj=resp) as gz:
                shutil.copyfileobj(gz, out)
            os.chmod(tmp, 0o644)  # mkstemp creates 0600
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
        return True


def sample_elevations(lats, lons, cache: TileCache) -> list:
    """Bilinearly interpolated DEM elevation (m) at each point.

    Points that fall on a void cell or outside any tile come back as ``None``.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    out = np.full(lats.shape, np.nan)
    names = np.array([tile_name(a, o) for a, o in zip(lats, lons)])

    for name in np.unique(names):
        grid = cache.get(name)
        if grid is None:
            continue
        idx = np.nonzero(names == name)[0]
        lat0, lon0 = _tile_origin(name)
        n = grid.shape[0]
        # Rows run north -> south, columns west -> east.
        row = (lat0 + 1 - lats[idx]) * (n - 1)
        col = (lons[idx] - lon0) * (n - 1)
        r0 = np.clip(np.floor(row).astype(int), 0, n - 2)
        c0 = np.clip(np.floor(col).astype(int), 0, n - 2)
        fr, fc = row - r0, col - c0
        corners = np.stack([grid[r0, c0], grid[r0, c0 + 1],
                            grid[r0 + 1, c0], grid[r0 + 1, c0 + 1]]).astype(float)
        corners[corners == VOID] = np.nan  # any void corner -> NaN result
        out[idx] = (corners[0] * (1 - fr) * (1 - fc) + corners[1] * (1 - fr) * fc
                    + corners[2] * fr * (1 - fc) + corners[3] * fr * fc)

    return [None if np.isnan(v) else float(v) for v in out]


def dem_track(track: GpxTrack, cache_dir: str,
              step_km: float = RESAMPLE_STEP_KM, fetch=_default_fetch):
    """Copy of ``track`` resampled every ``step_km`` with DEM elevations.

    Resampling densifies sparse route-planner tracks so the DEM sees the
    terrain between vertices; distances, total length and control points are
    unchanged.

    Returns:
        ``(track, coverage)`` where ``coverage`` is the fraction of points
        that got a DEM elevation. Callers should fall back to the GPX
        elevation below :data:`MIN_COVERAGE`.

    Raises:
        OSError / urllib.error.URLError: if a tile download fails.
    """
    dense = resample_track(track, step_km)
    eles = sample_elevations(dense.lats, dense.lons, TileCache(cache_dir, fetch))
    coverage = (sum(e is not None for e in eles) / len(eles)) if eles else 0.0
    return dataclasses.replace(dense, eles=eles), coverage
