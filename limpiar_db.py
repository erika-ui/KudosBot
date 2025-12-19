import certifi
from pymongo import MongoClient

# --- PEGA AQUÍ TU URL DIRECTAMENTE ---
# Asegúrate de reemplazar <password> por tu contraseña real
MONGO_URI = "mongodb+srv://erika_db_user:lOvgbL6Fu6rq9zlQ@cluster0.rdurzcx.mongodb.net/?retryWrites=true&w=majority"

print("⏳ Conectando a la base de datos...")

try:
    # Conexión directa
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client.get_database("kudos_db")
    collection = db.transacciones
    
    # Verificar cuántos hay antes de borrar
    cantidad = collection.count_documents({})
    print(f"📉 Se encontraron {cantidad} registros de prueba.")
    
    if cantidad == 0:
        print("✅ La base de datos ya está vacía.")
    else:
        # Pregunta de seguridad
        confirmacion = input("⚠️ ¿Estás seguro de borrar TODO el historial? (escribe 'si'): ")
        
        if confirmacion.lower() == "si":
            collection.delete_many({}) 
            print("🗑️ ¡Registros eliminados correctamente!")
            print("✨ La base de datos está lista para producción (0 kudos).")
        else:
            print("🚫 Operación cancelada.")

except Exception as e:
    print(f"❌ Error de conexión: {e}")
    print("Consejo: Verifica que tu usuario y contraseña en la URL sean correctos.")