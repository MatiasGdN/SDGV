import sqlite3

conexion = sqlite3.connect("gestor_deventas.db")
cursor = conexion.cursor()

# Convertir cualquier CUIT vacío, con texto 'None' o 'null' a NULL real
cursor.execute("UPDATE clientes SET cuit = NULL WHERE cuit = '' OR TRIM(cuit) = '' OR cuit = 'None' OR cuit = 'null';")

conexion.commit()
conexion.close()

print("Base de datos saneada correctamente.")
