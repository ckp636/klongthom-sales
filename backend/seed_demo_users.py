"""Give the sample personnel a username + password for dev and staff training.

    python seed_demo_users.py              # password demo1234
    python seed_demo_users.py <password>   # another password

EMP001…EMP011 → staff01…staff11 named สตาฟ หนึ่ง…สตาฟ สิบเอ็ด,
ADM001 → admin01 named แอดมิน หนึ่ง. Re-running resets names and passwords.
Accounts only work where PASSWORD_LOGIN_ENABLED=true.
"""
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.personnel import Personnel
from app.schemas.log import LogCreate
from app.services import log_service
from app.services.security import hash_password

password = sys.argv[1] if len(sys.argv) > 1 else "demo1234"
THAI_NUMBERS = ["หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า", "สิบ", "สิบเอ็ด"]
# emp code → (username, first name, last name)
accounts = {f"EMP{i:03d}": (f"staff{i:02d}", "สตาฟ", THAI_NUMBERS[i - 1]) for i in range(1, 12)}
accounts["ADM001"] = ("admin01", "แอดมิน", "หนึ่ง")

with SessionLocal() as db, db.begin():
    people = db.execute(select(Personnel).where(Personnel.p7EmpCode.in_(accounts))).scalars().all()
    for person in sorted(people, key=lambda p: p.p7EmpCode):
        old = {"p7FName": person.p7FName, "p7LName": person.p7LName, "p7User": person.p7User}
        person.p7User, person.p7FName, person.p7LName = accounts[person.p7EmpCode]
        person.p7Nick = None
        person.p7PwdHash = hash_password(password)
        log_service.write(db, LogCreate(
            l9Type="audit", l9Module="personnel", l9Action="set_demo_login",
            l9Page="seed_demo_users.py", l9Pid=person.p7PID, l9Sid=person.p7Sid,
            l9RefTable="mod7$_Personnel", l9RefID=person.p7PID, l9OldVal=old,
            l9NewVal={"p7FName": person.p7FName, "p7LName": person.p7LName, "p7User": person.p7User},
        ))
        print(f"{person.p7User:8s} {person.p7Role:6s} {person.p7FName} {person.p7LName}".rstrip())
    print(f"{len(people)} accounts, password: {password}")
