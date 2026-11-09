"""A SQLite database shaped like ARM 2.24.4's, for the exporter's tests.

The `job` and `track` tables have the columns, order and declared types of a
deployed ARM 2.24.4 database, which ARM's migrations built: they differ from
`arm/models/job.py` in putting `path` and `stage` after `pid_hash`, as bare
VARCHAR. Values are stored as SQLAlchemy stores them, as on that database:
booleans 0/1, datetimes as text with a space before the time. Rows are
synthetic; a real arm.db is never committed. `reelbarrow_raw_copy` is the
deployment's patch's table (*The raw copy's record*).
"""

import json
import sqlite3
from pathlib import Path

JOB = """
CREATE TABLE job (
    job_id INTEGER NOT NULL,
    arm_version VARCHAR(20),
    crc_id VARCHAR(63),
    logfile VARCHAR(256),
    start_time DATETIME,
    stop_time DATETIME,
    job_length VARCHAR(12),
    status VARCHAR(32),
    no_of_titles INTEGER,
    title VARCHAR(256),
    title_auto VARCHAR(256),
    title_manual VARCHAR(256),
    year VARCHAR(4),
    year_auto VARCHAR(4),
    year_manual VARCHAR(4),
    video_type VARCHAR(20),
    video_type_auto VARCHAR(20),
    video_type_manual VARCHAR(20),
    imdb_id VARCHAR(15),
    imdb_id_auto VARCHAR(15),
    imdb_id_manual VARCHAR(15),
    poster_url VARCHAR(256),
    poster_url_auto VARCHAR(256),
    poster_url_manual VARCHAR(256),
    devpath VARCHAR(15),
    mountpoint VARCHAR(20),
    hasnicetitle BOOLEAN,
    errors TEXT,
    disctype VARCHAR(20),
    label VARCHAR(256),
    ejected BOOLEAN,
    updated BOOLEAN,
    pid INTEGER,
    pid_hash INTEGER,
    path VARCHAR,
    stage VARCHAR,
    is_iso BOOLEAN,
    manual_start BOOLEAN,
    manual_mode BOOLEAN,
    PRIMARY KEY (job_id)
)
"""

TRACK = """
CREATE TABLE track (
    track_id INTEGER NOT NULL,
    job_id INTEGER,
    track_number VARCHAR(4),
    length INTEGER,
    aspect_ratio VARCHAR(20),
    fps FLOAT,
    main_feature BOOLEAN,
    basename VARCHAR(256),
    filename VARCHAR(256),
    orig_filename VARCHAR(256),
    new_filename VARCHAR(256),
    ripped BOOLEAN,
    status VARCHAR(32),
    error TEXT,
    source VARCHAR(32),
    process BOOLEAN,
    chapters INTEGER,
    filesize BIGINT,
    PRIMARY KEY (track_id),
    FOREIGN KEY(job_id) REFERENCES job (job_id)
)
"""

# A cut-down config table: it holds ARM's API keys, and must never reach a
# manifest.
CONFIG = """
CREATE TABLE config (
    CONFIG_ID INTEGER NOT NULL,
    job_id INTEGER,
    OMDB_API_KEY VARCHAR(256),
    PO_USER_KEY VARCHAR(64),
    PRIMARY KEY (CONFIG_ID),
    FOREIGN KEY(job_id) REFERENCES job (job_id)
)
"""

SECRET = "not-a-real-omdb-key-0123456789"


def job(job_id: int, **overrides) -> dict:
    """A DVD movie job as ARM leaves it on success."""
    row = {
        "job_id": job_id,
        "arm_version": "2.24.4",
        "crc_id": "1a2b3c4d5e6f7081",
        "logfile": f"SAMPLE_MOVIE_{job_id}.log",
        "start_time": "2026-10-21 19:49:49.973701",
        "stop_time": "2026-10-21 21:02:13.204518",
        "job_length": "1:12:23",
        "status": "success",
        "no_of_titles": 2,
        "title": "Sample-Movie",
        "title_auto": "Sample-Movie",
        "title_manual": None,
        "year": "1965",
        "year_auto": "1965",
        "year_manual": None,
        "video_type": "movie",
        "video_type_auto": "movie",
        "video_type_manual": None,
        "imdb_id": "tt0000000",
        "imdb_id_auto": "tt0000000",
        "imdb_id_manual": None,
        "poster_url": None,
        "poster_url_auto": None,
        "poster_url_manual": None,
        "devpath": "/dev/sr0",
        "mountpoint": "/mnt/dev/sr0",
        "hasnicetitle": 1,
        "errors": None,
        "disctype": "dvd",
        "label": "SAMPLE_MOVIE",
        "ejected": 1,
        "updated": 0,
        "pid": 4242,
        "pid_hash": 8061347162311430543,
        "path": "/root/video/completed/movies/Sample-Movie (1965)",
        "stage": "176107498997",
        "is_iso": 0,
        "manual_start": 0,
        "manual_mode": 0,
    }
    return row | overrides


def track(track_id: int, job_id: int, **overrides) -> dict:
    """A HandBrake track row, transcoded."""
    row = {
        "track_id": track_id,
        "job_id": job_id,
        "track_number": "1",
        "length": 6372,
        "aspect_ratio": "16:9",
        "fps": 23.976,
        "main_feature": 1,
        "basename": "SAMPLE_MOVIE",
        "filename": "title_1.mkv",
        "orig_filename": None,
        "new_filename": None,
        "ripped": 1,
        "status": "success",
        "error": None,
        "source": "HandBrake",
        "process": 1,
        "chapters": 24,
        "filesize": 4718592000,
    }
    return row | overrides


# The deployment's raw-copy record, as its patch creates it.
RAW_COPY = """
CREATE TABLE reelbarrow_raw_copy (job_id INTEGER PRIMARY KEY, document TEXT NOT NULL)
"""


def create(path: Path, *, raw_copy: bool = True) -> Path:
    with sqlite3.connect(path) as con:
        con.execute(JOB)
        con.execute(TRACK)
        con.execute(CONFIG)
        if raw_copy:
            con.execute(RAW_COPY)
    con.close()
    return path


def raw_copy(job_id: int, **overrides) -> dict:
    """A DVD image's record, as the patch leaves it once the job has filed its
    transcodes: two titles, the second not saved."""
    folder = "/root/video/raw/SAMPLE_MOVIE"
    completed = "/root/video/completed/movies/Sample-Movie (1965)"
    document = {
        "schema": 1,
        "folder": folder,
        "form": "dvd-image",
        "complete": {"value": True, "reason": "sizes_and_hashes"},
        "problems": [],
        "title_map": [
            {
                "disc_title": 1,
                "mkv": f"{folder}/titles/SAMPLE-B1_t00.mkv",
                "handbrake_title": 1,
            },
            {
                "disc_title": 3,
                "mkv": f"{folder}/titles/SAMPLE-C1_t01.mkv",
                "handbrake_title": None,
            },
        ],
        "image": f"{folder}/SAMPLE_MOVIE.iso",
        "transcodes": {"1": f"{completed}/title_1.mkv"},
    }
    return {"job_id": job_id, "document": json.dumps(document | overrides)}


def insert(path: Path, table: str, row: dict) -> None:
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with sqlite3.connect(path) as con:
        con.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(row.values())
        )
    con.close()


def execute(path: Path, sql: str, *params) -> None:
    with sqlite3.connect(path) as con:
        con.execute(sql, params)
    con.close()
