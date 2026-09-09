-- Allergy AI Companion — PostgreSQL schema (generated from docs/erd/gen_dmm.py)
-- Source of truth for the ERD is docs/erd/allergy_ai.dmm (open in Luna Modeler).

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (email)
);

CREATE TABLE user_allergies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    allergen VARCHAR(30) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE symptom_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    conversation_id INTEGER,
    symptoms JSONB NOT NULL,
    severity INTEGER,
    duration VARCHAR(50),
    possible_trigger VARCHAR(50),
    breathing_difficulty BOOLEAN NOT NULL DEFAULT false,
    airway_swelling BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE TABLE triage_results (
    id SERIAL PRIMARY KEY,
    symptom_event_id INTEGER NOT NULL,
    risk_level VARCHAR(12) NOT NULL,
    recommendation TEXT,
    rule_version VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (symptom_event_id) REFERENCES symptom_events(id) ON DELETE CASCADE
);

CREATE TABLE environment_snapshots (
    id SERIAL PRIMARY KEY,
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    tree_pollen VARCHAR(10),
    grass_pollen VARCHAR(10),
    weed_pollen VARCHAR(10),
    pm25 NUMERIC(6,2),
    pm10 NUMERIC(6,2),
    temperature NUMERIC(5,2),
    humidity NUMERIC(5,2),
    wind_speed NUMERIC(5,2),
    risk_level VARCHAR(12),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    environment_snapshot_id INTEGER,
    risk_level VARCHAR(12) NOT NULL,
    alert_type VARCHAR(15) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (environment_snapshot_id) REFERENCES environment_snapshots(id) ON DELETE SET NULL
);

CREATE TABLE notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    alert_pollen BOOLEAN NOT NULL DEFAULT true,
    alert_air_quality BOOLEAN NOT NULL DEFAULT true,
    alert_weather BOOLEAN NOT NULL DEFAULT true,
    min_risk_level VARCHAR(12) NOT NULL DEFAULT 'MODERATE',
    quiet_hours_start INTEGER,
    quiet_hours_end INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE hospital_searches (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    specialty VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE hospital_results (
    id SERIAL PRIMARY KEY,
    hospital_search_id INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    address VARCHAR(300),
    distance_m INTEGER,
    specialty VARCHAR(40),
    is_open BOOLEAN,
    phone VARCHAR(40),
    place_id VARCHAR(120),
    rank INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (hospital_search_id) REFERENCES hospital_searches(id) ON DELETE CASCADE
);
