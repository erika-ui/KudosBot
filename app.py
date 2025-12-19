import os
import datetime
import random
import threading
import certifi
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pymongo import MongoClient

# --- CONFIGURACIÓN ---
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

CANAL_OFICIAL_KUDOS = "C0A1GB750BW" 
LIMITE_MENSUAL = 40 
IMAGEN_POR_DEFECTO = "https://a.slack-edge.com/80588/img/services/api_512.png"

app = App(token=SLACK_BOT_TOKEN)

# --- CONEXIÓN A MONGODB ---
if not MONGO_URI:
    print("❌ ERROR: No se encontró la variable MONGO_URI")
    exit(1)

# Agregamos tlsCAFile para Render (Corrección: quitado el doble 'client =')
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
db = client.get_database("kudos_db") 
collection = db.transacciones     

# --- FUNCIONES DE BASE DE DATOS ---
def guardar_transaccion(nueva_data):
    try:
        collection.insert_one(nueva_data)
        print("✅ Transacción guardada en Mongo")
        return True
    except Exception as e:
        print(f"❌ Error guardando en Mongo: {e}")
        return False

def cargar_transacciones():
    try:
        return list(collection.find({}, {"_id": 0}))
    except Exception as e:
        print(f"❌ Error leyendo Mongo: {e}")
        return []

def calcular_totales():
    historial = cargar_transacciones()
    totales = {}
    for t in historial:
        receptor = t["to"]
        totales[receptor] = totales.get(receptor, 0) + 1
    return totales

def obtener_info_usuario(user_id):
    try:
        result = app.client.users_info(user=user_id)
        user = result["user"]
        profile = user.get("profile", {})
        imagen = profile.get("image_48", IMAGEN_POR_DEFECTO)
        return {"name": user.get("real_name") or user.get("name"), "image": imagen}
    except:
        return {"name": "Usuario", "image": IMAGEN_POR_DEFECTO}

def generar_bloques_stats(user_id):
    now = datetime.datetime.now()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0).timestamp()
    mes_str = now.strftime("%B %Y")
    
    historial = cargar_transacciones()
    received_total, granted_month = 0, 0
    recent_history = []
    emojis = ["🚀", "🔥", "🤝", "💎", "🎯", "🌟"]

    for t in reversed(historial):
        if t["to"] == user_id:
            received_total += 1
            if len(recent_history) < 5:
                fecha_fmt = datetime.datetime.fromtimestamp(t["ts"]).strftime("%B %d")
                emoji = random.choice(emojis)
                linea = f"{emoji} *+1 kudos* {t['reason']} from <@{t['from']}> in <#{t.get('channel_id', 'general')}> on {fecha_fmt}"
                recent_history.append(linea)
        
        if t["from"] == user_id and t["ts"] >= inicio_mes:
            granted_month += 1

    disponible = max(0, LIMITE_MENSUAL - granted_month)

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "📊 Personal Stats", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"📅 *{mes_str}*"}]},
        {"type": "divider"},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Received:*\n{received_total}"},
            {"type": "mrkdwn", "text": f"*Granted:*\n{granted_month}"},
            {"type": "mrkdwn", "text": f"*Available:*\n{disponible}"},
            {"type": "mrkdwn", "text": f"*Limit:*\n{LIMITE_MENSUAL}/month"}
        ]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Recent History*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n\n".join(recent_history)}} if recent_history else {"type": "context", "elements": [{"type": "mrkdwn", "text": "No has recibido kudos recientemente."}]}
    ]

# --- INTERACCIONES ---

# 1. DAR KUDOS (Comando + Atajo)
@app.shortcut("dar_kudos_atajo") # <--- ESTE ID DEBE COINCIDIR EXACTAMENTE EN SLACK
@app.command("/dar-kudos")
def abrir_modal_kudos(ack, body, client):
    ack()
    
    modal_view = {
        "type": "modal",
        "callback_id": "kudos_modal_submission",
        "title": {"type": "plain_text", "text": "KudosBot", "emoji": True},
        "submit": {"type": "plain_text", "text": "Enviar", "emoji": True},
        "close": {"type": "plain_text", "text": "Cancelar", "emoji": True},
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "¡Vamos a reconocer el buen trabajo! ⭐"}},
            {"type": "input", "block_id": "receivers", "element": {"type": "multi_users_select", "placeholder": {"type": "plain_text", "text": "Selecciona compañeros"}, "action_id": "id"}, "label": {"type": "plain_text", "text": "¿A quién agradeces? 👥"}},
            {"type": "input", "block_id": "custom", "element": {"type": "plain_text_input", "multiline": True, "action_id": "message"}, "label": {"type": "plain_text", "text": "Tu mensaje de agradecimiento 🖊️"}}
        ]
    }   
    try:
        client.views_open(trigger_id=body["trigger_id"], view=modal_view)
    except Exception as e:
        print(f"❌ Error abriendo modal: {e}")

