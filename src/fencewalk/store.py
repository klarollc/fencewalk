"""Engagement store: one SQLite database per engagement.

The store enforces the method's invariants in code:

- A coverage score with no cited inventory entries may only be saved as
  Unknown, or as Not applicable with a non-empty N/A reason. Every other
  non-Unknown status requires at least one cited entry, and Not applicable
  always requires a written reason.
- Evidence labels and fix statuses change only through explicit calls that
  record the date and the actor; every change is appended to a history
  table. No code path upgrades an UNKNOWN label implicitly.

Files are the interchange: everything in the store can be rebuilt from the
fixture files (see fencewalk.fixture).
"""

import re
import sqlite3

EVIDENCE_LABELS = ("VERIFIED", "ON RECORD", "UNKNOWN")


def _verify_next_seq(seq):
    if type(seq) is int:
        return seq
    if isinstance(seq, str):
        try:
            number = int(seq)
        except ValueError:
            pass
        else:
            if str(number) == seq:
                return number
    raise ValueError("verify-next seq must be a canonical integer")

UNSET = object()
"""Sentinel for update_entry_details date arguments: UNSET leaves a date
unchanged, None clears it, a string sets it. (None cannot be the "leave
unchanged" marker for dates, because clearing a date must be expressible.)"""
COVERAGE_STATUSES = ("Covered", "Partial", "Unknown", "Not applicable", "Gap")
FIX_STATUSES = ("proposed", "approved", "done", "deferred")
ADJUDICATION_SECTIONS = ("coverage", "chains", "fixes", "verify-next")
ADJUDICATION_DECISIONS = ("accept", "correct", "reject")
METHOD_ORDERS = ("verify-first", "model-first")
PACKET_POSTURES = ("standard", "adversarial")
PROBE_OUTCOMES = ("confirmed", "failed", "inconclusive")

SCHEMA = """
CREATE TABLE engagement (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    subject_label TEXT NOT NULL,
    created_date  TEXT NOT NULL,
    method_order  TEXT NOT NULL CHECK (method_order IN ('verify-first', 'model-first')),
    primary_pack  TEXT
);

CREATE TABLE inventory_entry (
    entry_id     TEXT PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    section      TEXT NOT NULL,
    body         TEXT NOT NULL,
    label        TEXT NOT NULL CHECK (label IN ('VERIFIED', 'ON RECORD', 'UNKNOWN')),
    source       TEXT NOT NULL,
    checked_date TEXT,
    decay_date   TEXT
);

CREATE TABLE entry_label_history (
    id         INTEGER PRIMARY KEY,
    entry_id   TEXT NOT NULL REFERENCES inventory_entry (entry_id),
    label      TEXT NOT NULL,
    date       TEXT NOT NULL,
    actor      TEXT NOT NULL
);

CREATE TABLE rubric_pack (
    pack_id         TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source_citation TEXT NOT NULL,
    version         TEXT NOT NULL
);

CREATE TABLE rubric_item (
    pack_id    TEXT NOT NULL REFERENCES rubric_pack (pack_id),
    item_id    TEXT NOT NULL,
    group_name TEXT NOT NULL,
    text       TEXT NOT NULL,
    PRIMARY KEY (pack_id, item_id)
);

CREATE TABLE coverage_score (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    pack_id       TEXT NOT NULL,
    item_id       TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('Covered', 'Partial', 'Unknown', 'Not applicable', 'Gap')),
    reasoning     TEXT NOT NULL,
    na_reason     TEXT,
    FOREIGN KEY (pack_id, item_id) REFERENCES rubric_item (pack_id, item_id)
);

CREATE TABLE coverage_citation (
    score_id INTEGER NOT NULL REFERENCES coverage_score (id),
    entry_id TEXT NOT NULL REFERENCES inventory_entry (entry_id),
    PRIMARY KEY (score_id, entry_id)
);

CREATE TABLE chain (
    id              INTEGER PRIMARY KEY,
    engagement_id   INTEGER NOT NULL REFERENCES engagement (id),
    chain_key       TEXT NOT NULL,
    name            TEXT NOT NULL,
    earliest_control TEXT NOT NULL,
    control_rubric  TEXT,
    control_status  TEXT NOT NULL,
    control_pack    TEXT
);

CREATE TABLE chain_step (
    chain_id  INTEGER NOT NULL REFERENCES chain (id),
    step_no   INTEGER NOT NULL,
    phase     TEXT NOT NULL,
    text      TEXT NOT NULL,
    item_id   TEXT,
    item_pack TEXT,
    PRIMARY KEY (chain_id, step_no)
);

CREATE TABLE fix (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    fix_id        TEXT NOT NULL,
    action        TEXT NOT NULL,
    effort        TEXT NOT NULL,
    chains_broken TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'done', 'deferred')),
    status_date   TEXT NOT NULL,
    status_actor  TEXT NOT NULL
);

CREATE TABLE fix_rubric (
    fix_pk  INTEGER NOT NULL REFERENCES fix (id),
    item_id TEXT NOT NULL,
    pack_id TEXT,
    PRIMARY KEY (fix_pk, item_id)
);

CREATE TABLE fix_status_history (
    id      INTEGER PRIMARY KEY,
    fix_pk  INTEGER NOT NULL REFERENCES fix (id),
    status  TEXT NOT NULL,
    date    TEXT NOT NULL,
    actor   TEXT NOT NULL
);

CREATE TABLE verify_next (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    seq           INTEGER NOT NULL,
    unknown_text  TEXT NOT NULL,
    why           TEXT NOT NULL,
    cheapest_check TEXT NOT NULL
);

CREATE TABLE packet_record (
    id             INTEGER PRIMARY KEY,
    engagement_id  INTEGER NOT NULL REFERENCES engagement (id),
    pack_id        TEXT NOT NULL,
    assembled_date TEXT NOT NULL,
    word_cap       INTEGER NOT NULL,
    byte_count     INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    posture        TEXT
);

CREATE TABLE model_run (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    packet_hash   TEXT NOT NULL,
    model_label   TEXT NOT NULL,
    run_date      TEXT NOT NULL,
    raw_output    TEXT NOT NULL
);

CREATE TABLE adjudication (
    id       INTEGER PRIMARY KEY,
    run_id   INTEGER NOT NULL REFERENCES model_run (id),
    section  TEXT NOT NULL,
    decision TEXT NOT NULL,
    note     TEXT,
    date     TEXT NOT NULL,
    actor    TEXT NOT NULL
);

CREATE TABLE probe_result (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    pack_id       TEXT NOT NULL,
    item_id       TEXT NOT NULL,
    method        TEXT NOT NULL,
    outcome       TEXT NOT NULL CHECK (outcome IN ('confirmed', 'failed', 'inconclusive')),
    date          TEXT NOT NULL,
    actor         TEXT NOT NULL,
    FOREIGN KEY (pack_id, item_id) REFERENCES rubric_item (pack_id, item_id)
);
"""

