import eventlet
eventlet.monkey_patch()
import json, os, threading, asyncio, math
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, ShareEvent

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURACIÓN DE ECONOMÍA ---
PREMIO_ACIERTOS_XP = 100
PREMIO_ACIERTOS_MONEDAS = 50
PENALIZACION_FALLO_XP = 20
PREMIO_COMPARTIR_MONEDAS = 100
LIMITE_SHARES = 2
REGALO_INICIAL_MONEDAS = 500
VALOR_MONEDA_TIKTOK = 100 # 1 Diamante = 100 M

usuarios = {} 
TIKTOK_USER = "portal.maravilla" 

# --- TRIVIAS COMPLETAS (Incluyendo SOCIOS) ---
TRIVIAS_MAESTRAS = [
    {"id": 101, "cat": " Diario ⚡", "tit": "Reto TikTok 1", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué color brilla?", "res": "verde", "premio": 1000},
    {"id": 102, "cat": " Diario ⚡", "tit": "Reto TikTok 2", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Cuántos dedos ves?", "res": "3", "premio": 1000},
    {"id": 201, "cat": " Niveles ⭐", "tit": "Maestría I", "costo": 50, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Palabra clave?", "res": "maravilla", "premio": 500},
    {"id": 202, "cat": " Niveles ⭐", "tit": "Maestría II", "costo": 100, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué objeto sale?", "res": "llave", "premio": 800},
    {"id": 1, "cat": " TikTok 📱", "tit": "Portal Rojo", "costo": 10, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Color logo?", "res": "blanco", "premio": 100},
    {"id": 2, "cat": " TikTok 📱", "tit": "Efecto Neón", "costo": 15, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Qué brilla?", "res": "ojos", "premio": 150},
    {"id": 3, "cat": " TikTok 📱", "tit": "Baile 777", "costo": 20, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "¿Quién sale?", "res": "johnny", "premio": 200},
    {"id": 300, "cat": " Socios 🤝", "tit": "Patrocinio Oro", "costo": 1000, "url": "https://www.tiktok.com/@portal.maravilla", "preg": "Código del Socio:", "res": "maravilla", "premio": 4000, "xp": 4000},
]

def obtener_ranking():
    sorted_users = sorted(usuarios.items(), key=lambda x: x[1]['puntos'], reverse=True)
    return [{"user": u[1]['nombre'], "puntos": u[1]['puntos'], "monedas": u[1]['monedas']} for u in sorted_users[:5]]

# --- LÓGICA TIKTOK LIVE ---
def run_tiktok():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TikTokLiveClient(unique_id=TIKTOK_USER)

    @client.on("comment")
    async def on_comment(event: CommentEvent):
        u_id = event.user.unique_id
        msg = event.comment.lower().strip()
        if u_id not in usuarios:
            usuarios[u_id] = {"nombre": event.user.nickname, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0}

        mapeo = {"1": "Rojo", "2": "Azul", "3": "Verde", "4": "Amarillo", 
                 "rojo": "Rojo", "azul": "Azul", "verde": "Verde", "amarillo": "Amarillo"}
        
        if msg in mapeo:
            socketio.emit('evento_especial', {'tipo': 'input_externo', 'user': u_id, 'color': mapeo[msg]})

    @client.on("gift")
    async def on_gift(event: GiftEvent):
        if not event.streaking:
            u_id = event.user.unique_id
            m_ganadas = event.gift.info.diamond_count * VALOR_MONEDA_TIKTOK
            if u_id in usuarios:
                usuarios[u_id]['monedas'] += m_ganadas
                socketio.emit('evento_especial', {'tipo': 'regalo', 'user': event.user.nickname, 'msg': f"¡Envió {event.gift.info.name}! +{m_ganadas} M", 'monedas': m_ganadas})
                socketio.emit('update_ranking', obtener_ranking())

    async def start():
        try: await client.connect()
        except: pass
    loop.run_until_complete(start())

@app.route('/login', methods=['POST'])
def login():
    uid = request.json.get('id', 'Invitado')
    if uid not in usuarios:
        usuarios[uid] = {"nombre": uid, "puntos": 0, "monedas": REGALO_INICIAL_MONEDAS, "shares": 0}
    trivias_pub = [{k: v for k, v in t.items() if k != 'res'} for t in TRIVIAS_MAESTRAS]
    return jsonify({"stats": usuarios[uid], "trivias": trivias_pub, "ranking": obtener_ranking()})

@socketio.on('actualizar_progreso_memoria')
def handle_progreso(data):
    u_id, exito = data.get('user'), data.get('exito')
    if u_id in usuarios:
        if exito:
            usuarios[u_id]['puntos'] += PREMIO_ACIERTOS_XP
            usuarios[u_id]['monedas'] += PREMIO_ACIERTOS_MONEDAS
        else:
            usuarios[u_id]['puntos'] = max(0, usuarios[u_id]['puntos'] - PENALIZACION_FALLO_XP)
        emit('update_stats', {'stats': usuarios[u_id]}, room=request.sid)
        emit('update_ranking', obtener_ranking(), broadcast=True)

if __name__ == '__main__':
    threading.Thread(target=run_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