@app.view("kudos_modal_submission")
def manejar_envio_modal(ack, body, view, client):
    ack()
    user_origen = body["user"]["id"]
    valores = view["state"]["values"]
    lista_usuarios = valores["receivers"]["id"]["selected_users"]
    mensaje = valores["custom"]["message"]["value"]
    
    nombres_receptores = [] 
    timestamp = datetime.datetime.now().timestamp()
    fecha_str = datetime.datetime.now().strftime("%Y-%m-%d")

    for usuario_destino in lista_usuarios:
        if usuario_destino == user_origen: continue
        transaccion = {
            "from": user_origen, "to": usuario_destino, "reason": mensaje,
            "date": fecha_str, "ts": timestamp, "channel_id": CANAL_OFICIAL_KUDOS
        }
        guardar_transaccion(transaccion)
        nombres_receptores.append(f"<@{usuario_destino}>")

    if not nombres_receptores:
        client.chat_postEphemeral(channel=user_origen, user=user_origen, text="🚫 No puedes darte puntos a ti mismo.")
        return

    client.chat_postMessage(channel=CANAL_OFICIAL_KUDOS, blocks=[
        {"type": "section", "fields": [{"type": "mrkdwn", "text": f"🏅 *{', '.join(nombres_receptores)}*"}, {"type": "mrkdwn", "text": "*+1*"}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f" <@{user_origen}> _{mensaje}_"}}
    ], text="¡Nuevos Kudos!")

# 2. LEADERBOARD
@app.shortcut("leaderboard")
@app.command("/leaderboard")
def mostrar_leaderboard(ack, body, client):
    ack()
    
    user_id = body.get("user_id") or body.get("user", {}).get("id")
    channel_id = body.get("channel_id")
    
    totales = calcular_totales()
    if not totales:
        msg = "Aún no hay puntos. ¡Sé el primero en dar kudos! 🚀"
        if channel_id:
            client.chat_postMessage(channel=channel_id, text=msg)
        else:
            client.chat_postMessage(channel=user_id, text=msg)
        return
    
    sorted_db = sorted(totales.items(), key=lambda item: item[1], reverse=True)[:10]
    fecha_actual = datetime.datetime.now().strftime("%B %Y")
    
    bloques = [
        {"type": "header", "text": {"type": "plain_text", "text": "🏆 Leaderboard", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Global · *{fecha_actual}*"}]},
        {"type": "divider"}
    ]
    
    medallas = ["🥇", "🥈", "🥉"]
    for i in range(min(3, len(sorted_db))):
        uid, pts = sorted_db[i]
        info = obtener_info_usuario(uid)
        bloques.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{medallas[i]} *{i+1}. {info['name']}*\n{pts} Kudos"}, "accessory": {"type": "image", "image_url": info['image'], "alt_text": "avatar"}})

    if len(sorted_db) > 3:
        bloques.append({"type": "divider"})
        fields = []
        for i in range(3, len(sorted_db)):
            uid, pts = sorted_db[i]
            fields.extend([{"type": "mrkdwn", "text": f"*{i+1}.* <@{uid}>"}, {"type": "mrkdwn", "text": f"{pts} Kudos"}])
        bloques.append({"type": "section", "fields": fields})

    bloques.append({"type": "divider"})
    bloques.append({"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Mis estadísticas", "emoji": True}, "value": "mis_stats", "action_id": "mis_stats", "style": "primary"}]})
    
    try:
        if channel_id:
            client.chat_postMessage(channel=channel_id, blocks=bloques, text="Leaderboard")
        else:
            client.chat_postMessage(channel=user_id, blocks=bloques, text="Leaderboard")
    except Exception as e:
        print(f"❌ Error enviando leaderboard: {e}")

# 3. MIS ESTADISTICAS
@app.action("mis_stats")
def action_mis_stats(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    client.chat_postEphemeral(channel=channel_id, user=user_id, blocks=generar_bloques_stats(user_id), text="Tus stats")

@app.shortcut("mis-kudos")  
@app.command("/mis-kudos")  
def command_mis_stats(ack, body, client):
    ack()
    user_id = body.get("user_id") or body.get("user", {}).get("id")
    channel_id = body.get("channel_id")
    bloques = generar_bloques_stats(user_id)

    try:
        if channel_id:
            client.chat_postEphemeral(channel=channel_id, user=user_id, blocks=bloques, text="Tus stats")
        else:
            client.chat_postMessage(channel=user_id, blocks=bloques, text="Tus stats")
    except Exception as e:
        print(f"❌ Error enviando stats: {e}")

# --- HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"OK")
    def log_message(self, format, *args): pass

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000)) 
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🏥 Health Check corriendo en el puerto {port}")
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_check_server, daemon=True).start()
    print("🤖 Bot conectando a Slack...")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()