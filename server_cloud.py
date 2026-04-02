import eventlet
eventlet.monkey_patch()
import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, LikeEvent, GiftEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

DB_FILE = "base_datos.json"
ADMIN_ID = "portal.maravilla"
P_M, P_XP, F_XP, MULTA_TRAMPA = 100, 10, 20, 50

usuarios = {}
cont_promo = 0
premiados_promo = []
respuestas_prohibidas = ["verde", "3", "maravilla", "llave", "blanco", "ojos", "johnny", "azul", "maravilla2026", "leon", "exito"]

def cargar_db():
    global usuarios
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f:
            usuarios = json.load(f)

def guardar_db():
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(usuarios, f, indent=4)

cargar_db()

# --- LAS 13 TRIVIAS COMPLETAS ---
TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "res": "verde", "premio": 1000, "xp": 500},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "res": "3", "premio": 1000, "xp": 500},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "res": "maravilla", "premio": 500, "xp": 1000},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "res": "llave", "premio": 800, "xp": 1500},
    {"id": 1, "cat": " TikTok 📱", "tit": "Portal Rojo", "costo": 10, "res": "blanco", "premio": 100, "xp": 100},
    {"id": 2, "cat": " TikTok 📱", "tit": "Efecto Neón", "costo": 15, "res": "ojos", "premio": 150, "xp": 150},
    {"id": 3, "cat": " TikTok 📱", "tit": "Baile 777", "costo": 20, "res": "johnny", "premio": 200, "xp": 200},
    {"id": 300, "cat": " Socios 🤝", "tit": "Patrocinio Oro", "costo": 1000, "res": "maravilla", "premio": 4000, "xp": 4000},
    {"id": 301, "cat": " Socios 🤝", "tit": "Misión Recon", "costo": 200, "res": "azul", "premio": 800, "xp": 1000},
    {"id": 302, "cat": " Socios 🤝", "tit": "Código Oro", "costo": 500, "res": "maravilla2026", "premio": 1500, "xp": 2000},
    {"id": 303, "cat": " Socios 🤝", "tit": "Detective", "costo": 300, "res": "leon", "premio": 1000, "xp": 1200},
    {"id": 304, "cat": " Socios 🤝", "tit": "Socio VIP", "costo": 1500, "url": "perfil_socio_4", "preg": "¿Palabra biografía?", "res": "exito", "premio": 5000, "xp": 6000},
    {"id": 305, "cat": " Socios 🤝", "tit": "Explorador", "costo": 800, "url": "perfil_socio_5", "preg": "¿Calificación?", "res": "5", "premio": 2500, "xp": 3000},
]

@app.route('/')
def home(): return "Servidor Maravilla Hub ONLINE 🚀"

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado').lower().strip()
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": 500, "logros": []}
        guardar_db()
    xp = usuarios[uid]['puntos']
    diff = 3 + int(math.log10(xp)) if xp >= 10 else 3
    ranking = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
    return jsonify({"stats": usuarios[uid], "trivias": TRIVIAS_MAESTRAS, "ranking": [{"user": v['nombre'], "puntos": v['puntos']} for k, v in ranking], "dificultad": diff})

@socketio.on('actualizar_progreso_memoria')
def progreso(data):
    u = data.get('user').lower().strip()
    if u in usuarios:
        if data.get('exito'):
            usuarios[u]['monedas'] += P_M; usuarios[u]['puntos'] += P_XP
        else:
            usuarios[u]['puntos'] = max(0, usuarios[u]['puntos'] - F_XP)
        guardar_db()
        diff = 3 + int(math.log10(usuarios[u]['puntos'])) if usuarios[u]['puntos'] >= 10 else 3
        emit('update_stats', {'stats': usuarios[u], 'dificultad': diff}, room=request.sid)
        ranking = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
        emit('update_ranking', [{"user": v['nombre'], "puntos": v['puntos']} for k, v in ranking], broadcast=True)

@socketio.on('verificar_trivia')
def verificar(data):
    u, tid, res = data['user'].lower().strip(), data['trivia_id'], data['respuesta'].lower().strip()
    t = next((x for x in TRIVIAS_MAESTRAS if x['id'] == tid), None)
    if t and u in usuarios and res == t['res'] and tid not in usuarios[u]['logros']:
        if usuarios[u]['monedas'] >= t['costo']:
            usuarios[u]['monedas'] = (usuarios[u]['monedas'] - t['costo']) + t['premio']
            usuarios[u]['puntos'] += t.get('xp', 500)
            usuarios[u]['logros'].append(tid)
            guardar_db()
            emit('resultado_trivia', {'success': True, 'id_completado': tid, 'stats': usuarios[u]}, room=request.sid)

@socketio.on('comando_masivo_97')
def masivo(data):
    lista_users = data.get('users', [])
    for user_id in lista_users:
        uid = user_id.lower().strip()
        if uid in usuarios:
            usuarios[uid]['puntos'] += 40
            usuarios[uid]['monedas'] += 200
    guardar_db()
    ranking = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
    emit('update_ranking', [{"user": v['nombre'], "puntos": v['puntos']} for k, v in ranking], broadcast=True)

def run_tiktok():
    global cont_promo, premiados_promo
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=ADMIN_ID)

    @client.on("like")
    async def on_like(event: LikeEvent):
        global cont_promo
        uid = event.user.unique_id.lower()
        if cont_promo < 10 and uid not in premiados_promo and uid in usuarios:
            usuarios[uid]['puntos'] += 50
            premiados_promo.append(uid)
            cont_promo += 1
            guardar_db()
            socketio.emit('evento_especial', {'msg': f'¡MegaLike! @{uid} +50 XP ({cont_promo}/10)'})

    @client.on("gift")
    async def on_gift(event: GiftEvent):
        uid = event.user.unique_id.lower()
        if uid in usuarios:
            monedas = event.gift.info.diamond_count * 100
            usuarios[uid]['monedas'] += monedas
            guardar_db()
            socketio.emit('evento_especial', {'msg': f'@{uid} envió regalo: +{monedas}M'})

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        global cont_promo, premiados_promo
        msg, uid = event.comment.lower().strip(), event.user.unique_id.lower()
        
        # Filtro de tramposos
        if msg in respuestas_prohibidas and uid in usuarios:
            usuarios[uid]['puntos'] = max(0, usuarios[uid]['puntos'] - MULTA_TRAMPA)
            guardar_db()
            socketio.emit('recibir_mensaje', {'user': 'SISTEMA', 'msg': f'@{uid} multa -50 XP por filtrar respuesta'})

        if uid == ADMIN_ID:
            if msg == "#66": socketio.emit('toggle_auto', {'active': True})
            if msg == "#67": socketio.emit('toggle_auto', {'active': False})
            if msg == "#96": 
                cont_promo = 0; premiados_promo = []
                socketio.emit('recibir_mensaje', {'user': 'SISTEMA', 'msg': 'Promo Likes Reiniciada'})

        if msg == "!puntos" and uid in usuarios:
            u = usuarios[uid]
            socketio.emit('recibir_mensaje', {'user': 'SISTEMA', 'msg': f'@{uid}: 💎{u["monedas"]}M | 🏆{u["puntos"]}XP'})

        m = {"1":"rojo","2":"azul","3":"verde","4":"amarillo"}
        if msg in m: socketio.emit('intento_usuario_tiktok', {'user': uid, 'color': m[msg]})

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
