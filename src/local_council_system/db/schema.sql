CREATE TABLE municipalities (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefecture TEXT NOT NULL
);

CREATE TABLE meetings (
    id TEXT PRIMARY KEY,
    municipality_code TEXT NOT NULL,
    session TEXT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    issue INTEGER,
    source_url TEXT NOT NULL,
    pdf_url TEXT,
    FOREIGN KEY (municipality_code) REFERENCES municipalities(code)
);

CREATE TABLE speeches (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    speech_order INTEGER NOT NULL,
    speaker_name TEXT NOT NULL,
    speaker_yomi TEXT,
    speaker_group TEXT,
    speaker_position TEXT,
    speaker_role TEXT,
    speech_text TEXT NOT NULL,
    start_page INTEGER,
    source_url TEXT,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id),
    UNIQUE (meeting_id, speech_order)
);

CREATE INDEX idx_meetings_date ON meetings(date);
CREATE INDEX idx_meetings_municipality ON meetings(municipality_code);
CREATE INDEX idx_meetings_name ON meetings(name);
CREATE INDEX idx_speeches_meeting ON speeches(meeting_id);
CREATE INDEX idx_speeches_speaker ON speeches(speaker_name);
