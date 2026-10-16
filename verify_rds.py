import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
sql = """
SELECT 'clients' AS table_name, COUNT(*) AS row_count FROM clients
UNION ALL SELECT 'projects', COUNT(*) FROM projects
UNION ALL SELECT 'consultants', COUNT(*) FROM consultants
UNION ALL SELECT 'invoices', COUNT(*) FROM invoices
"""
connection = psycopg2.connect(
    host=os.environ["RDS_HOST"],
    port=os.getenv("RDS_PORT", "5432"),
    dbname=os.environ["RDS_DATABASE"],
    user=os.environ["RDS_USER"],
    password=os.environ["RDS_PASSWORD"],
)
try:
    with connection.cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            print(f"{row[0]}: {row[1]}")
finally:
    connection.close()
