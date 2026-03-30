import eventlet
eventlet.monkey_patch()
import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, ShareEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURACIÓN MAESTRA ---
DB_FILE = "base_datos.json"
NUMERO_DE_LIVE = 1 # Cambia a 4+ después del 3er Live
REGALO_INICIAL = 500 if NUMERO_DE_LIVE <= 3 else 100
VALOR_DIAMANTE = 100 # 1 Diamante = 100M
PREMIO_P, PREMIO_XP, FALLO_XP = 100, 10, 20 # Reglas de Patrón
TIKTOK_USER = "portal.maravilla"
ADMIN_ID = "portal.maravilla"

usuarios = {}

def cargar_db():
    global usuarios
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f:
            usuarios = json.load(f)

def guardar_db():
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(usuarios, f, indent=4)

cargar_db()

# --- BIBLIOTECA DE TRIVIAS (No simplificada) ---
TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "link_a_tu_perfil", "preg": "¿Color de mi camisa?", "res": "verde", "premio": 1000, "xp": 500},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "url": "link_a_tu_perfil", "preg": "¿Cuántos dedos?", "res": "3", "premio": 1000, "xp": 500},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Palabra clave?", "res": "maravilla", "premio": 500},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué objeto sale?", "res": "llave", "premio": 800},
    {"id": 301, "cat": " Socios 🤝", "tit": "Misión Recon", "costo": 200, "url": "perfil_socio_1", "preg": "¿Color de silla?", "res": "azul", "premio": 800, "xp": 1000},
    {"id": 302, "cat": " Socios 🤝", "tit": "Código Oro", "costo": 500, "url": "perfil_socio_2", "preg": "¿Código bio?", "res": "maravilla2026", "premio": 1500, "xp": 2000},
    {"id": 303, "cat": " Socios 🤝", "tit": "Detective", "costo": 300, "url": "perfil_socio_3", "preg": "¿Animal logo?", "res": "leon", "premio": 1000, "xp": 1200},
    {"id": 304, "cat": " Socios 🤝", "tit": "Socio VIP", "costo": 1500, "url": "perfil_socio_4", "preg": "¿Palabra biografía?", "res": "exito", "premio": 5000, "xp": 6000},
    {"id": 305, "cat": " Socios 🤝", "tit": "Explorador", "costo": 800, "url": "perfil_socio_5", "preg": "¿Calificación?", "res": "5", "premio": 2500, "xp": 3000}
]

def get_dificultad(xp):
    if xp < 10: return 3
    return 3 + int(math.log10(xp))

def get_ranking():
    sorted_u = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)[:5]
    return [{"user": v['nombre'], "puntos": v['puntos']} for k, v in sorted_u]

@app.route('/')
def home(): return "Servidor Maravilla Hub ONLINE 🚀"

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": REGALO_INICIAL, "logros": [], "shares": 0}
        guardar_db()
    return jsonify({"stats": usuarios[uid], "trivias": TRIVIAS_MAESTRAS, "ranking": get_ranking(), "dificultad": get_dificultad(usuarios[uid]['puntos'])})

@socketio.on('actualizar_progreso_memoria')
def progreso(data):
    u = data.get('user')
    if u in usuarios:
        if data.get('exito'):
            usuarios[u]['monedas'] += PREMIO_P; usuarios[u]['puntos'] += PREMIO_XP
        else:
            usuarios[u]['puntos'] = max(0, usuarios[u]['puntos'] - FALLO_XP)
        guardar_db()
        emit('update_stats', {'stats': usuarios[u], 'dificultad': get_dificultad(usuarios[u]['puntos'])}, room=request.sid)
        emit('update_ranking', get_ranking(), broadcast=True)

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
            emit('resultado_trivia', {'success': True, 'id_completado': tid, 'stats': usuarios[u], 'dificultad': get_dificultad(usuarios[u]['puntos'])}, room=request.sid)
            emit('update_ranking', get_ranking(), broadcast=True)

def run_tiktok():
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USER)

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        msg = event.comment.lower().strip()
        u_id = event.user.unique_id
        if u_id not in usuarios:
            usuarios[u_id] = {"nombre": event.user.nickname, "puntos": 0, "monedas": REGALO_INICIAL, "logros": [], "shares": 0}
        
        # Lógica de Comandos !mision
        if msg.startswith("!mision"):
            try:
                parts = msg.split() # !mision 101 verde
                socketio.emit('comando_mision', {'user': u_id, 'tid': int(parts[1]), 'res': parts[2]})
            except: pass

        # Mapeo 1,2,3,4
        m = {"1":"rojo","2":"azul","3":"verde","4":"amarillo","rojo":"rojo","azul":"azul","verde":"verde","amarillo":"amarillo"}
        if msg in m: socketio.emit('intento_usuario', {'user': u_id, 'color': m[msg]})

    @client.on("gift")
    async def on_gift(event: GiftEvent):
        if not event.streaking:
            u_id = event.user.unique_id
            if u_id in usuarios:
                m_ganadas = event.gift.info.diamond_count * VALOR_DIAMANTE
                usuarios[u_id]['monedas'] += m_ganadas; guardar_db()
                socketio.emit('evento_especial', {'tipo': 'regalo', 'user': event.user.nickname, 'msg': f"envió {event.gift.info.name} +{m_ganadas}M"})

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
