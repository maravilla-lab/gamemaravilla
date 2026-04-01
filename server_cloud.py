import eventlet
eventlet.monkey_patch()
import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, LikeEvent, ShareEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURACIÓN MAESTRA ---
DB_FILE = "base_datos.json"
NUMERO_LIVE = 1
REGALO_INICIAL = 500 if NUMERO_LIVE <= 3 else 100
VALOR_D = 100
P_M, P_XP, F_XP, MULTA = 100, 10, 20, 50
PREMIO_INTERACCION_XP = 50 # Recompensa por Like/Share
ADMIN_ID = "portal.maravilla"

# Control de los primeros 10
contador_interacciones = 0
usuarios_premiados = []

usuarios = {}
RESPUESTAS_KEY = ["verde", "maravilla", "3", "llave", "blanco", "ojos", "johnny", "azul", "maravilla2026", "leon", "exito", "5"]

def cargar_db():
    global usuarios
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f:
            usuarios = json.load(f)

def guardar_db():
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(usuarios, f, indent=4)

cargar_db()

TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué color brilla?", "res": "verde", "premio": 1000},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Cuántos dedos ves?", "res": "3", "premio": 1000},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Palabra clave?", "res": "maravilla", "premio": 500},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué objeto sale?", "res": "llave", "premio": 800},
    {"id": 300, "cat": " Socios 🤝", "tit": "Patrocinio Oro", "costo": 1000, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "Código:", "res": "maravilla", "premio": 4000, "xp": 4000},
    {"id": 301, "cat": " Socios 🤝", "tit": "Misión Recon", "costo": 200, "url": "perfil_socio_1", "preg": "¿Silla?", "res": "azul", "premio": 800, "xp": 1000},
    {"id": 302, "cat": " Socios 🤝", "tit": "Código Oro", "costo": 500, "url": "perfil_socio_2", "preg": "¿Bio?", "res": "maravilla2026", "premio": 1500, "xp": 2000},
    {"id": 303, "cat": " Socios 🤝", "tit": "Detective", "costo": 300, "url": "perfil_socio_3", "preg": "¿Animal?", "res": "leon", "premio": 1000, "xp": 1200},
    {"id": 304, "cat": " Socios 🤝", "tit": "Socio VIP", "costo": 1500, "url": "perfil_socio_4", "preg": "¿Palabra biografía?", "res": "exito", "premio": 5000, "xp": 6000},
    {"id": 305, "cat": " Socios 🤝", "tit": "Explorador", "costo": 800, "url": "perfil_socio_5", "preg": "¿Calificación?", "res": "5", "premio": 2500, "xp": 3000},
    {"id": 1, "cat": " TikTok 📱", "tit": "Portal Rojo", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Color logo?", "res": "blanco", "premio": 100},
    {"id": 2, "cat": " TikTok 📱", "tit": "Efecto Neón", "costo": 15, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué brilla?", "res": "ojos", "premio": 150},
    {"id": 3, "cat": " TikTok 📱", "tit": "Baile 777", "costo": 20, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Quién sale?", "res": "johnny", "premio": 200},

]

@app.route('/')
def home(): return "Servidor Maravilla Hub ONLINE 🚀"

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": REGALO_INICIAL, "logros": [], "shares": 0}
        guardar_db()
    xp = usuarios[uid]['puntos']
    diff = 3 + int(math.log10(xp)) if xp >= 10 else 3
    sorted_u = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
    ranking = [{"user": v['nombre'], "puntos": v['puntos']} for k, v in sorted_u]
    return jsonify({"stats": usuarios[uid], "trivias": TRIVIAS_MAESTRAS, "ranking": ranking, "dificultad": diff})

@socketio.on('actualizar_progreso_memoria')
def progreso(data):
    u = data.get('user')
    if u in usuarios:
        if data.get('exito'):
            usuarios[u]['monedas'] += P_M; usuarios[u]['puntos'] += P_XP
        else:
            usuarios[u]['puntos'] = max(0, usuarios[u]['puntos'] - F_XP)
        guardar_db()
        xp = usuarios[u]['puntos']
        diff = 3 + int(math.log10(xp)) if xp >= 10 else 3
        emit('update_stats', {'stats': usuarios[u], 'dificultad': diff}, room=request.sid)
        sorted_u = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
        emit('update_ranking', [{"user": v['nombre'], "puntos": v['puntos']} for k, v in sorted_u], broadcast=True)

@socketio.on('verificar_trivia')
def verificar(data):
    u, tid, res = data['user'], data['trivia_id'], data['respuesta'].lower().strip()
    t = next((x for x in TRIVIAS_MAESTRAS if x['id'] == tid), None)
    if t and u in usuarios and res == t['res'] and tid not in usuarios[u]['logros']:
        if usuarios[u]['monedas'] >= t['costo']:
            usuarios[u]['monedas'] = (usuarios[u]['monedas'] - t['costo']) + t['premio']
            usuarios[u]['puntos'] += t.get('xp', 500)
            usuarios[u]['logros'].append(tid)
            guardar_db()
            xp = usuarios[u]['puntos']; diff = 3 + int(math.log10(xp)) if xp >= 10 else 3
            emit('resultado_trivia', {'success': True, 'id_completado': tid, 'stats': usuarios[u], 'dificultad': diff}, room=request.sid)
            sorted_u = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
            emit('update_ranking', [{"user": v['nombre'], "puntos": v['puntos']} for k, v in sorted_u], broadcast=True)

@socketio.on('enviar_mensaje')
def handle_msg(data):
    emit('recibir_mensaje', data, broadcast=True)

def run_tiktok():
    global contador_interacciones, usuarios_premiados
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id="portal.maravilla")

    @client.on("like")
    async def on_like(event: LikeEvent):
        global contador_interacciones
        u_id = event.user.unique_id
        if contador_interacciones < 10 and u_id not in usuarios_premiados:
            if u_id in usuarios:
                usuarios[u_id]['puntos'] += PREMIO_INTERACCION_XP
                usuarios_premiados.append(u_id)
                contador_interacciones += 1
                guardar_db()
                socketio.emit('evento_especial', {'tipo': 'promo', 'user': event.user.nickname, 'msg': f'¡Top 10 MegaLike! +50 XP ({contador_interacciones}/10)'})

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        msg, u_id = event.comment.lower().strip(), event.user.unique_id
        if msg in RESPUESTAS_KEY:
            if u_id in usuarios:
                usuarios[u_id]['puntos'] = max(0, usuarios[u_id]['puntos'] - MULTA); guardar_db()
                socketio.emit('evento_especial', {'tipo': 'trampa', 'user': event.user.nickname, 'msg': 'Penalizado -50 XP por revelar respuesta'})

        if msg == "#66" and u_id == ADMIN_ID: socketio.emit('toggle_auto', {'active': True})
        if msg == "#67" and u_id == ADMIN_ID: socketio.emit('toggle_auto', {'active': False})
        
        if msg.startswith("!mision"):
            socketio.emit('recibir_mensaje', {'user': 'SISTEMA', 'msg': f"@{event.user.nickname} usa !{msg.split()[1]} [respuesta] para completar"})
        
        if msg.startswith("!") and len(msg.split()) > 1:
            try:
                tid = int(msg[1:].split()[0])
                res = msg.split()[1]
                socketio.emit('validar_mision_directa', {'user': u_id, 'tid': tid, 'res': res})
            except: pass

        m = {"1":"rojo","2":"azul","3":"verde","4":"amarillo","rojo":"rojo","azul":"azul","verde":"verde","amarillo":"amarillo"}
        if msg in m: socketio.emit('intento_usuario', {'user': u_id, 'color': m[msg]})

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