MODEL_PASS_SCHEMA = """
CREATE TABLE IF NOT EXISTS packet_record (
    id             INTEGER PRIMARY KEY,
    engagement_id  INTEGER NOT NULL REFERENCES engagement (id),
    pack_id        TEXT NOT NULL,
    assembled_date TEXT NOT NULL,
    word_cap       INTEGER NOT NULL,
    byte_count     INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    posture        TEXT
);

CREATE TABLE IF NOT EXISTS model_run (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    packet_hash   TEXT NOT NULL,
    model_label   TEXT NOT NULL,
    run_date      TEXT NOT NULL,
    raw_output    TEXT NOT NULL
);
"""
"""The slice-4 tables, created lazily by the model-pass store methods.

SCHEMA is applied only when a database is created, so a database built
by slices 1-3 has no packet_record or model_run table. The model-pass
methods create both with IF NOT EXISTS before touching them, which lets
an older database work with the slice-4 commands with no migration
step."""

ADJUDICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS adjudication (
    id       INTEGER PRIMARY KEY,
    run_id   INTEGER NOT NULL REFERENCES model_run (id),
    section  TEXT NOT NULL,
    decision TEXT NOT NULL,
    note     TEXT,
    date     TEXT NOT NULL,
    actor    TEXT NOT NULL
);
"""
"""The slice-5 table, created lazily by the adjudication store methods,
for the same reason as MODEL_PASS_SCHEMA: a database built by slices 1-4
has no adjudication table, and the slice-5 commands create it with
IF NOT EXISTS before touching it."""

PROBE_SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_result (
    id            INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagement (id),
    pack_id       TEXT NOT NULL,
    item_id       TEXT NOT NULL,
    method        TEXT NOT NULL,
    outcome       TEXT NOT NULL CHECK (outcome IN ('confirmed', 'failed', 'inconclusive')),
    date          TEXT NOT NULL,
    actor         TEXT NOT NULL,
    FOREIGN KEY (pack_id, item_id) REFERENCES rubric_item (pack_id, item_id)
);
"""
"""The Deeper Slice 3 table: behavioral verification probes, one row
per probe, append-only. SCHEMA carries it for new databases; an older
database gets it from record_probe, on the write path only. Reads never
create it: list_probes treats a missing table as no probes recorded."""


ADDED_COLUMNS = (
    ("fix_rubric", "pack_id", "TEXT"),
    ("chain", "control_pack", "TEXT"),
    ("engagement", "primary_pack", "TEXT"),
    ("packet_record", "posture", "TEXT"),
    ("chain_step", "item_id", "TEXT"),
    ("chain_step", "item_pack", "TEXT"),
)
"""Columns added after a table first shipped. 0.3.4: the pack each
rubric citation was validated against (fix_rubric.pack_id,
chain.control_pack); NULL means the citation was recorded before
0.3.4. After 0.4.0: the engagement's primary pack
(engagement.primary_pack); NULL means none is recorded, and
default_pack_id falls back to the alphabetically-first loaded pack.
Deeper Slice 1: the posture a packet was assembled under
(packet_record.posture, 'standard' or 'adversarial'); NULL means the
packet was recorded before the column existed, and it reads as
'standard'. Deeper Slice 4a: the rubric item a chain step exercises
and the pack it was validated against (chain_step.item_id,
chain_step.item_pack), both NULL or both set, as the chain head's
control_rubric / control_pack pair; NULL means the step names no item. MODEL_PASS_SCHEMA carries it as well, because a database
that predates the model-pass tables gets packet_record lazily, after
migrate has run. All are nullable. SCHEMA carries them for new databases;
Store.migrate adds them to a database that predates them, so both
routes end at the same schema. Migration is lazy (0.3.5): opening a
database never writes to it; the first write through a Store
migrates first."""


