import datetime
import sqlite3

DB_NAME = "routeguard.db"

# Master coordinate lookup for key Chitral corridors & passes
LOCATION_COORDS = {
    "lowari tunnel": [35.3524, 71.7869],
    "lowari tunnel north portal": [35.3524, 71.7869],
    "lowari tunnel south portal": [35.3175, 71.7942],
    "kuragh": [36.0353, 72.0831],
    "shandur": [36.0853, 72.5481],
    "shandur top": [36.0853, 72.5481],
    "shandur pass": [36.0853, 72.5481],
    "drosh": [35.5592, 71.7961],
    "booni": [36.2731, 72.0883],
    "chitral town": [35.8510, 71.7869],
    "garam chashma": [36.0234, 71.5302],
    "mastuj": [36.2825, 72.5113],
    "ayun": [35.6882, 71.7821],
    "bumburet": [35.6811, 71.6667],
}

DEFAULT_COORDS = [35.8510, 71.7869]  # Default Chitral Center


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS route_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            status TEXT NOT NULL,
            cause TEXT,
            severity TEXT,
            estimated_clearance TEXT,
            summary_urdu TEXT,
            reporter_phone TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM route_reports")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            (
                "Lowari Tunnel North Portal",
                "BLOCKED",
                "Snow",
                "HIGH",
                "4 Hours",
                "لواری ٹنل نارتھ پورٹل کے قریب شدید برف باری کی وجہ سے راستہ مکمل طور پر بند ہے، کلیئرنس میں 4 گھنٹے لگ سکتے ہیں۔",
                "+923000000001",
                "2026-09-26 08:30:00",
            ),
            (
                "Kuragh",
                "ONE_WAY",
                "Landslide",
                "MEDIUM",
                "2 Hours",
                "کورغ کے مقام پر ملبہ ہٹانے کا کام جاری ہے، سڑک ایک طرفہ ٹریفک کے لیے کھلی ہے۔",
                "+923000000002",
                "2026-09-26 09:15:00",
            ),
            (
                "Shandur Top",
                "CLEAR",
                "Clear",
                "LOW",
                "Operational",
                "شندور ٹاپ پر موسم صاف ہے اور سڑک تمام ہلکی گاڑیوں کے لیے مکمل طور پر کھلی ہے۔",
                "+923000000003",
                "2026-09-26 10:00:00",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO route_reports 
            (location, status, cause, severity, estimated_clearance, summary_urdu, reporter_phone, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            seed_data,
        )

    conn.commit()
    conn.close()


def get_all_reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM route_reports ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_report(data: dict, reporter_phone: str = "Anonymous") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO route_reports 
        (location, status, cause, severity, estimated_clearance, summary_urdu, reporter_phone, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            data.get("location", "Unknown Location"),
            data.get("status", "HAZARD"),
            data.get("cause", "Unspecified"),
            data.get("severity", "MEDIUM"),
            data.get("estimated_clearance", "Unknown"),
            data.get("summary_urdu", ""),
            reporter_phone,
            now_str,
        ),
    )

    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id


def get_coords_for_location(location_name: str) -> list:
    """Fuzzy matching coordinate resolution for standard Chitral locations."""
    loc_clean = location_name.strip().lower()

    for key, coords in LOCATION_COORDS.items():
        if key in loc_clean or loc_clean in key:
            return coords

    return DEFAULT_COORDS