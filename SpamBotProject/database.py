import sqlite3
from config import PRICE_USDT

DB_PATH = 'spambots.db'

def _conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS bots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id   INTEGER NOT NULL,
            token      TEXT    UNIQUE NOT NULL,
            admin_id   INTEGER NOT NULL,
            active     INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bot_users (
            bot_id  INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (bot_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS used_txs (
            tx_hash    TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    conn.commit(); conn.close()

# ── Bots ──────────────────────────────────────────────
def db_add_bot(owner_id, token, admin_id):
    c = _conn()
    c.execute('INSERT INTO bots (owner_id, token, admin_id) VALUES (?,?,?)',
              (owner_id, token, admin_id))
    row_id = c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.commit(); c.close()
    return row_id

def db_get_all_bots():
    c = _conn()
    rows = c.execute('SELECT id, token, admin_id, owner_id FROM bots WHERE active=1').fetchall()
    c.close(); return rows

def db_get_owner_bot(owner_id):
    c = _conn()
    row = c.execute('SELECT id FROM bots WHERE owner_id=? AND active=1', (owner_id,)).fetchone()
    c.close(); return row[0] if row else None

# ── Users ─────────────────────────────────────────────
def db_add_user(bot_id, user_id):
    c = _conn()
    c.execute('INSERT OR IGNORE INTO bot_users (bot_id, user_id) VALUES (?,?)', (bot_id, user_id))
    c.commit(); c.close()

def db_get_bot_users(bot_id):
    c = _conn()
    rows = c.execute('SELECT user_id FROM bot_users WHERE bot_id=?', (bot_id,)).fetchall()
    c.close(); return [r[0] for r in rows]

def db_get_all_users():
    c = _conn()
    rows = c.execute('SELECT DISTINCT user_id FROM bot_users').fetchall()
    c.close(); return [r[0] for r in rows]

# ── Transactions ──────────────────────────────────────
def db_is_tx_used(tx_hash: str) -> bool:
    c = _conn()
    row = c.execute('SELECT 1 FROM used_txs WHERE tx_hash=?', (tx_hash,)).fetchone()
    c.close(); return row is not None

def db_mark_tx_used(tx_hash: str, user_id: int):
    c = _conn()
    c.execute('INSERT OR IGNORE INTO used_txs (tx_hash, user_id) VALUES (?,?)', (tx_hash, user_id))
    c.commit(); c.close()

# ── Settings / Price ──────────────────────────────────
def get_price() -> float:
    c = _conn()
    row = c.execute("SELECT value FROM settings WHERE key='price'").fetchone()
    c.close()
    return float(row[0]) if row else PRICE_USDT

def set_price(price: float):
    c = _conn()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('price', ?)", (str(price),))
    c.commit(); c.close()

# ── Statistics ────────────────────────────────────────
def db_get_stats():
    c = _conn()
    bots_count  = c.execute('SELECT COUNT(*) FROM bots WHERE active=1').fetchone()[0]
    main_users  = c.execute('SELECT COUNT(*) FROM bot_users WHERE bot_id=0').fetchone()[0]
    total_users = c.execute('SELECT COUNT(DISTINCT user_id) FROM bot_users').fetchone()[0]
    breakdown   = c.execute(
        'SELECT b.owner_id, b.id, COUNT(bu.user_id) '
        'FROM bots b LEFT JOIN bot_users bu ON b.id=bu.bot_id '
        'WHERE b.active=1 GROUP BY b.id ORDER BY COUNT(bu.user_id) DESC'
    ).fetchall()
    c.close()
    return bots_count, main_users, total_users, breakdown
