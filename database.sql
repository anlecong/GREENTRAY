PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'customer')),
    password_hash TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    box_type TEXT NOT NULL DEFAULT 'Hộp',
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'rented', 'cleaning')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rentals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    deposit INTEGER NOT NULL CHECK (deposit >= 0),
    status TEXT NOT NULL CHECK (status IN ('rented', 'returned')),
    condition TEXT,
    rented_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    returned_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS one_open_rental_per_box
    ON rentals(box_id) WHERE status = 'rented';

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    rental_id TEXT NOT NULL REFERENCES rentals(id),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('rent', 'return')),
    amount INTEGER NOT NULL,
    green_points INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('deposit_amount', '10000');
