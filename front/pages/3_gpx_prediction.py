"""GPX Time Prediction page.

Upload a GPX course, carve it into segments, and predict split + total times
with the AI model the logged-in runner trained on their own results (see the
*My Results* page — that is where a runner finds themselves and trains a model).

This page only adds GPX parsing and course segmentation; the inference itself
reuses the exact same path as the Race Results page (load ``model.pkl`` and
call ``XGBoostRegressorModel.predict``), so the model process is untouched.

Segments can be defined in several ways, which all edit the same list of
interior split distances:
  * the course's own GPX control points (waypoints), when present;
  * clicking on the elevation profile to drop a split where you want;
  * an even split every N km;
  * typing a distance to add a single split.
"""
import logging
import os

import joblib
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from config import get_config
from auth import require_auth
from ai.features import Features
from ai.xgboost import XGBoostRegressorModel
from ai.gpx import (parse_gpx, build_profile, boundaries_to_segments,
                    even_cuts, normalize_cuts, FEATURE_COLUMNS)
from ai.dem import dem_track, MIN_COVERAGE

logger = logging.getLogger(__name__)

cfg = get_config()
DB_PATH = cfg.db_path
# DEM tiles live under the data volume so they survive container rebuilds.
DEM_CACHE_DIR = os.path.join(cfg.data_dir_path, "dem")

ELE_DEM = "Terrain model (DEM)"
ELE_GPX = "GPX file"

# Segments at/above this length fall outside the training distribution (the
# models learn from partial splits < 30 km), so predictions degrade. We warn
# rather than block.
LONG_SEGMENT_KM = 30.0

# Must be the first Streamlit call on the page (before require_auth renders any
# widgets), so it lives at module top rather than inside main().
st.set_page_config(layout="wide", page_title="GPX Time Prediction",
                   page_icon="🗺️")

if not require_auth(DB_PATH):
    st.stop()


def _init_state():
    st.session_state.setdefault("gpx_sig", None)
    st.session_state.setdefault("gpx_track", None)
    st.session_state.setdefault("gpx_cuts", [])
    st.session_state.setdefault("gpx_last_pick", None)
    st.session_state.setdefault("gpx_smoothing", 3.0)
    st.session_state.setdefault("gpx_prediction", None)
    st.session_state.setdefault("gpx_ele_source", ELE_DEM)
    st.session_state.setdefault("gpx_dem", None)        # (track, coverage)
    st.session_state.setdefault("gpx_dem_error", None)


def _load_track(uploaded):
    '''
    Parse an uploaded GPX once per distinct file. On a new file the
    segmentation (cuts, last click, previous prediction) is reset so state
    from a previous course does not leak in.
    '''
    sig = (uploaded.name, uploaded.size)
    if st.session_state.gpx_sig == sig and st.session_state.gpx_track is not None:
        return st.session_state.gpx_track

    track = parse_gpx(uploaded.getvalue())
    st.session_state.gpx_sig = sig
    st.session_state.gpx_track = track
    # Default segmentation: use the GPX's own control points if it has any,
    # otherwise an even split every 5 km (a sensible on-distribution default).
    if track.control_points:
        st.session_state.gpx_cuts = normalize_cuts(
            [c[0] for c in track.control_points], track.total_distance_km)
    else:
        st.session_state.gpx_cuts = even_cuts(track.total_distance_km, 5.0)
    st.session_state.gpx_last_pick = None
    st.session_state.gpx_prediction = None
    st.session_state.gpx_dem = None
    st.session_state.gpx_dem_error = None
    return track


def _load_dem_track(track):
    '''
    The course resampled with DEM elevations, computed once per upload.
    Returns ``None`` (and remembers why) if the DEM can't be used, so the
    page falls back to the GPX elevation.
    '''
    if st.session_state.gpx_dem is None and st.session_state.gpx_dem_error is None:
        with st.spinner("Fetching terrain elevation (first use of a region "
                        "downloads ~16 MB per 1° tile, cached afterwards)..."):
            try:
                st.session_state.gpx_dem = dem_track(track, DEM_CACHE_DIR)
            except Exception as exc:  # network / disk errors -> GPX fallback
                logger.exception("DEM elevation lookup failed")
                st.session_state.gpx_dem_error = f"could not fetch terrain data ({exc})"
        dem = st.session_state.gpx_dem
        if dem is not None and dem[1] < MIN_COVERAGE:
            st.session_state.gpx_dem_error = (
                f"the terrain model only covers {dem[1]:.0%} of this course")
    if st.session_state.gpx_dem_error:
        return None
    return st.session_state.gpx_dem[0]


