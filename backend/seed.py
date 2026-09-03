"""Seed test data — run once: python seed.py"""
import pyodbc

cs = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=209.15.116.56,1433;"
    "DATABASE=@KlongThom_Sales;"
    "UID=JCAT;PWD=SKIN7646;"
    "TrustServerCertificate=yes;Encrypt=yes;"
)
conn = pyodbc.connect(cs)
conn.autocommit = True
cur = conn.cursor()

# clear existing test data
cur.execute("DELETE FROM [mod7$_Personnel]")
cur.execute("DELETE FROM [mod7$_Store]")

# stores
stores = [
    ('A1', 'กอล์ฟ',       'retail'),
    ('A2', 'นิ่ม (เพลง)', 'retail'),
    ('A3', 'ต่อ',          'retail'),
]
for code, name, stype in stores:
    cur.execute("INSERT INTO [mod7$_Store](s7Code,s7Name,s7Type,s7Status) VALUES(?,?,?,1)", code, name, stype)
print("Stores inserted")

# get s7Sid for A1
cur.execute("SELECT s7Sid FROM [mod7$_Store] WHERE s7Code='A1'")
sid_a1 = cur.fetchone()[0]
cur.execute("SELECT s7Sid FROM [mod7$_Store] WHERE s7Code='A2'")
sid_a2 = cur.fetchone()[0]

# personnel (LINE_TEST_001 for dev login)
persons = [
    (sid_a1, 'EMP001', 'LINE_TEST_001', 'hash', 'สมชาย', 'ใจดี',  'staff'),
    (sid_a1, 'EMP002', 'LINE_TEST_002', 'hash', 'วันดี',  'ศรีสุข','staff'),
    (sid_a2, 'EMP003', 'LINE_TEST_ADMIN', 'hash', 'อรทัย', 'จัดการ', 'admin'),
]
for sid, code, user, pwd, fname, lname, role in persons:
    cur.execute(
        "INSERT INTO [mod7$_Personnel](p7Sid,p7EmpCode,p7User,p7PwdHash,p7FName,p7LName,p7Role,p7Status) VALUES(?,?,?,?,?,?,?,1)",
        sid, code, user, pwd, fname, lname, role
    )
print("Personnel inserted")

cur.execute("SELECT p7PID, p7FName, p7LName, p7Role FROM [mod7$_Personnel]")
for r in cur.fetchall():
    print(f"  p7PID={r[0]}  {r[1]} {r[2]}  ({r[3]})")

conn.close()
print("Done")
