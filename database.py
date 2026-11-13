import asyncio
import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    balance       INTEGER NOT NULL DEFAULT 0,
    ltc_address   TEXT UNIQUE,
    deposit_index INTEGER UNIQUE,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hilo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, guess TEXT NOT NULL, won INTEGER NOT NULL,
    payout INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS registered_wallets (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    currency TEXT NOT NULL,
    address  TEXT NOT NULL,
    UNIQUE(currency, address)
);
CREATE INDEX IF NOT EXISTS idx_rw_addr ON registered_wallets(currency, address);

CREATE TABLE IF NOT EXISTS deposits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    currency     TEXT NOT NULL,
    txid         TEXT NOT NULL UNIQUE,
    from_addr    TEXT,
    amount_raw   INTEGER NOT NULL,
    amount       REAL NOT NULL,
    usd_value    REAL NOT NULL,
    points       INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'credited',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS unmatched_deposits (
    txid       TEXT PRIMARY KEY,
    currency   TEXT NOT NULL,
    from_addr  TEXT,
    amount_raw INTEGER NOT NULL,
    amount     REAL NOT NULL,
    usd_value  REAL NOT NULL,
    points     INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'unmatched',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    currency   TEXT NOT NULL,
    address    TEXT NOT NULL,
    points     INTEGER NOT NULL,
    amount_raw INTEGER NOT NULL,
    txid       TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tips (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id    INTEGER NOT NULL,
    to_id      INTEGER NOT NULL,
    amount     INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coinflips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    wager INTEGER NOT NULL, pick TEXT NOT NULL, result TEXT NOT NULL,
    won INTEGER NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS blackjack (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, player_score INTEGER NOT NULL,
    dealer_score INTEGER NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS mines (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, mines_count INTEGER NOT NULL,
    revealed INTEGER NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS limbo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, target REAL NOT NULL, result REAL NOT NULL,
    payout INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS crash (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, crash_point REAL NOT NULL, cashed_out REAL NOT NULL,
    payout INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS horse (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, horse_chosen INTEGER NOT NULL, winner INTEGER NOT NULL,
    payout INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS baccarat (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, choice TEXT NOT NULL, p_score INTEGER NOT NULL,
    b_score INTEGER NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS towers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, difficulty TEXT NOT NULL, floors INTEGER NOT NULL,
    payout INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS plinko (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, multiplier REAL NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS keno (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    bet INTEGER NOT NULL, picked TEXT NOT NULL, drawn TEXT NOT NULL,
    matches INTEGER NOT NULL, payout INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT NOT NULL
);
"""

class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def init(self):
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    # ── users ──────────────────────────────────────────────────────────
    async def get_or_create_user(self, user_id: int) -> aiosqlite.Row:
        async with self._lock:
            await self.db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
            await self.db.commit()
            cur = await self.db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return await cur.fetchone()

    async def get_user(self, user_id: int):
        cur = await self.db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

    # ── moderation ─────────────────────────────────────────────────────
    async def is_user_banned(self, user_id: int) -> bool:
        cur = await self.db.execute("SELECT 1 FROM settings WHERE key=?", (f"ban_{user_id}",))
        return (await cur.fetchone()) is not None

    async def ban_user(self, user_id: int):
        async with self._lock:
            await self.db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, 'banned')", 
                (f"ban_{user_id}",)
            )
            await self.db.commit()

    async def unban_user(self, user_id: int):
        async with self._lock:
            await self.db.execute("DELETE FROM settings WHERE key=?", (f"ban_{user_id}",))
            await self.db.commit()

    async def reset_user(self, user_id: int):
        """Completely wipes a user's data from the casino."""
        async with self._lock:
            games = ["coinflips", "blackjack", "mines", "limbo", "crash", "horse", "baccarat", "towers", "plinko", "keno"]
            for table in games:
                await self.db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
            
            await self.db.execute("DELETE FROM withdrawals WHERE user_id=?", (user_id,))
            await self.db.execute("DELETE FROM deposits WHERE user_id=?", (user_id,))
            await self.db.execute("DELETE FROM registered_wallets WHERE user_id=?", (user_id,))
            await self.db.execute("DELETE FROM tips WHERE from_id=? OR to_id=?", (user_id, user_id))
            await self.db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            
            await self.db.commit()

    # ── registered wallets ─────────────────────────────────────────────
    async def register_wallet(self, user_id: int, currency: str, address: str) -> str:
        async with self._lock:
            cur = await self.db.execute(
                "SELECT user_id FROM registered_wallets WHERE currency=? AND address=?",
                (currency, address),
            )
            existing = await cur.fetchone()
            if existing:
                return "exists" if existing["user_id"] == user_id else "taken"
            await self.db.execute(
                "INSERT INTO registered_wallets(user_id, currency, address) VALUES(?,?,?)",
                (user_id, currency, address),
            )
            await self.db.commit()
            return "ok"

    async def get_registered_wallet(self, user_id: int, currency: str) -> str | None:
        cur = await self.db.execute(
            "SELECT address FROM registered_wallets WHERE user_id=? AND currency=?",
            (user_id, currency),
        )
        row = await cur.fetchone()
        return row["address"] if row else None

    async def delete_wallet(self, user_id: int, currency: str):
        async with self._lock:
            await self.db.execute(
                "DELETE FROM registered_wallets WHERE user_id=? AND currency=?",
                (user_id, currency)
            )
            await self.db.commit()

    async def find_user_by_wallet(self, currency: str, address: str) -> int | None:
        cur = await self.db.execute(
            "SELECT user_id FROM registered_wallets WHERE currency=? AND address=?",
            (currency, address),
        )
        row = await cur.fetchone()
        return int(row["user_id"]) if row else None

    # ── balance ────────────────────────────────────────────────────────
    async def add_balance(self, user_id: int, delta: int):
        async with self._lock:
            await self.db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?",
                (delta, user_id),
            )
            await self.db.commit()

    async def deduct(self, user_id: int, amount: int) -> bool:
        async with self._lock:
            await self.db.execute("BEGIN IMMEDIATE")
            cur = await self.db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row or row["balance"] < amount:
                await self.db.rollback()
                return False
            await self.db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id=?",
                (amount, user_id),
            )
            await self.db.commit()
            return True

    async def transfer(self, from_id: int, to_id: int, amount: int) -> bool:
        if from_id == to_id or amount <= 0:
            return False
        async with self._lock:
            await self.db.execute("BEGIN IMMEDIATE")
            cur = await self.db.execute("SELECT balance FROM users WHERE user_id=?", (from_id,))
            row = await cur.fetchone()
            if not row or row["balance"] < amount:
                await self.db.rollback()
                return False
            await self.db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id=?",
                (amount, from_id),
            )
            await self.db.execute(
                "INSERT INTO users(user_id, balance) VALUES(?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                (to_id, amount, amount),
            )
            await self.db.execute(
                "INSERT INTO tips(from_id, to_id, amount) VALUES(?,?,?)",
                (from_id, to_id, amount),
            )
            await self.db.commit()
            return True

    # ── deposits ───────────────────────────────────────────────────────
    async def deposit_seen(self, txid: str) -> bool:
        cur = await self.db.execute(
            "SELECT 1 FROM deposits WHERE txid=? UNION SELECT 1 FROM unmatched_deposits WHERE txid=?",
            (txid, txid),
        )
        return (await cur.fetchone()) is not None

    async def record_deposit(
        self, user_id: int, currency: str, txid: str, from_addr: str | None,
        amount_raw: int, amount: float, usd: float, points: int,
        status: str = "credited",
    ) -> bool:
        async with self._lock:
            cur = await self.db.execute(
                "INSERT OR IGNORE INTO deposits"
                "(user_id, currency, txid, from_addr, amount_raw, amount, usd_value, points, status) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (user_id, currency, txid, from_addr, amount_raw, amount, usd, points, status),
            )
            await self.db.commit()
            return cur.rowcount > 0

    async def record_unmatched(
        self, currency: str, txid: str, from_addr: str | None,
        amount_raw: int, amount: float, usd: float, points: int,
    ) -> bool:
        async with self._lock:
            cur = await self.db.execute(
                "INSERT OR IGNORE INTO unmatched_deposits"
                "(txid, currency, from_addr, amount_raw, amount, usd_value, points) "
                "VALUES(?,?,?,?,?,?,?)",
                (txid, currency, from_addr, amount_raw, amount, usd, points),
            )
            await self.db.commit()
            return cur.rowcount > 0

    async def claim_unmatched(self, txid: str, user_id: int) -> dict | None:
        async with self._lock:
            await self.db.execute("BEGIN IMMEDIATE")
            cur = await self.db.execute(
                "SELECT * FROM unmatched_deposits WHERE txid=? AND status='unmatched'",
                (txid,),
            )
            row = await cur.fetchone()
            if not row:
                await self.db.rollback()
                return None

            await self.db.execute("UPDATE unmatched_deposits SET status='claimed' WHERE txid=?", (txid,))
            await self.db.execute(
                "INSERT OR IGNORE INTO deposits"
                "(user_id, currency, txid, from_addr, amount_raw, amount, usd_value, points, status) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (user_id, row["currency"], txid, row["from_addr"], row["amount_raw"], row["amount"], row["usd_value"], row["points"], "credited"),
            )
            await self.db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (row["points"], user_id))
            await self.db.commit()
            return {"points": row["points"], "currency": row["currency"], "amount": row["amount"], "usd": row["usd_value"]}

    # ── withdrawals ────────────────────────────────────────────────────
    async def create_withdrawal(self, user_id: int, currency: str, address: str, points: int, amount_raw: int) -> int:
        async with self._lock:
            cur = await self.db.execute(
                "INSERT INTO withdrawals(user_id, currency, address, points, amount_raw) VALUES(?,?,?,?,?)",
                (user_id, currency, address, points, amount_raw),
            )
            await self.db.commit()
            return cur.lastrowid

    async def complete_withdrawal(self, wid: int, txid: str):
        async with self._lock:
            await self.db.execute("UPDATE withdrawals SET txid=?, status='sent' WHERE id=?", (txid, wid))
            await self.db.commit()

    async def fail_withdrawal(self, wid: int):
        async with self._lock:
            await self.db.execute("UPDATE withdrawals SET status='failed' WHERE id=?", (wid,))
            await self.db.commit()

    # ── game logs ──────────────────────────────────────────────────────
    async def record_hilo(self, user_id: int, bet: int, guess: str, won: bool, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO hilo(user_id, bet, guess, won, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, guess, int(won), payout),
            )
            await self.db.commit()

    async def record_coinflip(self, user_id: int, wager: int, pick: str, result: str, won: bool, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO coinflips(user_id, wager, pick, result, won, payout) VALUES(?,?,?,?,?,?)",
                (user_id, wager, pick, result, int(won), payout),
            )
            await self.db.commit()

    async def record_blackjack(self, user_id: int, bet: int, p_score: int, d_score: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO blackjack(user_id, bet, player_score, dealer_score, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, p_score, d_score, payout),
            )
            await self.db.commit()

    async def record_mines(self, user_id: int, bet: int, mines_count: int, revealed: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO mines(user_id, bet, mines_count, revealed, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, mines_count, revealed, payout),
            )
            await self.db.commit()

    async def record_limbo(self, user_id: int, bet: int, target: float, result: float, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO limbo(user_id, bet, target, result, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, target, result, payout),
            )
            await self.db.commit()

    async def record_crash(self, user_id: int, bet: int, crash_point: float, cashed_out: float, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO crash(user_id, bet, crash_point, cashed_out, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, crash_point, cashed_out, payout),
            )
            await self.db.commit()

    async def record_horse(self, user_id: int, bet: int, horse_chosen: int, winner: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO horse(user_id, bet, horse_chosen, winner, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, horse_chosen, winner, payout),
            )
            await self.db.commit()

    async def record_baccarat(self, user_id: int, bet: int, choice: str, p_score: int, b_score: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO baccarat(user_id, bet, choice, p_score, b_score, payout) VALUES(?,?,?,?,?,?)",
                (user_id, bet, choice, p_score, b_score, payout),
            )
            await self.db.commit()

    async def record_towers(self, user_id: int, bet: int, difficulty: str, floors: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO towers(user_id, bet, difficulty, floors, payout) VALUES(?,?,?,?,?)",
                (user_id, bet, difficulty, floors, payout),
            )
            await self.db.commit()

    async def record_plinko(self, user_id: int, bet: int, multiplier: float, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO plinko(user_id, bet, multiplier, payout) VALUES(?,?,?,?)",
                (user_id, bet, multiplier, payout),
            )
            await self.db.commit()

    async def record_keno(self, user_id: int, bet: int, picked: str, drawn: str, matches: int, payout: int):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO keno(user_id, bet, picked, drawn, matches, payout) VALUES(?,?,?,?,?,?)",
                (user_id, bet, picked, drawn, matches, payout),
            )
            await self.db.commit()

    # ── threads ────────────────────────────────────────────────────────
    async def get_thread_count(self, user_id: int) -> int:
        async with self._lock:
            cur = await self.db.execute("SELECT COUNT(*) FROM threads WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return int(row[0])

    async def add_thread(self, user_id: int, thread_id: int):
        async with self._lock:
            await self.db.execute("INSERT INTO threads(user_id, thread_id) VALUES(?, ?)", (user_id, thread_id))
            await self.db.commit()

    async def remove_thread(self, thread_id: int):
        async with self._lock:
            await self.db.execute("DELETE FROM threads WHERE thread_id=?", (thread_id,))
            await self.db.commit()

    # ── stats ──────────────────────────────────────────────────────────
    async def get_user_stats(self, user_id: int):
        async with self._lock:
            cur = await self.db.execute("""
                SELECT 
                    COALESCE(SUM(bet), 0) as total_wagered,
                    COALESCE(SUM(payout), 0) as total_won,
                    COUNT(id) as total_played
                FROM (
                    SELECT id, wager as bet, payout FROM coinflips WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM blackjack WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM mines WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM limbo WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM crash WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM horse WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM baccarat WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM towers WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM plinko WHERE user_id=?
                    UNION ALL
                    SELECT id, bet, payout FROM keno WHERE user_id=?
                )
            """, (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
            games = await cur.fetchone()

            cur = await self.db.execute(
                "SELECT COALESCE(SUM(points), 0) as total_withdrawn, COUNT(id) as withdraw_count FROM withdrawals WHERE user_id=? AND status='sent'",
                (user_id,)
            )
            withdrawals = await cur.fetchone()

            cur = await self.db.execute("SELECT COALESCE(SUM(amount), 0) as sent FROM tips WHERE from_id=?", (user_id,))
            tips_sent = await cur.fetchone()
            
            cur = await self.db.execute("SELECT COALESCE(SUM(amount), 0) as recv FROM tips WHERE to_id=?", (user_id,))
            tips_recv = await cur.fetchone()

            cur = await self.db.execute("""
                SELECT COALESCE(SUM(bet), 0) as week_wagered
                FROM (
                    SELECT wager as bet, created_at FROM coinflips WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM blackjack WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM mines WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM limbo WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM crash WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM horse WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM baccarat WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM towers WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM plinko WHERE user_id=?
                    UNION ALL
                    SELECT bet, created_at FROM keno WHERE user_id=?
                )
                WHERE created_at >= datetime('now', '-7 days')
            """, (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
            week_wagered = await cur.fetchone()

            return {
                "total_wagered": games["total_wagered"],
                "total_won": games["total_won"],
                "total_played": games["total_played"],
                "withdrawn": withdrawals["total_withdrawn"],
                "withdraw_count": withdrawals["withdraw_count"],
                "tips_sent": tips_sent["sent"],
                "tips_recv": tips_recv["recv"],
                "week_wagered": week_wagered["week_wagered"]
            }

    # ── settings ───────────────────────────────────────────────────────
    async def set_setting(self, key: str, value: str):
        async with self._lock:
            await self.db.execute(
                "INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            await self.db.commit()