# --- segmentation callbacks (mutate the shared gpx_cuts list) --------------

def _cb_even():
    tr = st.session_state.gpx_track
    st.session_state.gpx_cuts = even_cuts(tr.total_distance_km,
                                          st.session_state.gpx_even_km)
    st.session_state.gpx_prediction = None


def _cb_use_cp():
    tr = st.session_state.gpx_track
    st.session_state.gpx_cuts = normalize_cuts(
        [c[0] for c in tr.control_points], tr.total_distance_km)
    st.session_state.gpx_prediction = None


def _cb_add_manual():
    tr = st.session_state.gpx_track
    st.session_state.gpx_cuts = normalize_cuts(
        st.session_state.gpx_cuts + [st.session_state.gpx_manual_km],
        tr.total_distance_km)
    st.session_state.gpx_prediction = None


def _cb_clear():
    st.session_state.gpx_cuts = []
    st.session_state.gpx_prediction = None


def _cb_undo():
    if st.session_state.gpx_cuts:
        st.session_state.gpx_cuts = st.session_state.gpx_cuts[:-1]
        st.session_state.gpx_prediction = None


def _picked_distance(event):
    '''
    Pull the clicked distance out of an Altair selection event, defensively —
    the payload shape varies across Streamlit versions and may be missing.
    '''
    try:
        sel = event["selection"]
    except (TypeError, KeyError):
        sel = getattr(event, "selection", None)
    if not sel:
        return None
    items = sel.get("cut") if isinstance(sel, dict) else None
    if not items:
        return None
    item = items[-1]
    if isinstance(item, dict):
        val = item.get("dist")
    else:
        val = item
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _elevation_series(track):
    '''Elevation per track point, forward-filling any missing ``<ele>``.'''
    last = next((e for e in track.eles if e is not None), 0.0)
    out = []
    for e in track.eles:
        if e is not None:
            last = e
        out.append(last)
    return out


