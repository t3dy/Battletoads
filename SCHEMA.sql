-- NES Music Extraction Pipeline — Canonical Schema
-- Frame-level APU state is the source of truth.
-- MIDI, RPP, WAV are downstream projections.

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  developer TEXT,
  year INTEGER,
  mapper INTEGER,
  region TEXT CHECK (region IN ('ntsc', 'pal', 'dual') OR region IS NULL),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_files (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL CHECK (
    source_type IN ('rom','nsf','mesen_trace','disassembly','track_manifest','reference_audio')
  ),
  path TEXT NOT NULL,
  sha256 TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(game_id, source_type, path)
);

CREATE TABLE IF NOT EXISTS track_names (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  track_number INTEGER NOT NULL,
  track_name TEXT NOT NULL,
  game_context TEXT,
  source_url TEXT,
  UNIQUE(game_id, track_number)
);

CREATE TABLE IF NOT EXISTS manifests (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  version TEXT NOT NULL,
  sound_driver TEXT,
  channels_used_json TEXT NOT NULL DEFAULT '[]',
  period_table_json TEXT NOT NULL DEFAULT '[]',
  envelope_model TEXT,
  percussion_type TEXT,
  known_facts_json TEXT NOT NULL DEFAULT '[]',
  hypotheses_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(game_id, version)
);

CREATE TABLE IF NOT EXISTS captures (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
  capture_kind TEXT NOT NULL CHECK (capture_kind IN ('nsf_run', 'mesen_trace')),
  track_number INTEGER,
  capture_label TEXT,
  total_frames INTEGER,
  song_start_frame INTEGER,
  song_end_frame INTEGER,
  verification_status TEXT NOT NULL DEFAULT 'needs_review' CHECK (
    verification_status IN ('verified', 'needs_review', 'hypothesis')
  ),
  verification_notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS frame_states (
  id INTEGER PRIMARY KEY,
  capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  frame INTEGER NOT NULL,
  channel TEXT NOT NULL CHECK (
    channel IN ('pulse1', 'pulse2', 'triangle', 'noise', 'dpcm')
  ),
  period INTEGER,
  midi_note INTEGER,
  volume INTEGER CHECK (volume BETWEEN 0 AND 15 OR volume IS NULL),
  duty INTEGER CHECK (duty BETWEEN 0 AND 3 OR duty IS NULL),
  constant_volume INTEGER CHECK (constant_volume IN (0,1) OR constant_volume IS NULL),
  linear_counter INTEGER,
  length_counter INTEGER,
  noise_mode INTEGER CHECK (noise_mode IN (0,1) OR noise_mode IS NULL),
  sounding INTEGER CHECK (sounding IN (0,1) OR sounding IS NULL),
  source_method TEXT NOT NULL DEFAULT 'trace' CHECK (
    source_method IN ('trace', 'nsf_parser', 'hybrid')
  ),
  UNIQUE(capture_id, frame, channel)
);

CREATE INDEX IF NOT EXISTS idx_fs_capture_frame ON frame_states(capture_id, frame);
CREATE INDEX IF NOT EXISTS idx_fs_capture_channel ON frame_states(capture_id, channel, frame);

CREATE TABLE IF NOT EXISTS note_events (
  id INTEGER PRIMARY KEY,
  capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  frame_start INTEGER NOT NULL,
  frame_end INTEGER,
  midi_note INTEGER,
  velocity INTEGER CHECK (velocity BETWEEN 0 AND 127 OR velocity IS NULL),
  source_method TEXT NOT NULL CHECK (
    source_method IN ('trace', 'nsf_parser', 'hybrid')
  ),
  confidence REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS cc_events (
  id INTEGER PRIMARY KEY,
  capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  frame INTEGER NOT NULL,
  cc_number INTEGER NOT NULL CHECK (cc_number IN (11, 12)),
  cc_value INTEGER NOT NULL CHECK (cc_value BETWEEN 0 AND 127),
  source_method TEXT NOT NULL CHECK (
    source_method IN ('trace', 'nsf_parser', 'hybrid')
  )
);

CREATE TABLE IF NOT EXISTS drum_events (
  id INTEGER PRIMARY KEY,
  capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  frame INTEGER NOT NULL,
  gm_note INTEGER,
  velocity INTEGER CHECK (velocity BETWEEN 0 AND 127 OR velocity IS NULL),
  noise_period INTEGER,
  noise_mode INTEGER CHECK (noise_mode IN (0,1) OR noise_mode IS NULL),
  detection_method TEXT NOT NULL CHECK (
    detection_method IN ('vol_gate', 'period_change', 'hybrid')
  ),
  confidence REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS output_artifacts (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  capture_id INTEGER REFERENCES captures(id) ON DELETE SET NULL,
  artifact_type TEXT NOT NULL CHECK (
    artifact_type IN ('midi', 'rpp', 'wav', 'sysex_midi', 'report')
  ),
  path TEXT NOT NULL,
  build_tool TEXT,
  synth_mode TEXT NOT NULL DEFAULT 'n/a' CHECK (
    synth_mode IN ('console_cc', 'apu2_sysex', 'n/a')
  ),
  version TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validation_runs (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  capture_id INTEGER REFERENCES captures(id) ON DELETE SET NULL,
  run_type TEXT NOT NULL CHECK (
    run_type IN (
      'startup_check', 'source_integrity', 'trace_compare',
      'parameter_coverage', 'artifact_build', 'pre_delivery',
      'batch_build', 'synth_validation'
    )
  ),
  status TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'warn')),
  summary TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validation_metrics (
  id INTEGER PRIMARY KEY,
  validation_run_id INTEGER NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
  metric_name TEXT NOT NULL,
  metric_value REAL,
  metric_text TEXT
);

CREATE TABLE IF NOT EXISTS mismatches (
  id INTEGER PRIMARY KEY,
  validation_run_id INTEGER NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
  frame INTEGER,
  channel TEXT,
  parameter TEXT,
  expected_value TEXT,
  actual_value TEXT,
  severity TEXT NOT NULL CHECK (severity IN ('info', 'warn', 'fail')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS session_decisions (
  id INTEGER PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  decision_key TEXT NOT NULL,
  decision_value TEXT NOT NULL,
  rationale TEXT,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL CHECK (status IN ('verified', 'tentative', 'superseded')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
