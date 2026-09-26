import datetime
import sqlite3

DB_NAME = "routeguard.db"

# Coordinate mapping for key Chitral locations
LOCATION_COORDS = {
    "Lowari Tunnel": (35.3536, 71.8021),
    "Lowari Tunnel North Portal": (35.3536, 71.8021),
    "Drosh": (35.5589, 71.7964),
    "Chitral Town": (35.8510, 71.7869),
    "Kuragh Point (Booni Road)": (36.0353, 72.0838),
    "Kuragh": (36.0353, 72.0838),
    "Booni": (36.2711, 72.0886),
    "Mastuj": (36.2794, 72.5161),
    "Shandur Top": (36.0853, 72.5481),
    "Shandur Pass": (36.0853, 72.5481),
}


def get_coords_for_location(location_name: str) -> tuple:
    """Matches a location string to latitude/longitude coordinates."""
    for key, coords in LOCATION_COORDS.items():
        if key.lower() in location_name.lower():
            return coords
    # Default to central Chitral if location is unspecified
    return (35.8510, 71.7869)


def init_db():
    """Initializes the SQLite database with required tables and seed data."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            status TEXT NOT NULL,
            cause TEXT NOT NULL,
            severity TEXT NOT NULL,
            estimated_clearance TEXT,
            summary_urdu TEXT,
            reporter_phone TEXT DEFAULT 'Anonymous',
            is_verified INTEGER DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM reports")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            (
                "Lowari Tunnel North Portal",
                "CLEAR",
                "Clear",
                "LOW",
                "Operational",
                "لواری ٹنل پر ٹریفک کی آمد و رفت معمول کے مطابق جاری ہے۔",
                "+923001234567",
                1,
            ),
            (
                "Kuragh Point (Booni Road)",
                "BLOCKED",
                "Landslide",
                "HIGH",
                "2 to 3 hours",
                "کورغ کے مقام پر شدید لینڈ سلائیڈنگ کی وجہ سے سڑک دونوں طرف سے بند ہے۔",
                "+923009876543",
                1,
            ),
            (
                "Shandur Top",
                "ONE_WAY",
                "Snow",
                "MEDIUM",
                "1 hour",
                "شندور ٹاپ پر سڑک سے برف ہٹائی جا رہی ہے، ایک طرفہ ٹریفک جاری ہے۔",
                "+923005551234",
                1,
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO reports (location, status, cause, severity, estimated_clearance, summary_urdu, reporter_phone, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            seed_data,
        )

    conn.commit()
    conn.close()


def add_report(report_dict: dict, reporter_phone: str = "Anonymous"):
    """Inserts a new report into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO reports (location, status, cause, severity, estimated_clearance, summary_urdu, reporter_phone, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            report_dict.get("location", "Unknown Location"),
            report_dict.get("status", "HAZARD"),
            report_dict.get("cause", "Unspecified"),
            report_dict.get("severity", "MEDIUM"),
            report_dict.get("estimated_clearance", "Unknown"),
            report_dict.get("summary_urdu", ""),
            reporter_phone,
            1,
        ),
    )

    conn.commit()
    conn.close()


def get_all_reports():
    """Fetches all verified reports ordered by latest first."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM reports WHERE is_verified = 1 ORDER BY timestamp DESC"
    )
    rows = cursor.fetchall()

    reports = [dict(row) for row in rows]
    conn.close()
    return reports


if __name__ == "__main__":
    init_db()
    print("✅ Database updated with location coordinates!")