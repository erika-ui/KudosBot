import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI") 

if not MONGO_URI:
    print("❌ Error: No tengo la MONGO_URI")
    exit()

print("⏳ Conectando a la base de datos...")
try:
    # Conexión
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client.get_database("kudos_db")
    collection = db.transacciones
    
    # Verificar cuántos hay antes de borrar
    cantidad = collection.count_documents({})
    print(f"📉 Se encontraron {cantidad} registros de prueba.")
    
    if cantidad == 0:
        print("✅ La base de datos ya está vacía.")
    else:
        confirmacion = input("⚠️ ¿Estás seguro de borrar TODO el historial? (escribe 'si'): ")
        
        if confirmacion.lower() == "si":
            # --- AQUÍ OCURRE EL BORRADO ---
            collection.delete_many({}) 
            print("🗑️ ¡Registros eliminados correctamente!")
            print("✨ La base de datos está lista para producción (0 kudos).")
        else:
            print("🚫 Operación cancelada.")

except Exception as e:
    print(f"❌ Error: {e}")