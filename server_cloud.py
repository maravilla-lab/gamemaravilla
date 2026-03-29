import eventlet
eventlet.monkey_patch()

import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, ShareEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURACIÓN DE ECONOMÍA Y REGLAS ---
PREMIO_PATRON_XP = 10
PREMIO_PATRON_MONEDAS = 100
PENALIZACION_FALLO_XP = 20
PREMIO_COMPARTIR_MONEDAS = 100
LIMITE_SHARES = 2
REGALO_INICIAL_MONEDAS = 500
VALOR_MONEDA_TIKTOK = 100 # 1 Diamante = 100 M
DB_FILE = "base_datos.json"

usuarios = {}
TIKTOK_USER = "portal.maravilla"
ADMIN_UNIQUE_ID = "portal.maravilla"

# --- CARGA Y GUARDADO DE BASE DE DATOS ---
def cargar_db():
    global usuarios
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                usuarios = json.load(f)
        except Exception as e:
            print(f"Error cargando DB: {e}")
            usuarios = {}

def guardar_db():
    try:
        with open(DB_FILE, "w", encoding='utf-8') as f:
            json.dump(usuarios, f, indent=4)
    except Exception as e:
        print(f"Error guardando DB: {e}")

cargar_db()

# --- TRIVIAS MAESTRAS ---
TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué color brilla?", "res": "verde", "premio": 1000},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Cuántos dedos ves?", "res": "3", "premio": 1000},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Palabra clave?", "res": "maravilla", "premio": 500},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué objeto sale?", "res": "llave", "premio": 800},
    { "id": 300, "cat": " Socios 🤝", "tit": "Visita a @Amigo", "costo": 0, "url": "URL", "preg": "...", "res": "...", "premio": 2000 },
    {"id": 1, "cat": " TikTok 📱", "tit": "Portal Rojo", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Color logo?", "res": "blanco", "premio": 100},
    {"id": 2, "cat": " TikTok 📱", "tit": "Efecto Neón", "costo": 15, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué brilla?", "res": "ojos", "premio": 150},
    {"id": 3, "cat": " TikTok 📱", "tit": "Baile 777", "costo": 20, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Quién sale?", "res": "johnny", "premio": 200},

# Añade aquí tus nuevas trivias de patrocinadores:

    # 
]
def obtener_ranking():
    sorted_users = sorted(usuarios.items(), key=lambda x: x[1].get('puntos', 0), reverse=True)
    return [{"user": u[1].get('nombre', u[0]), "puntos": u[1].get('puntos', 0), "monedas": u[1].get('monedas', 0)} for u in sorted_users[:5]]

# --- MOTOR TIKTOK ---
def run_tiktok():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USER)

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        u_id = event.user.unique_id
        msg = event.comment.lower().strip()
        if u_id not in usuarios:
            usuarios[u_id] = {"nombre": event.user.nickname, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0, "logros": []}
            guardar_db()

        # Mapeo Teclas 1,2,3,4
        mapeo = {"1": "rojo", "2": "azul", "3": "verde", "4": "amarillo", "rojo": "rojo", "azul": "azul", "verde": "verde", "amarillo": "amarillo"}
        if msg in mapeo:
            socketio.emit('intento_usuario', {'user': u_id, 'color': mapeo[msg]})

    @client.on("gift")
    async def on_gift(event: GiftEvent):
        u_id = event.user.unique_id
        if not event.streaking:
            m_ganadas = event.gift.info.diamond_count * VALOR_MONEDA_TIKTOK
            if u_id not in usuarios:
                usuarios[u_id] = {"nombre": event.user.nickname, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0, "logros": []}
            
            usuarios[u_id]['monedas'] += m_ganadas
            guardar_db()
            socketio.emit('evento_especial', {'tipo': 'regalo', 'user': event.user.nickname, 'msg': f"envió {event.gift.info.name} +{m_ganadas}M", 'monedas': m_ganadas})
            socketio.emit('update_stats', {'stats': usuarios[u_id]}, room=u_id) # Si el usuario está conectado
            socketio.emit('update_ranking', obtener_ranking())

    @client.on("share")
    async def on_share(event: ShareEvent):
        u_id = event.user.unique_id
        if u_id in usuarios and usuarios[u_id].get('shares', 0) < LIMITE_SHARES:
            usuarios[u_id]['monedas'] += PREMIO_COMPARTIR_MONEDAS
            usuarios[u_id]['shares'] += 1
            guardar_db()
            socketio.emit('notificacion', {'msg': f"¡{usuarios[u_id]['nombre']} +100M por compartir! 🎁"})

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

# --- RUTAS Y SOCKETS ---
@app.route('/')
def home(): return "Servidor Maravilla Hub ONLINE 🚀"

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0, "logros": []}
        guardar_db()
    trivias_pub = [{k: v for k, v in t.items() if k != 'res'} for t in TRIVIAS_MAESTRAS]
    return jsonify({"stats": usuarios[uid], "trivias": trivias_pub, "ranking": obtener_ranking()})

@socketio.on('actualizar_progreso_memoria')
def handle_progreso(data):
    u = data.get('user')
    if u in usuarios:
        if data.get('exito'):
            usuarios[u]['monedas'] += PREMIO_PATRON_MONEDAS
            usuarios[u]['puntos'] += PREMIO_PATRON_XP
        else:
            usuarios[u]['puntos'] = max(0, usuarios[u]['puntos'] - PENALIZACION_FALLO_XP)
        guardar_db()
        emit('update_stats', {'stats': usuarios[u]}, room=request.sid)
        emit('update_ranking', obtener_ranking(), broadcast=True)

@socketio.on('verificar_trivia')
def verificar(data):
    u, t_id, res = data['user'], data['trivia_id'], data['respuesta'].lower().strip()
    trivia = next((t for t in TRIVIAS_MAESTRAS if t['id'] == t_id), None)
    if trivia and res == trivia['res'] and u in usuarios:
        if t_id not in usuarios[u].get('logros', []):
            usuarios[u]['monedas'] += trivia['premio']
            usuarios[u]['puntos'] += trivia.get('xp', 500)
            usuarios[u].setdefault('logros', []).append(t_id)
            guardar_db()
            emit('resultado_trivia', {'success': True, 'id_completado': t_id, 'stats': usuarios[u]}, room=request.sid)
            emit('update_ranking', obtener_ranking(), broadcast=True)

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
