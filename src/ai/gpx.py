"""GPX track parsing and feature extraction for AI time inference.

This module is deliberately dependency-free (standard library only) so the
feature maths can be unit-tested without pandas/streamlit. The Streamlit page
(``front/pages/3_gpx_prediction.py``) turns the dicts produced here into a
DataFrame whose columns match exactly what the models were trained on.

The model consumes one row per *segment* of a course and predicts the time of
that segment; the whole-course time is the sum of the segment predictions. The
feature columns and their sign conventions mirror the ``features`` table that
feeds training (see ``src/database/load_features.py``):

    dist_total, elevation_pos_total, elevation_neg_total,
    dist_segment, dist_cumul,
    elevation_pos_segment, elevation_pos_cumul,
    elevation_neg_segment, elevation_neg_cumul

IMPORTANT: descent (``elevation_neg_*``) is stored as a NEGATIVE number, just
like the training data (e.g. a race with 13812 m of descent has
``elevation_neg_total = -13812``). GPX-derived features follow the same rule so
inference stays on-distribution.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# Feature columns in the exact order the models were trained on. The Streamlit
# page builds its DataFrame with ``[FEATURE_COLUMNS]`` so column order can never
# drift from the training schema.
FEATURE_COLUMNS = [
    "dist_total",
    "elevation_pos_total",
    "elevation_neg_total",
    "dist_segment",
    "dist_cumul",
    "elevation_pos_segment",
    "elevation_pos_cumul",
    "elevation_neg_segment",
    "elevation_neg_cumul",
]

EARTH_RADIUS_M = 6371008.8  # mean Earth radius (metres)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometres."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a)) / 1000.0


def _local(tag: str) -> str:
    """Strip the XML namespace from a tag, e.g. '{ns}trkpt' -> 'trkpt'."""
    return tag.rsplit("}", 1)[-1]


@dataclass
class GpxTrack:
    """A parsed GPX track plus any embedded control points (waypoints).

    Attributes:
        lats/lons/eles: per-point coordinates. ``eles`` entries are ``None``
            where the GPX lacked an ``<ele>`` tag.
        dist_cumul: cumulative distance (km) at each track point.
        control_points: ``(distance_km, name)`` tuples for GPX waypoints,
            snapped onto the track by nearest point and sorted by distance.
    """
    lats: list = field(default_factory=list)
    lons: list = field(default_factory=list)
    eles: list = field(default_factory=list)
    dist_cumul: list = field(default_factory=list)
    control_points: list = field(default_factory=list)

    @property
    def total_distance_km(self) -> float:
        return self.dist_cumul[-1] if self.dist_cumul else 0.0

    @property
    def has_elevation(self) -> bool:
        return any(e is not None for e in self.eles)

    @property
    def n_points(self) -> int:
        return len(self.lats)


def _read_points(root, tag: str):
    """Yield ``(lat, lon, ele_or_None)`` for every element with local ``tag``."""
    for el in root.iter():
        if _local(el.tag) != tag:
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        ele = None
        name = None
        for child in el:
            lc = _local(child.tag)
            if lc == "ele" and child.text:
                try:
                    ele = float(child.text)
                except ValueError:
                    ele = None
            elif lc == "name" and child.text:
                name = child.text.strip()
        yield float(lat), float(lon), ele, name


def parse_gpx(source) -> GpxTrack:
    """Parse a GPX document into a :class:`GpxTrack`.

    Args:
        source: file path, raw string/bytes, or a file-like object with a
            ``.read()`` method (e.g. a Streamlit ``UploadedFile``).

    Raises:
        ValueError: if the document is not valid XML or contains no track
            points (nor route points to fall back on).
    """
    if hasattr(source, "read"):
        data = source.read()
    else:
        data = source
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Could not parse GPX file: {exc}") from exc

    # Prefer track points; fall back to route points for route-only GPX files.
    pts = list(_read_points(root, "trkpt"))
    if not pts:
        pts = list(_read_points(root, "rtept"))
    if not pts:
        raise ValueError("No track points (<trkpt>) or route points (<rtept>) "
                         "found in the GPX file.")

    track = GpxTrack()
    prev = None
    cum = 0.0
    for lat, lon, ele, _name in pts:
        if prev is not None:
            cum += haversine_km(prev[0], prev[1], lat, lon)
        track.lats.append(lat)
        track.lons.append(lon)
        track.eles.append(ele)
        track.dist_cumul.append(round(cum, 4))
        prev = (lat, lon)

    # Waypoints become control points, snapped to the nearest track distance.
    waypoints = list(_read_points(root, "wpt"))
    control = []
    for lat, lon, _ele, name in waypoints:
        dist = _nearest_track_distance(track, lat, lon)
        if dist is not None:
            control.append((round(dist, 3), name or ""))
    control.sort(key=lambda c: c[0])
    track.control_points = control

    return track


def _nearest_track_distance(track: GpxTrack, lat: float, lon: float):
    """Cumulative distance (km) of the track point closest to ``(lat, lon)``."""
    if not track.lats:
        return None
    best_i, best_d = 0, float("inf")
    for i, (plat, plon) in enumerate(zip(track.lats, track.lons)):
        d = haversine_km(lat, lon, plat, plon)
        if d < best_d:
            best_d, best_i = d, i
    return track.dist_cumul[best_i]


def resample_track(track: GpxTrack, step_km: float) -> GpxTrack:
    """Points every ``step_km`` along the track, plus the exact finish.

    Positions are interpolated linearly along each original leg, so the total
    distance is preserved; elevation is interpolated too (or carried over from
    whichever neighbour has one). Control points are kept as-is.
    """
    if step_km <= 0:
        raise ValueError("step_km must be positive")
    out = GpxTrack(control_points=list(track.control_points))
    d = track.dist_cumul
    if not d:
        return out

    targets = [k * step_km for k in range(int(d[-1] / step_km) + 1)]
    if d[-1] - targets[-1] > 1e-9:
        targets.append(d[-1])

    i = 0
    for target in targets:
        while i + 1 < len(d) - 1 and d[i + 1] < target:
            i += 1
        j = min(i + 1, len(d) - 1)
        span = d[j] - d[i]
        f = 0.0 if span <= 0 else min(1.0, max(0.0, (target - d[i]) / span))
        e0, e1 = track.eles[i], track.eles[j]
        if e0 is not None and e1 is not None:
            ele = e0 + f * (e1 - e0)
        else:
            ele = e0 if e0 is not None else e1
        out.lats.append(track.lats[i] + f * (track.lats[j] - track.lats[i]))
        out.lons.append(track.lons[i] + f * (track.lons[j] - track.lons[i]))
        out.eles.append(ele)
        out.dist_cumul.append(round(target, 4))
    return out


@dataclass
class Profile:
    """Cumulative distance / elevation-gain / elevation-loss along the course.

    ``pos_cumul`` is monotonically non-decreasing (>= 0); ``neg_cumul`` is
    monotonically non-increasing (<= 0), matching the training-data sign
    convention for descent.
    """
    dist: list              # cumulative distance (km)
    pos_cumul: list         # cumulative ascent (m), >= 0
    neg_cumul: list         # cumulative descent (m), <= 0

    @property
    def total_distance_km(self) -> float:
        return self.dist[-1] if self.dist else 0.0

    @property
    def total_gain_m(self) -> float:
        return self.pos_cumul[-1] if self.pos_cumul else 0.0

    @property
    def total_loss_m(self) -> float:
        return self.neg_cumul[-1] if self.neg_cumul else 0.0


def build_profile(track: GpxTrack, smoothing_m: float = 3.0) -> Profile:
    """Compute cumulative ascent/descent along the track.

    Raw GPX elevation is noisy; counting every tiny wiggle wildly inflates D+.
    A hysteresis threshold (``smoothing_m``) ignores elevation changes smaller
    than that many metres before booking them as gain or loss — the standard
    way to get a realistic D+/D-. Points with missing elevation reuse the last
    known value so distances stay aligned.

    Returns a :class:`Profile`. With no elevation data at all, gain/loss are 0.
    """
    dist = list(track.dist_cumul)
    pos_cumul = [0.0]
    neg_cumul = [0.0]

    # Seed the reference with the first available elevation.
    ref = next((e for e in track.eles if e is not None), None)
    last = ref
    gain = 0.0
    loss = 0.0

    for i in range(1, len(dist)):
        ele = track.eles[i]
        if ele is None:
            ele = last
        if ele is None or ref is None:
            # Still no elevation information available at this point.
            pos_cumul.append(gain)
            neg_cumul.append(loss)
            if ele is not None:
                ref = last = ele
            continue
        diff = ele - ref
        if diff > smoothing_m:
            gain += diff
            ref = ele
        elif diff < -smoothing_m:
            loss += diff  # diff is negative -> descent stays negative
            ref = ele
        last = ele
        pos_cumul.append(gain)
        neg_cumul.append(loss)

    return Profile(dist=dist, pos_cumul=pos_cumul, neg_cumul=neg_cumul)


def _interp(xs: list, ys: list, x: float) -> float:
    """Linear interpolation of ``ys`` at ``x`` over sorted ``xs`` (clamped)."""
    if not xs:
        return 0.0
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    # xs is sorted (cumulative distance); linear scan is fine for GPX sizes.
    lo, hi = 0, len(xs) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    if x1 == x0:
        return ys[lo]
    frac = (x - x0) / (x1 - x0)
    return ys[lo] + frac * (ys[hi] - ys[lo])


def normalize_cuts(cuts, total_km: float, tol_km: float = 0.2) -> list:
    """Clean a set of interior split distances.

    Clamps to ``(0, total)``, sorts, and drops points within ``tol_km`` of each
    other (or of the start/finish). Returns the interior cut distances only.
    """
    cleaned = []
    for c in sorted(float(x) for x in cuts):
        if c <= tol_km or c >= total_km - tol_km:
            continue
        if cleaned and c - cleaned[-1] < tol_km:
            continue
        cleaned.append(round(c, 3))
    return cleaned


def even_cuts(total_km: float, step_km: float) -> list:
    """Interior split distances for an even split every ``step_km`` kilometres."""
    if step_km <= 0:
        return []
    cuts = []
    d = step_km
    while d < total_km - 1e-9:
        cuts.append(round(d, 3))
        d += step_km
    return normalize_cuts(cuts, total_km, tol_km=min(0.2, step_km / 4))


def boundaries_to_segments(profile: Profile, boundaries: list) -> list:
    """Build per-segment feature dicts from boundary distances.

    Args:
        profile: the course :class:`Profile`.
        boundaries: distances (km) defining segment edges. 0 and the total
            distance are added automatically; interior values may fall
            anywhere (they are interpolated onto the profile).

    Returns:
        A list of dicts, one per segment, each carrying every key in
        :data:`FEATURE_COLUMNS` plus ``dist_from``/``dist_to`` for display.
        Descent values are negative, matching the training schema.
    """
    total = profile.total_distance_km
    if total <= 0:
        return []

    edges = normalize_cuts(boundaries, total)
    edges = [0.0] + edges + [total]

    total_pos = int(round(profile.total_gain_m))
    total_neg = int(round(profile.total_loss_m))

    segments = []
    for a, b in zip(edges[:-1], edges[1:]):
        pos_a = _interp(profile.dist, profile.pos_cumul, a)
        pos_b = _interp(profile.dist, profile.pos_cumul, b)
        neg_a = _interp(profile.dist, profile.neg_cumul, a)
        neg_b = _interp(profile.dist, profile.neg_cumul, b)
        segments.append({
            "dist_from": round(a, 2),
            "dist_to": round(b, 2),
            "dist_total": round(total, 2),
            "elevation_pos_total": total_pos,
            "elevation_neg_total": total_neg,
            "dist_segment": round(b - a, 2),
            "dist_cumul": round(b, 2),
            "elevation_pos_segment": int(round(pos_b - pos_a)),
            "elevation_pos_cumul": int(round(pos_b)),
            "elevation_neg_segment": int(round(neg_b - neg_a)),
            "elevation_neg_cumul": int(round(neg_b)),
        })
    return segments


def segment_features(track: GpxTrack, boundaries: list,
                     smoothing_m: float = 3.0) -> list:
    """Convenience wrapper: parse-time track + cuts -> feature dicts."""
    profile = build_profile(track, smoothing_m=smoothing_m)
    return boundaries_to_segments(profile, boundaries)
