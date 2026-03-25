import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent

app = Flask(__name__)
# Importante: para la nube usamos un cors más abierto
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = "base_datos.json"
TIKTOK_USER = "@portal.maravilla" 
usuarios_conectados = set()

# ==========================================================
# 📋 SECCIÓN DE TRIVIAS (Edita esto para cambiar el juego)
# ==========================================================
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
# ==========================================================

# --- LÓGICA DE JUEGO ---
RECOMPENSA_PUNTOS = 100
RECOMPENSA_MONEDAS = 10
PENALIZACION_PUNTOS = 20

def calcular_dif(puntos):
    dif = 3
    if puntos >= 10: dif += int(math.log10(puntos))
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

# --- TIKTOK LIVE ---
def run_tiktok():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USER)

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        msg = event.comment.lower()
        if "!maravilla" in msg:
            socketio.emit('evento_especial', {'tipo': 'efecto_visual', 'msg': '¡MODO MARAVILLA ACTIVADO!'})
        socketio.emit('recibir_mensaje', {'user': event.user.nickname, 'msg': event.comment})

    @client.on("gift")
    async def on_gift(event: GiftEvent):
        if event.gift.id == 5655: # Rosa
            socketio.emit('evento_especial', {'tipo': 'regalo', 'msg': f"¡{event.user.nickname} envió Rosa! +50M", 'monedas': 50})

    async def start():
        try: await client.connect()
        except: print("TikTok Offline")
    loop.run_until_complete(start())

threading.Thread(target=run_tiktok, daemon=True).start()

# --- SOCKETS Y RUTAS ---
@socketio.on('connect')
def handle_connect():
    usuarios_conectados.add(request.sid)
    socketio.emit('usuarios_online', len(usuarios_conectados))

@socketio.on('disconnect')
def handle_disconnect():
    usuarios_conectados.discard(request.sid)
    socketio.emit('usuarios_online', len(usuarios_conectados))

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios: usuarios[uid] = {"puntos": 0, "monedas": 500, "logros": []}
    guardar_datos(usuarios)
    # Filtramos para no enviar la respuesta al cliente
    trivias_pub = [{k: v for k, v in t.items() if k != 'res'} for t in TRIVIAS_MAESTRAS]
    return jsonify({
        "stats": usuarios[uid], 
        "trivias": trivias_pub, 
        "ranking": obtener_ranking(), 
        "online": len(usuarios_conectados),
        "dificultad": calcular_dif(usuarios[uid]['puntos'])
    })

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
        emit('update_ranking', obtener_ranking(), broadcast=True)
        emit('resultado_trivia', {'success': True, 'stats': usuarios[uid], 'nueva_dificultad': calcular_dif(usuarios[uid]['puntos'])})

@socketio.on('verificar_trivia')
def verificar(data):
    uid, t_id, res_u = data.get('user'), data.get('trivia_id'), str(data.get('respuesta')).lower().strip()
    if uid in usuarios:
        trivia = next((t for t in TRIVIAS_MAESTRAS if t['id'] == t_id), None)
        if trivia and res_u == trivia['res'] and t_id not in usuarios[uid]['logros']:
            usuarios[uid]['monedas'] -= trivia['costo']
            usuarios[uid]['puntos'] += trivia['premio']
            usuarios[uid]['logros'].append(t_id)
            guardar_datos(usuarios)
            emit('resultado_trivia', {'success': True, 'stats': usuarios[uid], 'id_completado': t_id, 'nueva_dificultad': calcular_dif(usuarios[uid]['puntos'])})

@socketio.on('enviar_mensaje')
def manejar_m(data): emit('recibir_mensaje', data, broadcast=True)

if __name__ == '__main__':
    # Usamos el puerto que asigne la nube (Render/Railway lo requieren)
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)