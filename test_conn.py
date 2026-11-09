from dotenv import load_dotenv
import os
import pyodbc
load_dotenv()
conn_str = os.getenv("SQL_CONNECTION_STRING")
print("String leído:", conn_str)

try:
    conn = pyodbc.connect(conn_str, timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION")
    print("Conexión OK. Versión de SQL Server:")
    print(cursor.fetchone()[0])
    conn.close()
except Exception as e:
    print("Error de conexión:", e)