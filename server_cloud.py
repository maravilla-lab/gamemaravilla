import eventlet
eventlet.monkey_patch()

import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURACIÓN DE ECONOMÍA ---
PREMIO_ACIERTOS_XP = 100
PREMIO_ACIERTOS_MONEDAS = 50
PENALIZACION_FALLO_XP = 20
PREMIO_COMPARTIR_MONEDAS = 100
LIMITE_SHARES = 2
REGALO_INICIAL_MONEDAS = 500  # Cambiar a 100 después del 3er Live

# --- BASE DE DATOS Y ADMIN ---
usuarios = {} 
TIKTOK_USER = "portal.maravilla" 
ADMIN_UNIQUE_ID = "portal.maravilla"

# --- TRIVIAS COMPLETAS ---
TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué color brilla?", "res": "verde", "premio": 1000},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Cuántos dedos ves?", "res": "3", "premio": 1000},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Palabra clave?", "res": "maravilla", "premio": 500},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué objeto sale?", "res": "llave", "premio": 800},
    {"id": 1, "cat": " TikTok 📱", "tit": "Portal Rojo", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Color logo?", "res": "blanco", "premio": 100},
    {"id": 2, "cat": " TikTok 📱", "tit": "Efecto Neón", "costo": 15, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué brilla?", "res": "ojos", "premio": 150},
    {"id": 3, "cat": " TikTok 📱", "tit": "Baile 777", "costo": 20, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Quién sale?", "res": "johnny", "premio": 200},
# Añade aquí tus nuevas trivias de patrocinadores:

    # { "id": 300, "cat": " Socios 🤝", "tit": "Visita a @Amigo", "costo": 0, "url": "URL", "preg": "...", "res": "...", "premio": 2000 },
]
def obtener_ranking():
    sorted_users = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)
    return [{"user": u[1]['nombre'], "puntos": u[1]['puntos'], "monedas": u[1]['monedas']} for u in sorted_users[:5]]

# --- MOTOR TIKTOK ---
def run_tiktok():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USER)

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        u_id = event.user.unique_id
        user_name = event.user.nickname
        msg = event.comment.lower().strip()

        if u_id not in usuarios:
            usuarios[u_id] = {"nombre": user_name, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0}

        # COMANDO RECARGA POR REGALOS (Solo Admin)
        if u_id == ADMIN_UNIQUE_ID and msg.startswith("!recarga"):
            try:
                partes = msg.split()
                target = partes[1].replace("@", "")
                monto = int(partes[2])
                if target in usuarios:
                    usuarios[target]['monedas'] += monto
                    socketio.emit('update_ranking', obtener_ranking())
                    print(f"RECARGA EXITOSA: {target} recibió {monto} monedas.")
            except: pass

        # JUEGO RÁPIDO POR NÚMEROS
        mapeo = {"1": "rojo", "2": "azul", "3": "verde", "4": "amarillo"}
        if msg in mapeo:
            socketio.emit('intento_usuario', {'user': u_id, 'color': mapeo[msg]})
        elif msg in ["rojo", "azul", "verde", "amarillo"]:
            socketio.emit('intento_usuario', {'user': u_id, 'color': msg})

    @client.on("share")
    async def on_share(event):
        u_id = event.user.unique_id
        if u_id in usuarios:
            if usuarios[u_id].get('shares', 0) < LIMITE_SHARES:
                usuarios[u_id]['monedas'] += PREMIO_COMPARTIR_MONEDAS
                usuarios[u_id]['shares'] += 1
                socketio.emit('notificacion', {'msg': f"¡{usuarios[u_id]['nombre']} +100 monedas por compartir! 🎁"})
                socketio.emit('update_ranking', obtener_ranking())

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

# --- RUTAS ---
@app.route('/')
def home(): return "Servidor Maravilla Hub ONLINE 🚀"

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0}
    
    trivias_pub = [{k: v for k, v in t.items() if k != 'res'} for t in TRIVIAS_MAESTRAS]
    return jsonify({"stats": usuarios[uid], "trivias": trivias_pub, "ranking": obtener_ranking()})

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