class InvariantError(ValueError):
    """Raised when a write would violate a method invariant."""


class Store:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Opening never writes (0.3.5). Record which ADDED_COLUMNS
        # columns are present — PRAGMA table_info, a read — so reads
        # can tolerate a database that predates them. True: present;
        # False: the table exists without the column (only migrate
        # adds it); None: the table does not exist yet (init_schema
        # will create it with the column), re-checked on use.
        self._added_columns = {
            (table, column): self._probe_column(table, column)
            for table, column, _decl in ADDED_COLUMNS
        }
        self._migrated = False

    def _probe_column(self, table, column):
        names = [
            row["name"] for row in self.conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        ]
        if not names:
            return None
        return column in names

    def _has_column(self, table, column):
        """Whether an ADDED_COLUMNS column is present. A read only."""
        present = self._added_columns[(table, column)]
        if present is None:
            present = self._probe_column(table, column)
            self._added_columns[(table, column)] = present
        return bool(present)

    def _ensure_migrated(self):
        """The write-path guard: every store method that writes calls
        this before its first write statement, so a database is
        migrated on the first write through a Store and never on a
        read. Runs migrate() at most once per Store instance."""
        if not self._migrated:
            self.migrate()
            self._migrated = True

    def migrate(self):
        """Bring an older database up to the current schema.

        Adds any ADDED_COLUMNS column the database lacks, then
        backfills the pack of every pre-0.3.4 citation whose pack is
        determined: a fix_rubric row (or a chain's control_rubric)
        with a NULL pack whose item occurs in exactly one loaded pack
        gets that pack. A citation of an item in no loaded pack, or
        in two or more, keeps its NULL — its original pack is
        unknowable, and the report's item lookup stays its fallback.

        Idempotent: it writes only when there is something to do,
        and a second run changes zero rows. It changes no other row
        and no other column. A table that does not exist yet (a
        database not yet initialised) is left for init_schema, whose
        SCHEMA already carries the columns. Returns the counts
        {"columns_added", "fix_rubric_backfilled", "chain_backfilled"}.
        """
        result = {
            "columns_added": 0,
            "fix_rubric_backfilled": 0,
            "chain_backfilled": 0,
        }
        for table, column, decl in ADDED_COLUMNS:
            present = self._probe_column(table, column)
            if present is False:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {decl}"
                )
                result["columns_added"] += 1
            self._added_columns[(table, column)] = (
                True if present is not None else None
            )
        if self._has_column("fix_rubric", "pack_id"):
            result["fix_rubric_backfilled"] = self._backfill(
                "fix_rubric", "item_id", "pack_id"
            )
        if self._has_column("chain", "control_pack"):
            result["chain_backfilled"] = self._backfill(
                "chain", "control_rubric", "control_pack"
            )
        if any(result.values()):
            self.conn.commit()
        return result

    # The items whose pack is determined: those in exactly one loaded
    # pack. MIN(pack_id) over such a group is that one pack.
    _SINGLE_PACK_ITEMS = (
        "SELECT item_id, MIN(pack_id) AS pack_id FROM rubric_item"
        " GROUP BY item_id HAVING COUNT(DISTINCT pack_id) = 1"
    )

    def _backfill(self, table, item_col, pack_col):
        """Fill pack_col for rows with a NULL pack whose item_col is in
        exactly one loaded pack. Counts first, so a run with nothing to
        fill issues no write at all. Returns the rows updated."""
        where = (
            f"{pack_col} IS NULL AND {item_col} IN"
            f" (SELECT item_id FROM ({self._SINGLE_PACK_ITEMS}))"
        )
        pending = self.conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}"
        ).fetchone()[0]
        if not pending:
            return 0
        cur = self.conn.execute(
            f"UPDATE {table} SET {pack_col} = ("
            f"SELECT s.pack_id FROM ({self._SINGLE_PACK_ITEMS}) AS s"
            f" WHERE s.item_id = {table}.{item_col}"
            f") WHERE {where}"
        )
        return cur.rowcount

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- engagement ------------------------------------------------------

    def create_engagement(self, name, subject_label, created_date, method_order):
        if method_order not in METHOD_ORDERS:
            raise InvariantError(f"method_order must be one of {METHOD_ORDERS}")
        self._ensure_migrated()
        cur = self.conn.execute(
            "INSERT INTO engagement (name, subject_label, created_date, method_order)"
            " VALUES (?, ?, ?, ?)",
            (name, subject_label, created_date, method_order),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_engagement(self):
        row = self.conn.execute("SELECT * FROM engagement LIMIT 1").fetchone()
        return dict(row) if row else None

    # -- inventory ---------------------------------------------------------

    def add_inventory_entry(self, engagement_id, entry_id, section, body, label,
                            source, checked_date=None, decay_date=None, *,
                            date, actor):
        if label not in EVIDENCE_LABELS:
            raise InvariantError(f"label must be one of {EVIDENCE_LABELS}")
        self._ensure_migrated()
        self.conn.execute(
            "INSERT INTO inventory_entry"
            " (entry_id, engagement_id, section, body, label, source, checked_date, decay_date)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, engagement_id, section, body, label, source,
             checked_date, decay_date),
        )
        self.conn.execute(
            "INSERT INTO entry_label_history (entry_id, label, date, actor)"
            " VALUES (?, ?, ?, ?)",
            (entry_id, label, date, actor),
        )
        self.conn.commit()

    def set_entry_label(self, entry_id, label, *, date, actor):
        """The only path that changes an evidence label. Explicit, dated, acted."""
        if label not in EVIDENCE_LABELS:
            raise InvariantError(f"label must be one of {EVIDENCE_LABELS}")
        self._ensure_migrated()
        self.conn.execute(
            "UPDATE inventory_entry SET label = ? WHERE entry_id = ?",
            (label, entry_id),
        )
        self.conn.execute(
            "INSERT INTO entry_label_history (entry_id, label, date, actor)"
            " VALUES (?, ?, ?, ?)",
            (entry_id, label, date, actor),
        )
        self.conn.commit()

    def update_entry_details(self, entry_id, *, body=None, source=None,
                             checked_date=UNSET, decay_date=UNSET):
        """Edit an entry's body, source, and dates. Never its label.

        body/source: None leaves the field unchanged (both columns are
        NOT NULL, so None is never a value to store). Dates use the UNSET
        sentinel: UNSET leaves the date unchanged, None clears it, a string
        sets it. This method never modifies the label column and never
        writes to entry_label_history; label changes go only through
        set_entry_label.
        """
        row = self.conn.execute(
            "SELECT entry_id FROM inventory_entry WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            raise InvariantError(f"no such entry: {entry_id}")
        assignments = []
        params = []
        if body is not None:
            assignments.append("body = ?")
            params.append(body)
        if source is not None:
            assignments.append("source = ?")
            params.append(source)
        if checked_date is not UNSET:
            assignments.append("checked_date = ?")
            params.append(checked_date)
        if decay_date is not UNSET:
            assignments.append("decay_date = ?")
            params.append(decay_date)
        if assignments:
            params.append(entry_id)
            self._ensure_migrated()
            self.conn.execute(
                "UPDATE inventory_entry SET " + ", ".join(assignments)
                + " WHERE entry_id = ?",
                params,
            )
            self.conn.commit()

    def next_entry_id(self, section):
        """Next free '<section><n>' inventory ID in a section (n from 1).

        Only existing IDs of exactly that shape count; other IDs in the
        section are left alone.
        """
        best = 0
        pattern = re.compile(re.escape(section) + r"(\d+)")
        for entry in self.list_inventory():
            if entry["section"] != section:
                continue
            m = pattern.fullmatch(entry["entry_id"])
            if m:
                best = max(best, int(m.group(1)))
        return f"{section}{best + 1}"

    def list_inventory(self):
        rows = self.conn.execute(
            "SELECT * FROM inventory_entry ORDER BY section, entry_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def inventory_label_counts(self):
        rows = self.conn.execute(
            "SELECT label, COUNT(*) AS n FROM inventory_entry GROUP BY label"
        ).fetchall()
        return {r["label"]: r["n"] for r in rows}

    # -- rubric packs ------------------------------------------------------

    def add_pack(self, pack):
        # Migrate (and backfill) before the new pack's items load, so
        # the backfill sees the packs the old citations were made
        # against.
        self._ensure_migrated()
        self.conn.execute(
            "INSERT INTO rubric_pack (pack_id, title, source_citation, version)"
            " VALUES (?, ?, ?, ?)",
            (pack["pack_id"], pack["title"], pack["source_citation"], pack["version"]),
        )
        for item in pack["items"]:
            self.conn.execute(
                "INSERT INTO rubric_item (pack_id, item_id, group_name, text)"
                " VALUES (?, ?, ?, ?)",
                (pack["pack_id"], item["item_id"], item["group"], item["text"]),
            )
        self.conn.commit()

    def get_pack(self, pack_id):
        row = self.conn.execute(
            "SELECT * FROM rubric_pack WHERE pack_id = ?", (pack_id,)
        ).fetchone()
        return dict(row) if row else None

    def default_pack_id(self):
        """The one pack default every command and page uses, or None.

        The engagement's recorded primary pack (primary_pack(), set
        by fixture loading or set_primary_pack) when one is recorded.
        Otherwise the alphabetically-first loaded pack: the ORDER BY
        guarantees it, whatever order SQLite would scan the table
        in. Never load order. A database with no recorded primary
        (one created before the primary pack existed, or by `new`)
        gets exactly the alphabetical default. A read only.
        """
        primary = self.primary_pack()
        if primary is not None:
            return primary
        row = self.conn.execute(
            "SELECT pack_id FROM rubric_pack ORDER BY pack_id LIMIT 1"
        ).fetchone()
        return row["pack_id"] if row else None

    def primary_pack(self):
        """The engagement's recorded primary pack, or None when none
        is recorded, the database predates the column, or the
        recorded id names no loaded pack. A read only."""
        if not self._has_column("engagement", "primary_pack"):
            return None
        row = self.conn.execute(
            "SELECT e.primary_pack FROM engagement AS e"
            " JOIN rubric_pack AS p ON p.pack_id = e.primary_pack"
            " ORDER BY e.id LIMIT 1"
        ).fetchone()
        return row["primary_pack"] if row else None

    def set_primary_pack(self, pack_id):
        """Record pack_id as the engagement's primary pack: the
        default for report, packet, pdf and rubric validation
        whenever no --pack is given. The pack must be loaded in this
        database, and the database must hold an engagement; either
        refusal raises InvariantError and writes nothing."""
        if self.get_pack(pack_id) is None:
            raise InvariantError(f"no such pack loaded: {pack_id}")
        eng = self.conn.execute(
            "SELECT id FROM engagement ORDER BY id LIMIT 1"
        ).fetchone()
        if eng is None:
            raise InvariantError("database holds no engagement")
        self._ensure_migrated()
        self.conn.execute(
            "UPDATE engagement SET primary_pack = ? WHERE id = ?",
            (pack_id, eng["id"]),
        )
        self.conn.commit()

    def list_packs(self):
        """All loaded packs, in load order (rowid). A listing only:
        defaults come from default_pack_id(), never from this order."""
        rows = self.conn.execute(
            "SELECT * FROM rubric_pack ORDER BY rowid"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_items(self, pack_id):
        rows = self.conn.execute(
            "SELECT * FROM rubric_item WHERE pack_id = ? ORDER BY item_id",
            (pack_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_pack_items(self, pack_id):
        """The pack's items in pack order (the order they were loaded)."""
        rows = self.conn.execute(
            "SELECT * FROM rubric_item WHERE pack_id = ? ORDER BY rowid",
            (pack_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- coverage ------------------------------------------------------------

    @staticmethod
    def _check_coverage(status, cited, na_reason):
        """The coverage invariants, checked before any write."""
        if status not in COVERAGE_STATUSES:
            raise InvariantError(f"status must be one of {COVERAGE_STATUSES}")
        if status == "Not applicable" and not (na_reason and na_reason.strip()):
            raise InvariantError(
                "Not applicable requires a non-empty N/A reason grounded in the inventory"
            )
        if not cited and status not in ("Unknown", "Not applicable"):
            raise InvariantError(
                "A coverage score with no cited inventory entries may only be "
                "saved as Unknown, or as Not applicable with an N/A reason"
            )

    def _insert_coverage(self, engagement_id, pack_id, item_id, status,
                         reasoning, cited, na_reason):
        """Insert a score and its citations. Caller checks the invariants
        first and owns the transaction (commit or rollback)."""
        cur = self.conn.execute(
            "INSERT INTO coverage_score"
            " (engagement_id, pack_id, item_id, status, reasoning, na_reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (engagement_id, pack_id, item_id, status, reasoning, na_reason),
        )
        score_id = cur.lastrowid
        for entry_id in cited:
            self.conn.execute(
                "INSERT INTO coverage_citation (score_id, entry_id) VALUES (?, ?)",
                (score_id, entry_id),
            )
        return score_id

    def save_coverage(self, engagement_id, pack_id, item_id, status, reasoning,
                      cited_entry_ids=(), na_reason=None):
        cited = list(cited_entry_ids or ())
        self._check_coverage(status, cited, na_reason)
        self._ensure_migrated()
        score_id = self._insert_coverage(
            engagement_id, pack_id, item_id, status, reasoning, cited, na_reason
        )
        self.conn.commit()
        return score_id

    def get_coverage(self, pack_id, item_id):
        """The score for one (pack, item), or None if it is not scored."""
        row = self.conn.execute(
            "SELECT cs.*, ri.group_name FROM coverage_score cs"
            " JOIN rubric_item ri ON ri.pack_id = cs.pack_id AND ri.item_id = cs.item_id"
            " WHERE cs.pack_id = ? AND cs.item_id = ?",
            (pack_id, item_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        cites = self.conn.execute(
            "SELECT entry_id FROM coverage_citation WHERE score_id = ? ORDER BY entry_id",
            (d["id"],),
        ).fetchall()
        d["cited_entry_ids"] = [c["entry_id"] for c in cites]
        return d

    def replace_coverage(self, engagement_id, pack_id, item_id, status,
                         reasoning, cited_entry_ids=(), na_reason=None):
        """Replace the existing score for (pack, item) with a new one.

        The invariants are checked before anything is touched, and the
        delete + insert run in one transaction: a failed replace (for
        example a citation naming a missing entry) leaves the old score
        intact. Returns (previous score dict, new score id). Raises
        InvariantError if the item has no score to replace.
        """
        cited = list(cited_entry_ids or ())
        self._check_coverage(status, cited, na_reason)
        old = self.get_coverage(pack_id, item_id)
        if old is None:
            raise InvariantError(
                f"no existing score for item {item_id} in pack {pack_id}"
            )
        self._ensure_migrated()
        try:
            self.conn.execute(
                "DELETE FROM coverage_citation WHERE score_id = ?", (old["id"],)
            )
            self.conn.execute(
                "DELETE FROM coverage_score WHERE id = ?", (old["id"],)
            )
            new_id = self._insert_coverage(
                engagement_id, pack_id, item_id, status, reasoning,
                cited, na_reason,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return old, new_id

    def list_coverage(self, pack_id):
        rows = self.conn.execute(
            "SELECT cs.*, ri.group_name FROM coverage_score cs"
            " JOIN rubric_item ri ON ri.pack_id = cs.pack_id AND ri.item_id = cs.item_id"
            " WHERE cs.pack_id = ? ORDER BY cs.item_id",
            (pack_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            cites = self.conn.execute(
                "SELECT entry_id FROM coverage_citation WHERE score_id = ? ORDER BY entry_id",
                (d["id"],),
            ).fetchall()
            d["cited_entry_ids"] = [c["entry_id"] for c in cites]
            out.append(d)
        return out

    def coverage_tallies(self, pack_id):
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM coverage_score"
            " WHERE pack_id = ? GROUP BY status",
            (pack_id,),
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # -- chains ----------------------------------------------------------------

    def add_chain(self, engagement_id, chain_key, name, steps,
                  earliest_control, control_status, control_rubric=None,
                  *, control_pack=None):
        """control_pack is the pack control_rubric was validated
        against; a chain that cites a rubric item must carry it."""
        if control_rubric is not None and control_pack is None:
            raise InvariantError("control_rubric requires control_pack")
        # A step may name the rubric item it exercises, with the pack it
        # was validated against: both or neither, checked for every step
        # before anything writes.
        for i, step in enumerate(steps, start=1):
            self._check_step_item(i, step.get("item_id"), step.get("item_pack"))
        self._ensure_migrated()
        cur = self.conn.execute(
            "INSERT INTO chain"
            " (engagement_id, chain_key, name, earliest_control, control_rubric,"
            " control_status, control_pack)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (engagement_id, chain_key, name, earliest_control,
             control_rubric, control_status, control_pack),
        )
        chain_pk = cur.lastrowid
        for i, step in enumerate(steps, start=1):
            self.conn.execute(
                "INSERT INTO chain_step"
                " (chain_id, step_no, phase, text, item_id, item_pack)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (chain_pk, i, step["phase"], step["text"],
                 step.get("item_id"), step.get("item_pack")),
            )
        self.conn.commit()
        return chain_pk

    @staticmethod
    def _check_step_item(step_no, item_id, item_pack):
        """The chain-step pairing invariant, the head's shape: a step
        item requires its pack, and a pack requires an item."""
        if item_id is not None and item_pack is None:
            raise InvariantError(
                f"step {step_no}: a step item requires its item_pack"
            )
        if item_pack is not None and item_id is None:
            raise InvariantError(
                f"step {step_no}: item_pack requires a step item"
            )

    def set_chain_step_item(self, chain_key, step_no, item_id, item_pack):
        """Name (or, with both None, clear) the rubric item one step of
        an existing chain exercises. Refuses — before any write — the
        pairing violation, an unknown chain, a step the chain does not
        have, and an item not in item_pack. Returns the step's previous
        (item_id, item_pack)."""
        self._check_step_item(step_no, item_id, item_pack)
        chains = self.conn.execute(
            "SELECT id FROM chain WHERE chain_key = ?", (chain_key,)
        ).fetchall()
        if not chains:
            raise InvariantError(f"no such chain: {chain_key}")
        if len(chains) > 1:
            raise InvariantError(f"chain key is not unique: {chain_key}")
        chain_pk = chains[0]["id"]
        step = self.conn.execute(
            "SELECT * FROM chain_step WHERE chain_id = ? AND step_no = ?",
            (chain_pk, step_no),
        ).fetchone()
        if step is None:
            raise InvariantError(f"chain {chain_key} has no step {step_no}")
        if item_id is not None:
            if self.get_pack(item_pack) is None:
                raise InvariantError(f"no such pack: {item_pack}")
            if item_id not in {i["item_id"] for i in self.list_items(item_pack)}:
                raise InvariantError(
                    f"no such item in pack {item_pack}: {item_id}"
                )
        step = dict(step)
        previous = (step.get("item_id"), step.get("item_pack"))
        self._ensure_migrated()
        self.conn.execute(
            "UPDATE chain_step SET item_id = ?, item_pack = ?"
            " WHERE chain_id = ? AND step_no = ?",
            (item_id, item_pack, chain_pk, step_no),
        )
        self.conn.commit()
        return previous

    def list_chains(self):
        rows = self.conn.execute("SELECT * FROM chain ORDER BY chain_key").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            steps = self.conn.execute(
                "SELECT * FROM chain_step WHERE chain_id = ? ORDER BY step_no",
                (d["id"],),
            ).fetchall()
            d["steps"] = [dict(s) for s in steps]
            out.append(d)
        return out

    # -- fixes -------------------------------------------------------------------

    def add_fix(self, engagement_id, fix_id, action, effort, chains_broken,
                rubric_item_ids=(), *, status, status_date, status_actor,
                rubric_pack_id=None):
        """rubric_pack_id is the pack the rubric items were validated
        against; a fix that cites rubric items must carry it."""
        if status not in FIX_STATUSES:
            raise InvariantError(f"status must be one of {FIX_STATUSES}")
        if rubric_item_ids and rubric_pack_id is None:
            raise InvariantError("rubric items require rubric_pack_id")
        self._ensure_migrated()
        cur = self.conn.execute(
            "INSERT INTO fix"
            " (engagement_id, fix_id, action, effort, chains_broken, status, status_date, status_actor)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (engagement_id, fix_id, action, effort, chains_broken,
             status, status_date, status_actor),
        )
        fix_pk = cur.lastrowid
        for item_id in rubric_item_ids or ():
            self.conn.execute(
                "INSERT INTO fix_rubric (fix_pk, item_id, pack_id)"
                " VALUES (?, ?, ?)",
                (fix_pk, item_id, rubric_pack_id),
            )
        self.conn.execute(
            "INSERT INTO fix_status_history (fix_pk, status, date, actor)"
            " VALUES (?, ?, ?, ?)",
            (fix_pk, status, status_date, status_actor),
        )
        self.conn.commit()
        return fix_pk

    def set_fix_status(self, fix_id, status, *, date, actor):
        """The only path that changes a fix status. Explicit, dated, acted."""
        if status not in FIX_STATUSES:
            raise InvariantError(f"status must be one of {FIX_STATUSES}")
        row = self.conn.execute(
            "SELECT id, status FROM fix WHERE fix_id = ?", (fix_id,)
        ).fetchone()
        if row is None:
            raise InvariantError(f"no such fix: {fix_id}")
        if row["status"] == status:
            raise InvariantError(f"fix {fix_id} is already {status}")
        self._ensure_migrated()
        self.conn.execute(
            "UPDATE fix SET status = ?, status_date = ?, status_actor = ? WHERE id = ?",
            (status, date, actor, row["id"]),
        )
        self.conn.execute(
            "INSERT INTO fix_status_history (fix_pk, status, date, actor)"
            " VALUES (?, ?, ?, ?)",
            (row["id"], status, date, actor),
        )
        self.conn.commit()

    def list_fixes(self):
        rows = self.conn.execute("SELECT * FROM fix ORDER BY id").fetchall()
        # A database opened before its first write may predate the
        # pack_id column (opening never migrates): read NULL for it.
        pack_col = (
            "pack_id" if self._has_column("fix_rubric", "pack_id")
            else "NULL AS pack_id"
        )
        out = []
        for r in rows:
            d = dict(r)
            cites = self.conn.execute(
                f"SELECT item_id, {pack_col} FROM fix_rubric"
                " WHERE fix_pk = ? ORDER BY item_id",
                (d["id"],),
            ).fetchall()
            d["rubric_item_ids"] = [c["item_id"] for c in cites]
            # The pack each citation was validated against; None for
            # a citation recorded before 0.3.4.
            d["rubric_item_packs"] = {
                c["item_id"]: c["pack_id"] for c in cites
            }
            out.append(d)
        return out

    def list_fix_status_history(self, fix_id):
        """Every recorded status of one fix, oldest first: a list of
        {status, date, actor} dicts ordered by fix_status_history.id,
        and [] for an unknown fix_id. A read only."""
        rows = self.conn.execute(
            "SELECT h.status, h.date, h.actor FROM fix_status_history AS h"
            " JOIN fix AS f ON f.id = h.fix_pk"
            " WHERE f.fix_id = ? ORDER BY h.id",
            (fix_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def fix_status_counts(self):
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM fix GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # -- verify-next ---------------------------------------------------------------

    def add_verify_next(self, engagement_id, seq, unknown_text, why, cheapest_check):
        seq = _verify_next_seq(seq)
        self._ensure_migrated()
        self.conn.execute(
            "INSERT INTO verify_next (engagement_id, seq, unknown_text, why, cheapest_check)"
            " VALUES (?, ?, ?, ?, ?)",
            (engagement_id, seq, unknown_text, why, cheapest_check),
        )
        self.conn.commit()

    def list_verify_next(self):
        rows = self.conn.execute(
            "SELECT * FROM verify_next ORDER BY seq"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- model pass: packets and runs --------------------------------------

    def _ensure_model_pass_tables(self):
        """Create the slice-4 tables if this database predates them."""
        self.conn.executescript(MODEL_PASS_SCHEMA)
        self.conn.commit()

    def record_packet(self, engagement_id, pack_id, assembled_date,
                      word_cap, byte_count, sha256, posture="standard"):
        """Record one assembled packet's hash, with the posture it was
        assembled under (PACKET_POSTURES)."""
        if posture not in PACKET_POSTURES:
            raise InvariantError(f"unknown packet posture: {posture}")
        self._ensure_migrated()
        self._ensure_model_pass_tables()
        cur = self.conn.execute(
            "INSERT INTO packet_record"
            " (engagement_id, pack_id, assembled_date, word_cap, byte_count,"
            " sha256, posture)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (engagement_id, pack_id, assembled_date, word_cap,
             byte_count, sha256, posture),
        )
        self.conn.commit()
        return cur.lastrowid

    @staticmethod
    def _packet_dict(row):
        """A packet_record row as a dict. A record from before the
        posture column (the column absent, or NULL) reads as
        'standard'."""
        d = dict(row)
        d["posture"] = d.get("posture") or "standard"
        return d

    def get_packet_by_hash(self, sha256):
        """The recorded packet with this SHA-256, or None."""
        self._ensure_model_pass_tables()
        row = self.conn.execute(
            "SELECT * FROM packet_record WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return self._packet_dict(row) if row else None

    def list_packets(self):
        self._ensure_model_pass_tables()
        rows = self.conn.execute(
            "SELECT * FROM packet_record ORDER BY id"
        ).fetchall()
        return [self._packet_dict(r) for r in rows]

    def record_run(self, engagement_id, packet_hash, model_label,
                   run_date, raw_output):
        """Store one model run's output verbatim, answering a packet.

        Recording a run writes only to model_run: it creates and modifies
        no coverage scores, chains, fixes, or verify-next items. Parsing
        the output into the record is adjudication's work (slice 5).
        """
        self._ensure_migrated()
        self._ensure_model_pass_tables()
        cur = self.conn.execute(
            "INSERT INTO model_run"
            " (engagement_id, packet_hash, model_label, run_date, raw_output)"
            " VALUES (?, ?, ?, ?, ?)",
            (engagement_id, packet_hash, model_label, run_date, raw_output),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_run(self, run_id):
        """One stored model run (with its raw output), or None."""
        self._ensure_model_pass_tables()
        row = self.conn.execute(
            "SELECT * FROM model_run WHERE id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_runs(self):
        self._ensure_model_pass_tables()
        rows = self.conn.execute(
            "SELECT * FROM model_run ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- adjudication --------------------------------------------------------

    def _ensure_adjudication_table(self):
        """Create the slice-5 table if this database predates it."""
        self.conn.executescript(ADJUDICATION_SCHEMA)
        self.conn.commit()

    def record_adjudication(self, run_id, section, decision, note,
                            date, actor):
        """Append one adjudication decision event for a model run.

        Events are append-only: adjudicating a section again adds a new
        event, and the section's current standing is its latest event —
        nothing is overwritten, so a changed mind is part of the record,
        exactly as a correction is. Recording a decision changes nothing
        else in the record; applying an accepted or corrected deliverable
        is the operator's separate explicit commands.
        """
        if section not in ADJUDICATION_SECTIONS:
            raise InvariantError(
                f"section must be one of {ADJUDICATION_SECTIONS}"
            )
        if decision not in ADJUDICATION_DECISIONS:
            raise InvariantError(
                f"decision must be one of {ADJUDICATION_DECISIONS}"
            )
        self._ensure_migrated()
        self._ensure_adjudication_table()
        cur = self.conn.execute(
            "INSERT INTO adjudication"
            " (run_id, section, decision, note, date, actor)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, section, decision, note, date, actor),
        )
        self.conn.commit()
        return cur.lastrowid

    # -- behavioral verification probes ------------------------------------

    def record_probe(self, engagement_id, pack_id, item_id, method,
                     outcome, date, actor):
        """Append one behavioral probe of a rubric item.

        Append-only, like adjudication events: a probe is never edited
        or deleted, and an item's current probe standing is its latest
        record. Recording a probe changes nothing else — no score moves;
        acting on a failed probe is the operator's separate rescore.
        Every refusal (an outcome outside PROBE_OUTCOMES, an unknown
        pack, an item not in the pack, an empty method) happens before
        the first write.
        """
        if outcome not in PROBE_OUTCOMES:
            raise InvariantError(f"outcome must be one of {PROBE_OUTCOMES}")
        if not method or not method.strip():
            raise InvariantError("a probe needs a method: what was done")
        if self.get_pack(pack_id) is None:
            raise InvariantError(f"no such pack: {pack_id}")
        if item_id not in {i["item_id"] for i in self.list_items(pack_id)}:
            raise InvariantError(f"no such item in pack {pack_id}: {item_id}")
        self._ensure_migrated()
        self.conn.executescript(PROBE_SCHEMA)
        cur = self.conn.execute(
            "INSERT INTO probe_result"
            " (engagement_id, pack_id, item_id, method, outcome, date, actor)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (engagement_id, pack_id, item_id, method, outcome, date, actor),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_probes(self, pack_id):
        """Every probe recorded for a pack, ordered by item, then date,
        then record order. A read only: a database from before the
        probe_result table has no probes, and the table is not created."""
        present = self.conn.execute(
            "SELECT 1 FROM sqlite_master"
            " WHERE type = 'table' AND name = 'probe_result'"
        ).fetchone()
        if present is None:
            return []
        rows = self.conn.execute(
            "SELECT * FROM probe_result WHERE pack_id = ?"
            " ORDER BY item_id, date, id",
            (pack_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_adjudications(self, run_id):
        """Every adjudication event recorded for a run, in record order."""
        self._ensure_adjudication_table()
        rows = self.conn.execute(
            "SELECT * FROM adjudication WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
