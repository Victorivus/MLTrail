'''
Module to load the features table with data present in the DB
'''
import os
import json
import sqlite3
import argparse
from database.create_db import Database
from database.loader_LiveTrail import db_LiveTrail_loader


def empty_features(db_path):
    '''
    Function to empty the table features
    '''
    db: Database = Database.create_database(path=db_path)
    conn = sqlite3.connect(db.path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM features
            ''')
            conn.commit()
    finally:
        conn.close()

def clean_spurious(db_path):
    '''
    Function to Remove the spourious segments from the table features,
    If the first CP is departure, there is this record added, so we clean them.
    '''
    db: Database = Database.create_database(path=db_path)
    conn = sqlite3.connect(db.path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM features
                WHERE
                    time = '00:00:00' AND
                    elevation_pos_segment = 0 AND
                    elevation_pos_cumul = 0 AND
                    elevation_neg_segment = 0 AND
                    elevation_neg_cumul = 0
            ''')
            conn.commit()
    finally:
        conn.close()


def load_features(db_path: str, clean: bool = False, update: dict = None):
    '''
    Function to load the features table from the timing_points
    Args:
        path (str): Path to SQLite3 DB.
        clean (bool): If True, the tables will be emtied before execution.
        update (dict): If specified, dict containing the list of files to use.
    '''

    if clean:
        empty_features(db_path)

    db: Database = Database.create_database(path=db_path)
    conn = sqlite3.connect(db.path, timeout=36000)  # 10h timeout
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                WITH ParsedTimes AS (
                SELECT
                    tp.race_id,
                    tp.event_id,
                    tp.bib,
                    cp.distance AS dist_cumul,
                    cp.elevation_pos AS elevation_pos_cumul,
                    cp.elevation_neg AS elevation_neg_cumul,
                    tp.time,
                    (SELECT MAX(distance) FROM control_points WHERE race_id = tp.race_id AND event_id = tp.event_id) AS dist_total,
                    (SELECT MAX(elevation_pos) FROM control_points WHERE race_id = tp.race_id AND event_id = tp.event_id) AS elevation_pos_total,
                    (SELECT MIN(elevation_neg) FROM control_points WHERE race_id = tp.race_id AND event_id = tp.event_id) AS elevation_neg_total,
                    cp.elevation_pos - LAG(cp.elevation_pos, 1, 0) OVER (PARTITION BY tp.race_id, tp.event_id, tp.bib ORDER BY cp.control_point_id) AS elevation_pos_segment,
                    cp.elevation_neg - LAG(cp.elevation_neg, 1, 0) OVER (PARTITION BY tp.race_id, tp.event_id, tp.bib ORDER BY cp.control_point_id) AS elevation_neg_segment,
                    cp.distance - LAG(cp.distance, 1, 0) OVER (PARTITION BY tp.race_id, tp.event_id, tp.bib ORDER BY cp.control_point_id) AS dist_segment,
                    -- only way to be able to work with >24h times
                    (SUBSTR(tp.time, 1, 2) * 3600) + (SUBSTR(tp.time, 4, 2) * 60) + SUBSTR(tp.time, 7, 2) AS time_in_seconds,
                    LAG((SUBSTR(tp.time, 1, 2) * 3600) + (SUBSTR(tp.time, 4, 2) * 60) + SUBSTR(tp.time, 7, 2), 1, 0) OVER (PARTITION BY tp.race_id, tp.event_id, tp.bib ORDER BY cp.control_point_id) AS prev_time_in_seconds
                FROM
                    timing_points tp
                JOIN
                    control_points cp ON tp.control_point_id = cp.control_point_id
            ),
            TimeDifferences AS (
                SELECT
                    race_id,
                    event_id,
                    bib,
                    dist_cumul,
                    elevation_pos_cumul,
                    elevation_neg_cumul,
                    dist_total,
                    elevation_pos_total,
                    elevation_neg_total,
                    elevation_pos_segment,
                    elevation_neg_segment,
                    dist_segment,
                    time,
                    -- Compute time difference, adjust for times crossing 24 hours boundary
                    printf('%02d:%02d:%02d',
                        (time_in_seconds - prev_time_in_seconds ) / 3600,
                        ((time_in_seconds - prev_time_in_seconds ) % 3600) / 60,
                        ((time_in_seconds - prev_time_in_seconds ) % 3600) % 60
                    ) AS time_segment
                FROM
                    ParsedTimes
            ),
            -- Next part of the query is to add an extra line of full race data
            TotalStats AS (
                SELECT
                    race_id,
                    event_id,
                    bib,
                    dist_total AS dist_cumul,
                    elevation_pos_total AS elevation_pos_cumul,
                    elevation_neg_total AS elevation_neg_cumul,
                    dist_total AS dist_total,
                    elevation_pos_total AS elevation_pos_total,
                    elevation_neg_total AS elevation_neg_total,
                    dist_total AS dist_segment,
                    elevation_pos_total AS elevation_pos_segment,
                    elevation_neg_total AS elevation_neg_segment,
                    (SELECT printf('%02d:%02d:%02d',
                        MAX(time_in_seconds) / 3600,
                        (MAX(time_in_seconds) % 3600) / 60,
                        (MAX(time_in_seconds) % 3600) % 60
                    ) FROM ParsedTimes pt
                    WHERE pt.race_id = t.race_id AND pt.event_id = t.event_id AND pt.bib = t.bib) AS time_segment
                FROM
                    TimeDifferences t
                WHERE
                    dist_cumul = dist_total
            )
            INSERT INTO features (
                race_id,
                event_id,
                bib,
                dist_total,
                elevation_pos_total,
                elevation_neg_total,
                dist_segment,
                dist_cumul,
                elevation_pos_segment,
                elevation_pos_cumul,
                elevation_neg_segment,
                elevation_neg_cumul,
                time
            )
            SELECT
                race_id,
                event_id,
                bib,
                dist_total,
                elevation_pos_total,
                elevation_neg_total,
                dist_segment,
                dist_cumul,
                elevation_pos_segment,
                elevation_pos_cumul,
                elevation_neg_segment,
                elevation_neg_cumul,
                time_segment
            FROM
                TimeDifferences
            UNION ALL
            SELECT
                race_id,
                event_id,
                bib,
                dist_total,
                elevation_pos_total,
                elevation_neg_total,
                dist_segment,
                dist_cumul,
                elevation_pos_segment,
                elevation_pos_cumul,
                elevation_neg_segment,
                elevation_neg_cumul,
                time_segment
            FROM
                TotalStats
            ORDER BY
                race_id,
                event_id,
                bib
        ''')
            conn.commit()
    finally:
        conn.close()

    clean_spurious(db.path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Data loader from CSV files into results table.')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('-p', '--path', default=None, help='DB path.')
    parser.add_argument('-c', '--clean', action='store_true', help='Remove all data from table before execution.')
    group.add_argument('-u', '--update', type=str, default=None, help='dict in "years" format containing the list of events and years to update or path for the file containing the list.')

    args = parser.parse_args()
    path = args.path
    clean = args.clean
    update = args.update
    if update:
        raise NotImplementedError
        # try:
        #     update = json.loads(args.update)
        # except json.JSONDecodeError:
        #     update = db_LiveTrail_loader.parse_events_years_txt_file(os.path.join(os.getcwd(), args.update))

    if not path:
        path = os.path.join(os.environ["DATA_DIR_PATH"], 'events.db')

    load_features(db_path=path, clean=clean)
