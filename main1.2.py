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
        # TAMAÑO COMPACTO ORIGINAL
        self.setFixedSize(450, 780)
        self.setWindowTitle("Maravilla Hub")
        self.dificultad_actual = 3
        
        self.uid, ok = QInputDialog.getText(self, "Maravilla Hub", "Usuario TikTok:")
        if not ok or not self.uid: self.uid = "Invitado"

        self.puntos, self.monedas = 0, 0
        # CORREGIDO: 4 variables para 4 listas
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

        # Ciclo automático de 10 segundos
        self.timer_ciclo = QTimer()
        self.timer_ciclo.timeout.connect(self.generar_patron)
        self.timer_ciclo.start(10000) 

    def init_ui(self):
        self.setStyleSheet("background-color: black; color: white; font-family: Segoe UI;")
        layout = QVBoxLayout()

        stats = QHBoxLayout()
        self.lbl_user = QLabel(f"👤 {self.uid}")
        self.lbl_puntos = QLabel("XP: 0")
        self.lbl_monedas = QLabel("💰: 0")
        self.lbl_online = QLabel("Online: 0")
        [l.setStyleSheet("font-weight: bold; font-size: 13px; color: #25f4ee;") for l in [self.lbl_user, self.lbl_puntos, self.lbl_monedas, self.lbl_online]]
        stats.addWidget(self.lbl_user); stats.addStretch(); stats.addWidget(self.lbl_puntos); stats.addWidget(self.lbl_monedas); stats.addWidget(self.lbl_online)
        layout.addLayout(stats)

        self.trofeo = QLabel("🏆")
        self.trofeo.setAlignment(Qt.AlignCenter)
        self.trofeo.setStyleSheet("font-size: 50px; margin: 5px;")
        layout.addWidget(self.trofeo)
        
        self.lbl_lider = QLabel("LÍDER: ---")
        self.lbl_lider.setAlignment(Qt.AlignCenter)
        self.lbl_lider.setStyleSheet("color: #f1c40f; font-weight: bold;")
        layout.addWidget(self.lbl_lider)

        self.display_patron = QHBoxLayout()
        self.bolas = [QLabel() for _ in range(6)]
        for b in self.bolas:
            b.setFixedSize(40, 40)
            b.setStyleSheet("background: #1a1a1a; border-radius: 20px; border: 1px solid #333;")
            self.display_patron.addWidget(b)
        layout.addLayout(self.display_patron)

        grid = QGridLayout()
        colores = {"rojo": "#fe2c55", "azul": "#25f4ee", "verde": "#3fb950", "amarillo": "#f1c40f"}
        for i, (name, hex) in enumerate(colores.items()):
            btn = QPushButton(f"{i+1}")
            btn.setFixedSize(85, 85)
            btn.setStyleSheet(f"background: {hex}; color: black; border-radius: 42px; font-weight: bold; font-size: 18px;")
            btn.clicked.connect(lambda _, n=name: self.registrar_secuencia(n))
            grid.addWidget(btn, 0, i)
        layout.addLayout(grid)

        layout.addWidget(QLabel("🏆 RANKING"))
        self.lista_rank = QListWidget()
        self.lista_rank.setFixedHeight(120)
        layout.addWidget(self.lista_rank)

        layout.addWidget(QLabel("📚 TRIVIAS"))
        self.lista_trivias = QListWidget()
        self.lista_trivias.setFixedHeight(120)
        layout.addWidget(self.lista_trivias)

        self.setLayout(layout)

    def conectar_sio(self):
        @self.sio.on('update_ranking')
        def on_rank(data): self.signal_ranking.emit(data)
        @self.sio.on('intento_usuario')
        def on_intento(data): self.signal_chat.emit(data)
        threading.Thread(target=lambda: self.sio.connect("https://gamemaravilla-production.up.railway.app"), daemon=True).start()

    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}).json()
            self.puntos, self.monedas = r['stats']['puntos'], r['stats']['monedas']
            self.trivias = r.get('trivias', [])
            self.actualizar_ui(); self.render_biblioteca()
        except: pass

    def generar_patron(self):
        self.secuencia_usuario = []
        self.patron = [random.choice(["rojo", "azul", "verde", "amarillo"]) for _ in range(self.dificultad_actual)]
        for i, color in enumerate(self.patron):
            QTimer.singleShot(i * 500, lambda c=color, idx=i: self.animar_bola(idx, c))

    def animar_bola(self, idx, color):
        hex_c = {"rojo": "#fe2c55", "azul": "#25f4ee", "verde": "#3fb950", "amarillo": "#f1c40f"}[color]
        self.bolas[idx].setStyleSheet("background: white; border-radius: 20px;")
        QTimer.singleShot(300, lambda: self.bolas[idx].setStyleSheet(f"background: {hex_c}; border-radius: 20px; border: 1px solid white;"))
        if idx == len(self.patron)-1: QTimer.singleShot(1500, self.ocultar_patron)

    def ocultar_patron(self):
        for b in self.bolas: b.setStyleSheet("background: #1a1a1a; border-radius: 20px; border: 1px solid #333;")

    def registrar_secuencia(self, color):
        self.secuencia_usuario.append(color)
        if len(self.secuencia_usuario) == len(self.patron):
            exito = self.secuencia_usuario == self.patron
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': exito})
            QTimer.singleShot(500, self.conectar_datos)

    def procesar_resultado(self, data):
        self.puntos, self.monedas = data['stats']['puntos'], data['stats']['monedas']
        self.actualizar_ui()

    def actualizar_ui(self):
        self.lbl_puntos.setText(f"XP: {self.puntos}"); self.lbl_monedas.setText(f"💰: {self.monedas}")

    def render_biblioteca(self):
        self.lista_trivias.clear()
        for t in self.trivias: self.lista_trivias.addItem(f"{t['tit']} ({t['costo']}💰)")

    def actualizar_ranking_ui(self, rank):
        self.lista_rank.clear()
        for i, item in enumerate(rank[:5]):
            self.lista_rank.addItem(f"{i+1}. {item['user']} - {item['puntos']} XP")

    def efecto_trofeo(self, user):
        self.lbl_lider.setText(f"LÍDER: {user}")
        self.trofeo.setStyleSheet("font-size: 60px; color: #f1c40f;")
        QTimer.singleShot(500, lambda: self.trofeo.setStyleSheet("font-size: 50px; color: white;"))

    def mostrar_especial(self, d): pass
    def agregar_mensaje_chat(self, d): pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = MaravillaGame()
    game.show()
    sys.exit(app.exec_())