def _profile_chart(track, prof):
    '''
    Elevation-vs-distance profile drawn as contiguous bars, with a click
    selection that reports the clicked distance. Downsampled for snappiness.

    It must stay a single-view chart: Streamlit rejects ``on_select`` on
    layered charts, and Vega-Lite can't do ``nearest`` clicks on area marks.
    So segments alternate in shade and the bar holding each split is red,
    instead of overlaying rule layers.
    '''
    elev = _elevation_series(track)
    df = pd.DataFrame({"dist": prof.dist, "elev": elev})
    if len(df) > 600:
        df = df.iloc[:: max(1, len(df) // 600)].reset_index(drop=True)
    df["dist_end"] = df["dist"].shift(-1).fillna(df["dist"].iloc[-1])
    df["base"] = df["elev"].min()

    cuts = np.sort(np.asarray(st.session_state.gpx_cuts, dtype=float))
    seg = np.searchsorted(cuts, df["dist"].to_numpy(), side="right")
    df["shade"] = np.where(seg % 2 == 0, "even", "odd")
    if cuts.size:
        split_rows = np.searchsorted(df["dist"].to_numpy(), cuts, side="right") - 1
        df.loc[np.clip(split_rows, 0, len(df) - 1), "shade"] = "split"

    cut = alt.selection_point(name="cut", on="click", fields=["dist"],
                              clear=False)
    return alt.Chart(df).mark_bar(binSpacing=0).encode(
        x=alt.X("dist:Q", title="Distance (km)"),
        x2="dist_end:Q",
        y=alt.Y("elev:Q", title="Elevation (m)", scale=alt.Scale(zero=False)),
        y2="base:Q",
        color=alt.Color("shade:N", legend=None, scale=alt.Scale(
            domain=["even", "odd", "split"],
            range=["#7FA6CC", "#4C78A8", "#D62728"])),
        tooltip=[alt.Tooltip("dist:Q", title="km", format=".2f"),
                 alt.Tooltip("elev:Q", title="Elevation (m)", format=".0f")],
    ).add_params(cut).properties(height=280)


def _run_prediction(prof):
    '''
    Build the feature frame from the current segments and run the trained
    model, mirroring the Race Results inference path exactly.
    '''
    rows = boundaries_to_segments(prof, st.session_state.gpx_cuts)
    if not rows:
        st.error("No segments to predict. Define at least the full course.")
        return
    df = pd.DataFrame(rows)
    features = df[FEATURE_COLUMNS].copy()

    rgs = XGBoostRegressorModel(df=features.copy(), target_column=None,
                                only_partials=False)
    rgs.model = joblib.load(cfg.model_path)
    preds = rgs.predict(features, format="time")  # HH:MM:SS per segment

    seconds = [Features.get_seconds(p) for p in preds]
    cumulative = np.cumsum(seconds)
    out = pd.DataFrame({
        "From (km)": df["dist_from"],
        "To (km)": df["dist_to"],
        "Dist (km)": df["dist_segment"].round(2),
        "D+ (m)": df["elevation_pos_segment"],
        "D- (m)": df["elevation_neg_segment"],
        "Segment time": preds.values,
        "Cumulative time": [Features.format_time(int(s)) for s in cumulative],
    })
    st.session_state.gpx_prediction = {
        "table": out,
        "total": Features.format_time(int(sum(seconds))),
        "cuts": tuple(st.session_state.gpx_cuts),
        "cum_dist": df["dist_cumul"].tolist(),
        "cum_sec": [int(s) for s in cumulative],
    }


def _render_prediction():
    pred = st.session_state.gpx_prediction
    if pred is None:
        return
    if pred["cuts"] != tuple(st.session_state.gpx_cuts):
        st.info("Segments changed since the last prediction — click "
                "**Run AI prediction** again to refresh.")
        return

    st.subheader("Predicted times")
    st.metric("Total predicted time", pred["total"])
    st.dataframe(pred["table"], hide_index=True, use_container_width=True)
    st.caption(
        "The total is the sum of the per-segment predictions. These are "
        "estimates extrapolated from the runner's training races: they are "
        "most reliable on courses with similar distance and elevation to "
        "those the model was trained on, and ignore race-day conditions, "
        "terrain familiarity, and fitness changes."
    )

    chart_df = pd.DataFrame({
        "Distance (km)": pred["cum_dist"],
        "Cumulative hours": [s / 3600.0 for s in pred["cum_sec"]],
    })
    line = alt.Chart(chart_df).mark_line(point=True, color="#2CA02C").encode(
        x=alt.X("Distance (km):Q"),
        y=alt.Y("Cumulative hours:Q", title="Cumulative time (h)"),
        tooltip=["Distance (km)", "Cumulative hours"],
    ).properties(height=260)
    st.altair_chart(line, use_container_width=True)


def main():
    '''Streamlit entry point for the GPX prediction page.'''
    st.title("🗺️ GPX Time Prediction")
    st.markdown(
        "Upload a course as a **GPX** file and predict your split and finish "
        "times with the AI model you trained on the *My Results* page."
    )

    _init_state()

    # Gate on a model trained this session, exactly like the Race Results page.
    if st.session_state.get("model_params") is None:
        st.warning(
            "No AI model loaded. Head to **My Results**, find your results and "
            "train a model first — then come back to predict GPX courses."
        )
        return

    uploaded = st.file_uploader("Upload a GPX track", type=["gpx"])
    if uploaded is None:
        st.info("Upload a `.gpx` file to get started.")
        return

    try:
        track = _load_track(uploaded)
    except ValueError as exc:
        st.error(f"Could not read this GPX file: {exc}")
        return

    total = track.total_distance_km

    st.radio(
        "Elevation source", [ELE_DEM, ELE_GPX], horizontal=True,
        key="gpx_ele_source",
        help="GPX elevation is often inflated by GPS/barometer noise or "
             "planner jitter. The terrain model re-reads the ground elevation "
             "along the course from a ~30 m DEM (EU-DEM/SRTM), which tracks "
             "official D+ figures much more closely. Tiles are cached locally.",
    )
    dem = (_load_dem_track(track)
           if st.session_state.gpx_ele_source == ELE_DEM else None)
    if st.session_state.gpx_ele_source == ELE_DEM and dem is None:
        st.warning(f"Using the GPX elevation instead: "
                   f"{st.session_state.gpx_dem_error}.")
    active = dem if dem is not None else track

    smoothing = st.session_state.gpx_smoothing
    prof = build_profile(active, smoothing_m=smoothing)

    c1, c2, c3 = st.columns(3)
    c1.metric("Distance", f"{total:.1f} km")
    gain_delta = loss_delta = None
    if dem is not None and track.has_elevation:
        # Show what the raw GPX would have claimed, for transparency.
        gpx_prof = build_profile(track, smoothing_m=smoothing)
        gain_delta = f"GPX file says {int(round(gpx_prof.total_gain_m)):,} m"
        loss_delta = f"GPX file says {abs(int(round(gpx_prof.total_loss_m))):,} m"
    c2.metric("Elevation gain (D+)", f"{int(round(prof.total_gain_m)):,} m",
              delta=gain_delta, delta_color="off")
    c3.metric("Elevation loss (D-)", f"{abs(int(round(prof.total_loss_m))):,} m",
              delta=loss_delta, delta_color="off")

    if dem is None and not track.has_elevation:
        st.warning(
            "This GPX has no elevation data, so D+/D- are 0. Climb is a major "
            "driver of trail time — predictions will be unreliable. Use a GPX "
            "that includes elevation for meaningful results."
        )

    st.divider()
    st.subheader("Define segments")
    st.caption(
        "The model predicts one split per segment and sums them for the total. "
        "**Click the profile** to drop a split where you want; or use the "
        "controls below. Segments alternate in shade; red marks each split."
    )

    st.session_state.gpx_smoothing = st.slider(
        "Elevation smoothing (m)", min_value=0.0, max_value=10.0,
        value=float(st.session_state.gpx_smoothing), step=0.5,
        help="Ignores elevation wiggles smaller than this to avoid inflating "
             "D+/D- from GPS noise. Rebuilds the profile.",
    )
    prof = build_profile(active, smoothing_m=st.session_state.gpx_smoothing)

    event = st.altair_chart(_profile_chart(active, prof),
                            use_container_width=True, on_select="rerun",
                            key="gpx_profile_chart")

    picked = _picked_distance(event)
    if picked is not None and picked != st.session_state.gpx_last_pick:
        st.session_state.gpx_last_pick = picked
        st.session_state.gpx_cuts = normalize_cuts(
            st.session_state.gpx_cuts + [picked], total)
        st.session_state.gpx_prediction = None
        st.rerun()

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.4, 1.4, 1, 1])
    with ctrl1:
        even_max = max(2.0, float(total))
        st.number_input("Even split every (km)", min_value=1.0,
                        max_value=even_max, value=min(5.0, even_max), step=1.0,
                        key="gpx_even_km")
        st.button("Apply even split", on_click=_cb_even, use_container_width=True)
    with ctrl2:
        st.number_input("Add split at (km)", min_value=0.0,
                        max_value=float(total), value=min(5.0, float(total)),
                        step=0.5, key="gpx_manual_km")
        st.button("Add split", on_click=_cb_add_manual, use_container_width=True)
    with ctrl3:
        st.button("Use GPX control points", on_click=_cb_use_cp,
                  disabled=not track.control_points, use_container_width=True,
                  help=None if track.control_points
                       else "This GPX has no waypoints to use as control points.")
        st.button("Undo last split", on_click=_cb_undo,
                  disabled=not st.session_state.gpx_cuts, use_container_width=True)
    with ctrl4:
        st.button("Clear splits", on_click=_cb_clear,
                  disabled=not st.session_state.gpx_cuts, use_container_width=True)

    segments = boundaries_to_segments(prof, st.session_state.gpx_cuts)
    st.caption(f"**{len(segments)} segment(s)** · splits at: "
               + (", ".join(f"{c:.1f}" for c in st.session_state.gpx_cuts)
                  if st.session_state.gpx_cuts else "none (whole course)"))

    long_segs = [s for s in segments if s["dist_segment"] >= LONG_SEGMENT_KM]
    if long_segs:
        st.warning(
            f"{len(long_segs)} segment(s) are ≥ {LONG_SEGMENT_KM:.0f} km, longer "
            "than the partials the model was trained on. Add more splits for "
            "more reliable predictions."
        )

    st.divider()
    if st.button("Run AI prediction", type="primary"):
        with st.spinner("Running the AI model..."):
            try:
                _run_prediction(prof)
            except FileNotFoundError:
                st.error("Trained model file not found. Please (re)train on the "
                         "My Results page.")
            except Exception as exc:  # pragma: no cover - surfaced to the UI
                logger.exception("GPX prediction failed")
                st.error(f"Prediction failed: {exc}")

    _render_prediction()


if __name__ == "__main__":
    main()
