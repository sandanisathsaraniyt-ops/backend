from database import get_db_connection
from werkzeug.security import generate_password_hash

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO responsible_adult (email, password)
    VALUES (?, ?)
""", ("test@gmail.com", "Password1"))

conn.commit()
conn.close()

print("Test user inserted")

