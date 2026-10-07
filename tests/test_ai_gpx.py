'''
Tests for ai.gpx: GPX parsing and feature extraction for time inference.
'''
import unittest

from ai.gpx import (parse_gpx, build_profile, boundaries_to_segments,
                    segment_features, even_cuts, normalize_cuts,
                    haversine_km, resample_track, FEATURE_COLUMNS)


def _gpx(trkpts, wpts=(), tag="trkpt"):
    '''Build a minimal GPX document string from (lat, lon, ele) tuples.'''
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">']
    for lat, lon, name in wpts:
        lines.append(f'<wpt lat="{lat}" lon="{lon}"><name>{name}</name></wpt>')
    if tag == "trkpt":
        lines.append('<trk><name>t</name><trkseg>')
        close = '</trkseg></trk>'
    else:
        lines.append('<rte>')
        close = '</rte>'
    for lat, lon, ele in trkpts:
        if ele is None:
            lines.append(f'<{tag} lat="{lat}" lon="{lon}"></{tag}>')
        else:
            lines.append(f'<{tag} lat="{lat}" lon="{lon}"><ele>{ele}</ele></{tag}>')
    lines.append(close)
    lines.append('</gpx>')
    return "\n".join(lines)


def _hill_track(n=21):
    '''~2 km north-bound track that climbs 500 m then drops 400 m, with
    sub-threshold GPS noise added on alternate points.'''
    pts = []
    for i in range(n):
        lat = 45.0 + i * 0.0009   # ~100 m per step
        ele = (1000 + i * 50) if i <= 10 else (1500 - (i - 10) * 40)
        ele += 1.5 if i % 2 == 0 else -1.5  # noise < 3 m threshold
        pts.append((lat, 6.0, ele))
    return pts


class TestHaversine(unittest.TestCase):
    def test_one_degree_latitude(self):
        # 1 degree of latitude is ~111.19 km on a sphere.
        d = haversine_km(45.0, 6.0, 46.0, 6.0)
        self.assertAlmostEqual(d, 111.19, delta=0.5)

    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_km(45.0, 6.0, 45.0, 6.0), 0.0, places=6)


class TestParseGpx(unittest.TestCase):
    def test_basic_track(self):
        track = parse_gpx(_gpx(_hill_track()))
        self.assertEqual(track.n_points, 21)
        self.assertTrue(track.has_elevation)
        self.assertAlmostEqual(track.total_distance_km, 2.0, delta=0.1)
        self.assertEqual(len(track.dist_cumul), 21)
        self.assertEqual(track.dist_cumul[0], 0.0)

    def test_bytes_input(self):
        track = parse_gpx(_gpx(_hill_track()).encode("utf-8"))
        self.assertEqual(track.n_points, 21)

    def test_waypoints_become_control_points(self):
        summit_lat = 45.0 + 10 * 0.0009
        doc = _gpx(_hill_track(), wpts=[(summit_lat, 6.0, "Summit")])
        track = parse_gpx(doc)
        self.assertEqual(len(track.control_points), 1)
        dist, name = track.control_points[0]
        self.assertEqual(name, "Summit")
        self.assertAlmostEqual(dist, 1.0, delta=0.15)

    def test_route_points_fallback(self):
        track = parse_gpx(_gpx(_hill_track(), tag="rtept"))
        self.assertEqual(track.n_points, 21)

    def test_missing_elevation(self):
        pts = [(45.0 + i * 0.0009, 6.0, None) for i in range(5)]
        track = parse_gpx(_gpx(pts))
        self.assertFalse(track.has_elevation)

    def test_invalid_xml_raises(self):
        with self.assertRaises(ValueError):
            parse_gpx("not xml at all <<<")

    def test_no_points_raises(self):
        empty = ('<?xml version="1.0"?><gpx version="1.1" '
                 'xmlns="http://www.topografix.com/GPX/1/1"></gpx>')
        with self.assertRaises(ValueError):
            parse_gpx(empty)


class TestProfile(unittest.TestCase):
    def test_smoothing_filters_noise(self):
        track = parse_gpx(_gpx(_hill_track()))
        prof = build_profile(track, smoothing_m=3.0)
        # Noise of +/-1.5 m is below the 3 m threshold, so gain/loss stay clean.
        self.assertAlmostEqual(prof.total_gain_m, 500.0, delta=5.0)
        self.assertAlmostEqual(prof.total_loss_m, -400.0, delta=5.0)

    def test_descent_is_negative(self):
        track = parse_gpx(_gpx(_hill_track()))
        prof = build_profile(track)
        self.assertLess(prof.total_loss_m, 0.0)
        self.assertTrue(all(v <= 0 for v in prof.neg_cumul))
        self.assertTrue(all(v >= 0 for v in prof.pos_cumul))

    def test_cumulative_monotonic(self):
        track = parse_gpx(_gpx(_hill_track()))
        prof = build_profile(track)
        self.assertEqual(prof.pos_cumul, sorted(prof.pos_cumul))
        self.assertEqual(prof.neg_cumul, sorted(prof.neg_cumul, reverse=True))

    def test_no_elevation_zero_profile(self):
        pts = [(45.0 + i * 0.0009, 6.0, None) for i in range(5)]
        prof = build_profile(parse_gpx(_gpx(pts)))
        self.assertEqual(prof.total_gain_m, 0.0)
        self.assertEqual(prof.total_loss_m, 0.0)


