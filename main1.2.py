import sys, random, requests, socketio, threading, time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class MaravillaGame(QWidget):
    signal_resultado = pyqtSignal(dict)
    signal_chat = pyqtSignal(dict)
    signal_ranking = pyqtSignal(list)
    signal_online = pyqtSignal(int)
    signal_especial = pyqtSignal(dict)
    signal_nuevo_lider = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self.dificultad_actual = 3
        self.muted = False
        self.uid = "portal.maravilla" # Tu ID Admin

        self.puntos, self.monedas = 0, 0
        self.trivias, self.logros_usuario, self.patron, self.secuencia_usuario = [], [], [], []
        self.sio = socketio.Client()
        
        # Conexiones de señales
        self.signal_resultado.connect(self.procesar_resultado)
        self.signal_chat.connect(self.agregar_mensaje_chat)
        self.signal_ranking.connect(self.actualizar_ranking_ui)
        self.signal_online.connect(lambda c: self.lbl_online.setText(f"Online: {c}"))
        self.signal_especial.connect(self.mostrar_especial)
        self.signal_nuevo_lider.connect(self.efecto_trofeo)

        self.init_ui()
        self.conectar_sio()
        self.conectar_datos()

        # Temporizador para el ciclo de 10 segundos
        self.timer_ciclo = QTimer()
        self.timer_ciclo.timeout.connect(self.generar_patron)
        self.timer_ciclo.start(10000) # 10 segundos

    def init_ui(self):
        self.setWindowTitle("Maravilla Hub - Live 24H")
        self.setFixedSize(1100, 750)
        self.setStyleSheet("background-color: #0d1117; color: white; font-family: Segoe UI;")

        layout = QHBoxLayout()
        left = QVBoxLayout()
        
        # --- HEADER ---
        header = QHBoxLayout()
        self.lbl_user = QLabel(f"👤 {self.uid}")
        self.lbl_puntos = QLabel("XP: 0")
        self.lbl_monedas = QLabel("💰: 0")
        self.lbl_online = QLabel("Online: 0")
        [l.setStyleSheet("font-weight: bold; font-size: 16px; color: #58a6ff;") for l in [self.lbl_user, self.lbl_puntos, self.lbl_monedas, self.lbl_online]]
        header.addWidget(self.lbl_user); header.addStretch(); header.addWidget(self.lbl_puntos); header.addWidget(self.lbl_monedas); header.addWidget(self.lbl_online)
        left.addLayout(header)

        # --- ÁREA DE JUEGO (TROFEO Y PATRÓN) ---
        self.trofeo = QLabel("🏆")
        self.trofeo.setAlignment(Qt.AlignCenter)
        self.trofeo.setStyleSheet("font-size: 80px; margin: 10px;")
        left.addWidget(self.trofeo)

        self.lbl_lider = QLabel("LÍDER ACTUAL: ---")
        self.lbl_lider.setAlignment(Qt.AlignCenter)
        self.lbl_lider.setStyleSheet("color: #f1c40f; font-weight: bold; font-size: 20px;")
        left.addWidget(self.lbl_lider)

        self.display_patron = QHBoxLayout()
        self.bolas = [QLabel() for _ in range(6)]
        for b in self.bolas:
            b.setFixedSize(60, 60); b.setStyleSheet("background: #161b22; border-radius: 30px; border: 2px solid #30363d;")
            self.display_patron.addWidget(b)
        left.addLayout(self.display_patron)

        # Leyenda de ayuda para el chat
        self.leyenda = QLabel("1:ROJO | 2:AZUL | 3:VERDE | 4:AMARILLO")
        self.leyenda.setAlignment(Qt.AlignCenter)
        self.leyenda.setStyleSheet("color: #8b949e; font-size: 14px; margin-top: 10px;")
        left.addWidget(self.leyenda)

        # --- CONTROLES ---
        self.btn_gen = QPushButton("INICIAR CICLO 24H")
        self.btn_gen.clicked.connect(self.generar_patron)
        self.btn_gen.setStyleSheet("background: #238636; font-weight: bold; height: 50px; border-radius: 10px;")
        left.addWidget(self.btn_gen)

        grid = QGridLayout()
        self.btns = {}
        colores_hex = {"rojo": "#f85149", "azul": "#58a6ff", "verde": "#3fb950", "amarillo": "#d29922"}
        for i, (name, hex) in enumerate(colores_hex.items()):
            btn = QPushButton(f"{i+1}") # Mostramos el número en el botón
            btn.setFixedSize(120, 120)
            btn.setStyleSheet(f"background: {hex}; border-radius: 60px; font-size: 24px; font-weight: bold;")
            btn.clicked.connect(lambda _, n=name: self.registrar_secuencia(n))
            self.btns[name] = btn
            grid.addWidget(btn, 0, i)
        left.addLayout(grid)
        layout.addLayout(left, 2)

        # --- PANEL DERECHO (RANKING Y CHAT) ---
        right = QVBoxLayout()
        self.lbl_rank_tit = QLabel("🏆 RANKING GLOBAL")
        self.lbl_rank_tit.setStyleSheet("font-weight: bold; color: #f1c40f;")
        right.addWidget(self.lbl_rank_tit)
        
        self.lista_rank = QListWidget()
        self.lista_rank.setStyleSheet("background: #161b22; border: none; font-size: 14px;")
        right.addWidget(self.lista_rank)

        self.chat = QTextEdit(); self.chat.setReadOnly(True)
        self.chat.setStyleSheet("background: #010409; border: 1px solid #30363d; color: #8b949e;")
        right.addWidget(self.chat)
        
        layout.addLayout(right, 1)
        self.setLayout(layout)

    # --- LÓGICA DE CONEXIÓN ---
    def conectar_sio(self):
        @self.sio.on('connect')
        def on_connect(): print("Conectado SIO")

        @self.sio.on('update_ranking')
        def on_rank(data): self.signal_ranking.emit(data)

        @self.sio.on('intento_usuario')
        def on_intento(data):
            # Esta señal recibe el intento de TikTok (1,2,3,4)
            self.signal_chat.emit({'user': data['user'], 'msg': f"envió {data['color']}"})
            # Aquí podrías comparar con el patrón actual si quieres puntuar directo

        @self.sio.on('notificacion')
        def on_notif(data): self.signal_especial.emit(data)

        threading.Thread(target=self.iniciar_sio, daemon=True).start()

    def iniciar_sio(self):
        try: self.sio.connect("https://gamemaravilla-production.up.railway.app")
        except: pass

    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}, timeout=5).json()
            self.puntos = r['stats']['puntos']
            self.monedas = r['stats']['monedas']
            self.signal_ranking.emit(r.get('ranking', []))
            self.actualizar_ui()
        except: pass

    # --- MECÁNICAS DE JUEGO ---
    def generar_patron(self):
        self.secuencia_usuario = []
        self.patron = [random.choice(["rojo", "azul", "verde", "amarillo"]) for _ in range(self.dificultad_actual)]
        for i, b in enumerate(self.bolas):
            if i < len(self.patron):
                color = self.patron[i]
                hex_c = {"rojo": "#f85149", "azul": "#58a6ff", "verde": "#3fb950", "amarillo": "#d29922"}[color]
                b.setStyleSheet(f"background: {hex_c}; border-radius: 30px; border: 2px solid white;")
            else:
                b.setStyleSheet("background: #161b22; border-radius: 30px; border: 2px solid #30363d;")
        
        # El patrón brilla 3 segundos y luego se oculta para que memoricen
        QTimer.singleShot(3000, self.ocultar_patron)

    def ocultar_patron(self):
        for b in self.bolas: b.setStyleSheet("background: #30363d; border-radius: 30px;")

    def registrar_secuencia(self, color):
        self.secuencia_usuario.append(color)
        if len(self.secuencia_usuario) == len(self.patron):
            exito = self.secuencia_usuario == self.patron
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': exito})
            self.conectar_datos() # Refrescar stats

    def actualizar_ui(self):
        self.lbl_puntos.setText(f"XP: {self.puntos}")
        self.lbl_monedas.setText(f"💰: {self.monedas}")

    def actualizar_ranking_ui(self, rank):
        self.lista_rank.clear()
        for i, item in enumerate(rank):
            self.lista_rank.addItem(f"{i+1}. {item['user']} - {item['puntos']} XP")
            if i == 0:
                if self.lbl_lider.text() != f"LÍDER ACTUAL: {item['user']}":
                    self.signal_nuevo_lider.emit(item['user'])

    def efecto_trofeo(self, user):
        self.lbl_lider.setText(f"LÍDER ACTUAL: {user}")
        # Efecto visual simple
        self.trofeo.setStyleSheet("font-size: 90px; color: #f1c40f;")
        QTimer.singleShot(500, lambda: self.trofeo.setStyleSheet("font-size: 80px; color: white;"))

    def mostrar_especial(self, data):
        self.chat.append(f"<b style='color:#f1c40f;'>[EVENTO]: {data['msg']}</b>")

    def agregar_mensaje_chat(self, data):
        self.chat.append(f"<b style='color:#58a6ff;'>{data['user']}:</b> {data['msg']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = MaravillaGame()
    game.show()
    sys.exit(app.exec_())
