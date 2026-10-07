'''
Tests for ai.dem: DEM tile naming, caching, sampling and track re-elevation.

All tests use small synthetic tiles served through an injected ``fetch`` —
nothing touches the network.
'''
import gzip
import io
import os
import tempfile
import unittest
import urllib.error

import numpy as np

from ai.dem import (TileCache, sample_elevations, dem_track, tile_name,
                    VOID, TILE_URL)
from ai.gpx import parse_gpx, build_profile

N = 5  # synthetic tiles are 5x5 (real ones are 3601x3601)


def _tile_bytes(grid):
    '''gzip-compressed big-endian int16 tile, as served by the bucket.'''
    return gzip.compress(np.asarray(grid, dtype=">i2").tobytes())


def _linear_grid():
    '''Elevation linear in row/col, so bilinear sampling is exact.'''
    rows, cols = np.mgrid[0:N, 0:N]
    return 1000 + 100 * rows + 10 * cols


class FakeFetch:
    '''Serves tiles by name and records every URL requested.'''

    def __init__(self, tiles):
        self.tiles = tiles
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        for name, grid in self.tiles.items():
            if url == TILE_URL.format(folder=name[:3], name=name):
                return io.BytesIO(_tile_bytes(grid))
        return None


class DemTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()


class TestTileName(unittest.TestCase):
    def test_hemispheres(self):
        self.assertEqual(tile_name(42.25, 1.86), "N42E001")
        self.assertEqual(tile_name(-33.9, 151.2), "S34E151")
        self.assertEqual(tile_name(-0.5, -0.5), "S01W001")
        self.assertEqual(tile_name(0.0, 0.0), "N00E000")
        self.assertEqual(tile_name(40.4, -3.7), "N40W004")


class TestSampleElevations(DemTestCase):
    def test_bilinear_is_exact_on_linear_terrain(self):
        cache = TileCache(self.cache_dir, FakeFetch({"N45E006": _linear_grid()}))
        # lat 45.5 -> row 2, lon 6.25 -> col 1 ; lat 45.875 -> row 0.5, lon 6.6 -> col 2.4
        eles = sample_elevations([45.5, 45.875, 46.0 - 1e-12, 45.0],
                                 [6.25, 6.6, 6.0, 7.0 - 1e-12], cache)
        self.assertAlmostEqual(eles[0], 1000 + 200 + 10)
        self.assertAlmostEqual(eles[1], 1000 + 50 + 24)
        # North-west and south-east corners of the tile (lat 46.0 itself
        # belongs to the next tile up, which shares this edge row).
        self.assertAlmostEqual(eles[2], 1000, places=6)
        self.assertAlmostEqual(eles[3], 1000 + 400 + 40, places=6)

    def test_missing_tile_gives_none(self):
        cache = TileCache(self.cache_dir, FakeFetch({}))
        self.assertEqual(sample_elevations([45.5], [6.5], cache), [None])

    def test_void_cells_give_none(self):
        grid = _linear_grid()
        grid[0, 0] = VOID
        cache = TileCache(self.cache_dir, FakeFetch({"N45E006": grid}))
        near_void, far = sample_elevations([45.9, 45.1], [6.1, 6.9], cache)
        self.assertIsNone(near_void)
        self.assertIsNotNone(far)

    def test_points_across_two_tiles(self):
        fetch = FakeFetch({"N45E006": _linear_grid(),
                           "N45E007": _linear_grid() + 5000})
        cache = TileCache(self.cache_dir, fetch)
        a, b = sample_elevations([45.5, 45.5], [6.25, 7.25], cache)
        self.assertAlmostEqual(b - a, 5000)


class TestTileCache(DemTestCase):
    def test_tile_is_downloaded_once_and_reused_from_disk(self):
        fetch = FakeFetch({"N45E006": _linear_grid()})
        TileCache(self.cache_dir, fetch).get("N45E006")
        self.assertEqual(len(fetch.urls), 1)
        self.assertTrue(os.path.exists(os.path.join(self.cache_dir, "N45E006.hgt")))

        # A fresh cache (new session) reads the file and never fetches.
        fetch2 = FakeFetch({})
        grid = TileCache(self.cache_dir, fetch2).get("N45E006")
        self.assertEqual(fetch2.urls, [])
        self.assertEqual(int(grid[2, 1]), 1210)

    def test_failed_download_raises_and_leaves_no_partial_file(self):
        def broken(url):
            raise urllib.error.URLError("offline")
        with self.assertRaises(urllib.error.URLError):
            TileCache(self.cache_dir, broken).get("N45E006")

        def truncated(url):
            return io.BytesIO(_tile_bytes(_linear_grid())[:20])
        with self.assertRaises(EOFError):
            TileCache(self.cache_dir, truncated).get("N45E006")
        self.assertEqual(os.listdir(self.cache_dir), [])


class TestDemTrack(DemTestCase):
    def _gpx(self):
        # ~2 km north-bound in tile N45E006, with a flat but jittery GPX <ele>
        # and one waypoint.
        pts = "".join(
            f'<trkpt lat="{45.1 + i * 0.0009}" lon="6.5">'
            f'<ele>{1000 + (2 if i % 2 else -2)}</ele></trkpt>'
            for i in range(21))
        return ('<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
                '<wpt lat="45.109" lon="6.5"><name>CP1</name></wpt>'
                f'<trk><trkseg>{pts}</trkseg></trk></gpx>')

    def test_track_is_resampled_and_re_elevated(self):
        track = parse_gpx(self._gpx())
        fetch = FakeFetch({"N45E006": _linear_grid()})
        dem, coverage = dem_track(track, self.cache_dir, step_km=0.05,
                                  fetch=fetch)

        self.assertEqual(coverage, 1.0)
        self.assertAlmostEqual(dem.total_distance_km, track.total_distance_km,
                               places=3)
        self.assertEqual(dem.control_points, track.control_points)
        self.assertAlmostEqual(dem.dist_cumul[1], 0.05)
        self.assertGreater(dem.n_points, track.n_points)

        # Going north means decreasing row -> steadily falling terrain, with
        # none of the GPX jitter.
        lat = np.asarray(dem.lats)
        expected = 1000 + 100 * (46 - lat) * (N - 1) + 10 * 0.5 * (N - 1)
        np.testing.assert_allclose(dem.eles, expected, atol=1e-6)
        prof = build_profile(dem, smoothing_m=0)
        self.assertEqual(prof.total_gain_m, 0)
        self.assertAlmostEqual(prof.total_loss_m,
                               -(expected[0] - expected[-1]), places=6)

    def test_coverage_reports_missing_terrain(self):
        track = parse_gpx(self._gpx())
        dem, coverage = dem_track(track, self.cache_dir, fetch=FakeFetch({}))
        self.assertEqual(coverage, 0.0)
        self.assertTrue(all(e is None for e in dem.eles))


if __name__ == "__main__":
    unittest.main()