class TestSegments(unittest.TestCase):
    def setUp(self):
        self.track = parse_gpx(_gpx(_hill_track()))
        self.prof = build_profile(self.track, smoothing_m=3.0)

    def test_feature_schema_present(self):
        segs = boundaries_to_segments(self.prof, [1.0])
        self.assertEqual(len(segs), 2)
        for s in segs:
            for col in FEATURE_COLUMNS:
                self.assertIn(col, s)

    def test_sign_conventions(self):
        segs = boundaries_to_segments(self.prof, [1.0])
        for s in segs:
            self.assertLessEqual(s["elevation_neg_total"], 0)
            self.assertLessEqual(s["elevation_neg_segment"], 0)
            self.assertLessEqual(s["elevation_neg_cumul"], 0)
            self.assertGreaterEqual(s["elevation_pos_segment"], 0)

    def test_partials_sum_to_totals(self):
        segs = boundaries_to_segments(self.prof, [0.5, 1.0, 1.5])
        total = segs[0]["dist_total"]
        self.assertAlmostEqual(sum(s["dist_segment"] for s in segs), total,
                               delta=0.05)
        self.assertAlmostEqual(sum(s["elevation_pos_segment"] for s in segs),
                               segs[0]["elevation_pos_total"], delta=1)
        self.assertAlmostEqual(sum(s["elevation_neg_segment"] for s in segs),
                               segs[0]["elevation_neg_total"], delta=1)

    def test_last_cumul_equals_total(self):
        segs = boundaries_to_segments(self.prof, [0.7, 1.3])
        self.assertAlmostEqual(segs[-1]["dist_cumul"], segs[-1]["dist_total"],
                               delta=0.05)
        self.assertEqual(segs[-1]["elevation_pos_cumul"],
                         segs[-1]["elevation_pos_total"])

    def test_no_cuts_single_segment(self):
        segs = boundaries_to_segments(self.prof, [])
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["dist_segment"], segs[0]["dist_total"])

    def test_segment_features_wrapper(self):
        a = segment_features(self.track, [1.0], smoothing_m=3.0)
        b = boundaries_to_segments(build_profile(self.track, 3.0), [1.0])
        self.assertEqual(a, b)


class TestCuts(unittest.TestCase):
    def test_normalize_dedup_and_clamp(self):
        # 0.1 and 9.95 hug the ends; 5.0 and 5.05 collapse to one.
        self.assertEqual(normalize_cuts([0.1, 5.0, 5.05, 9.95], 10.0), [5.0])

    def test_normalize_sorts(self):
        self.assertEqual(normalize_cuts([7.0, 2.0, 4.0], 10.0), [2.0, 4.0, 7.0])

    def test_even_cuts_spacing(self):
        self.assertEqual(even_cuts(10.0, 3.0), [3.0, 6.0, 9.0])

    def test_even_cuts_non_positive_step(self):
        self.assertEqual(even_cuts(10.0, 0.0), [])



class TestResampleTrack(unittest.TestCase):
    def test_spacing_and_total_distance_preserved(self):
        track = parse_gpx(_gpx(_hill_track()))
        dense = resample_track(track, 0.025)
        self.assertAlmostEqual(dense.total_distance_km,
                               track.total_distance_km, places=4)
        steps = [b - a for a, b in zip(dense.dist_cumul, dense.dist_cumul[1:])]
        for s in steps[:-1]:
            self.assertAlmostEqual(s, 0.025, places=4)
        self.assertLessEqual(steps[-1], 0.025 + 1e-9)
        self.assertEqual(len(dense.lats), len(dense.eles))

    def test_positions_and_elevation_interpolated(self):
        # Two points ~1 km apart climbing 100 m: the midpoint is halfway.
        track = parse_gpx(_gpx([(45.0, 6.0, 1000.0), (45.009, 6.0, 1100.0)]))
        dense = resample_track(track, track.total_distance_km / 2)
        self.assertEqual(dense.n_points, 3)
        self.assertAlmostEqual(dense.lats[1], 45.0045, places=6)
        self.assertAlmostEqual(dense.eles[1], 1050.0, places=6)
        self.assertAlmostEqual(dense.eles[-1], 1100.0, places=6)

    def test_missing_elevation_carried_from_neighbour(self):
        track = parse_gpx(_gpx([(45.0, 6.0, None), (45.009, 6.0, 1100.0),
                                (45.018, 6.0, None)]))
        dense = resample_track(track, 0.1)
        self.assertTrue(all(e == 1100.0 for e in dense.eles))

    def test_keeps_control_points_and_profile_totals(self):
        climb = [(45.0 + i * 0.0009, 6.0, 1000.0 + i * 50) for i in range(11)]
        track = parse_gpx(_gpx(climb, wpts=[(45.0045, 6.0, "CP1")]))
        dense = resample_track(track, 0.01)
        self.assertEqual(dense.control_points, track.control_points)
        # Densifying straight legs must not invent (or lose) climb.
        a = build_profile(track, smoothing_m=0.0)
        b = build_profile(dense, smoothing_m=0.0)
        self.assertAlmostEqual(a.total_gain_m, 500.0, places=6)
        self.assertAlmostEqual(b.total_gain_m, 500.0, places=6)
        self.assertAlmostEqual(b.total_loss_m, 0.0, places=6)

    def test_rejects_non_positive_step(self):
        track = parse_gpx(_gpx(_hill_track()))
        with self.assertRaises(ValueError):
            resample_track(track, 0)


if __name__ == "__main__":
    unittest.main()
