import eventlet
eventlet.monkey_patch()

import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = "base_datos.json"
TIKTOK_USER = "@portal.maravilla" 
usuarios_conectados = set()

# --- BALANCE DEL JUEGO ---
RECOMPENSA_PUNTOS = 100
RECOMPENSA_MONEDAS = 10
PENALIZACION_PUNTOS = 20

def calcular_dif(puntos):
    dif = 3
    if puntos >= 10:
        dif += int(math.log10(puntos))
    return dif

def cargar_db():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f: return json.load(f)
        except: pass
    return {}

usuarios = cargar_db()

def guardar_datos(data):
    with open(DB_PATH, "w") as f: json.dump(data, f, indent=4)

def obtener_ranking():
    sorted_users = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)
    return [{"user": u[0], "puntos": u[1]['puntos']} for u in sorted_users[:5]]

TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué color brilla?", "res": "verde", "premio": 1000},
]

# --- RUTAS ---
@app.route('/')
def home():
    return "Servidor Maravilla Hub Online 🚀"

@app.route('/login', methods=['POST'])
def login():
    try:
        uid = request.json.get('id', 'Invitado')
        if uid not in usuarios:
            usuarios[uid] = {"puntos": 0, "monedas": 500, "logros": []}
        guardar_datos(usuarios)
        trivias_pub = [{k: v for k, v in t.items() if k != 'res'} for t in TRIVIAS_MAESTRAS]
        return jsonify({
            "stats": usuarios[uid], 
            "trivias": trivias_pub, 
            "ranking": obtener_ranking(), 
            "online": len(usuarios_conectados),
            "dificultad": calcular_dif(usuarios[uid]['puntos'])
        })
    except:
        return jsonify({"error": "server error"}), 500

# --- TIKTOK LIVE ---
def run_tiktok():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TikTokLiveClient(unique_id=TIKTOK_USER)
        
        @client.on("comment")
        async def on_comment(event: CommentEvent):
            socketio.emit('recibir_mensaje', {'user': event.user.nickname, 'msg': event.comment})
            
        async def start():
            try:
                await client.connect()
            except:
                pass
        
        loop.run_until_complete(start())
    except:
        pass

threading.Thread(target=run_tiktok, daemon=True).start()

# --- SOCKETS ---
@socketio.on('connect')
def handle_connect():
    usuarios_conectados.add(request.sid)
    socketio.emit('usuarios_online', len(usuarios_conectados))

@socketio.on('actualizar_progreso_memoria')
def actualizar_memoria(data):
    uid = data.get('user')
    exito = data.get('exito', False)
    if uid in usuarios:
        if exito:
            usuarios[uid]['puntos'] += RECOMPENSA_PUNTOS
            usuarios[uid]['monedas'] += RECOMPENSA_MONEDAS
        else:
            usuarios[uid]['puntos'] = max(0, usuarios[uid]['puntos'] - PENALIZACION_PUNTOS)
        guardar_datos(usuarios)
        socketio.emit('update_ranking', obtener_ranking())
        emit('resultado_trivia', {'success': True, 'stats': usuarios[uid], 'nueva_dificultad': calcular_dif(usuarios[uid]['puntos'])})

@socketio.on('enviar_mensaje')
def manejar_m(data):
    emit('recibir_mensaje', data, broadcast=True)

threading.Thread(target=run_tiktok, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
