import sys, random, requests, socketio, threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class MaravillaGame(QWidget):
    signal_chat = pyqtSignal(dict)
    signal_ranking = pyqtSignal(list)
    signal_especial = pyqtSignal(dict)
    signal_stats = pyqtSignal(dict)
    signal_online = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.dificultad_actual = 3
        self.muted = False
        self.uid, ok = QInputDialog.getText(self, "Maravilla Hub", "Usuario TikTok:")
        if not ok or not self.uid: self.uid = "Invitado"

        self.puntos, self.monedas = 0, 0
        self.trivias, self.patron, self.secuencia_usuario = [], [], []
        self.sio = socketio.Client(reconnection=True)
        
        # Conexiones de señales
        self.signal_chat.connect(lambda d: self.chat_view.append(f"<b>{d['user']}:</b> {d['msg']}"))
        self.signal_ranking.connect(self.actualizar_ranking_ui)
        self.signal_especial.connect(self.ejecutar_evento_especial)
        self.signal_stats.connect(self.actualizar_datos_locales)
        self.signal_online.connect(lambda c: self.lbl_online.setText(f"👥 Online: {c}"))

        @self.sio.on('evento_especial')
        def on_esp(d): self.signal_especial.emit(d)
        @self.sio.on('update_ranking')
        def on_rank(d): self.signal_ranking.emit(d)
        @self.sio.on('update_stats')
        def on_stats(d): self.signal_stats.emit(d['stats'])
        @self.sio.on('usuarios_online')
        def on_online(c): self.signal_online.emit(c)

        self.init_ui()
        threading.Thread(target=self.conectar_servidor, daemon=True).start()
        self.conectar_datos()

    def init_ui(self):
        self.setWindowTitle(f"Maravilla Hub - @{self.uid}")
        self.setFixedSize(450, 850)
        self.setStyleSheet("background-color: #050505; color: white; font-family: 'Segoe UI';")
        lay = QVBoxLayout(self)

        self.rank_box = QLabel("🏆 RANKING"); self.rank_box.setFixedHeight(60); self.rank_box.setAlignment(Qt.AlignCenter)
        self.rank_box.setStyleSheet("background:#111; color:#ffee00; border:1px solid #ffee00; border-radius:10px; font-weight:bold;")
        lay.addWidget(self.rank_box)

        self.lbl_online = QLabel("👥 Online: 1"); self.lbl_online.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_online)

        self.lbl_stats = QLabel(); self.lbl_stats.setStyleSheet("font-size:18px; color:#00ffcc; font-weight:bold;")
        lay.addWidget(self.lbl_stats)

        grid = QGridLayout()
        self.btns = {}
        colores = [("Rojo","#ff0050"), ("Azul","#00f2ea"), ("Verde","#00ff88"), ("Amarillo","#ffee00")]
        for i, (n, c) in enumerate(colores):
            b = QPushButton(n); b.setFixedSize(130, 130); b.setEnabled(False)
            b.setStyleSheet(f"background:{c}; color:black; border-radius:65px; border:5px solid #000; font-weight:bold;")
            b.clicked.connect(lambda _, x=n: self.clic_color(x))
            self.btns[n] = b; grid.addWidget(b, i//2, i%2)
        lay.addLayout(grid)

        self.btn_gen = QPushButton("GENERAR PATRÓN (ENTER)"); self.btn_gen.setFixedHeight(50)
        self.btn_gen.setStyleSheet("background:white; color:black; font-weight:bold; border-radius:10px;")
        self.btn_gen.clicked.connect(self.iniciar_secuencia); lay.addWidget(self.btn_gen)

        self.tabs = QTabWidget(); lay.addWidget(self.tabs)
        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True); self.chat_view.setFixedHeight(120)
        lay.addWidget(self.chat_view)

    # --- CONTROL TECLADO 1,2,3,4 ---
    def keyPressEvent(self, event):
        keys = {Qt.Key_1: "Rojo", Qt.Key_2: "Azul", Qt.Key_3: "Verde", Qt.Key_4: "Amarillo"}
        if event.key() in keys:
            color = keys[event.key()]
            if self.btns[color].isEnabled(): self.clic_color(color)
        elif event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            if self.btn_gen.isEnabled(): self.iniciar_secuencia()

    def ejecutar_evento_especial(self, d):
        if d['tipo'] == 'input_externo':
            if self.btns[d['color']].isEnabled(): self.clic_color(d['color'])
        elif d['tipo'] == 'regalo':
            self.chat_view.append(f"<b style='color:gold;'>🎁 {d['user']} {d['msg']}</b>")

    def clic_color(self, c):
        if not self.muted: QApplication.beep()
        self.flash(c)
        self.secuencia_usuario.append(c)
        idx = len(self.secuencia_usuario) - 1
        if self.secuencia_usuario[idx] != self.patron[idx]:
            if self.sio.connected: self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': False})
            self.reset()
        elif len(self.secuencia_usuario) == len(self.patron):
            if self.sio.connected: self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': True})
            self.dificultad_actual += 1; self.reset()

    def iniciar_secuencia(self):
        self.btn_gen.setEnabled(False)
        self.patron = [random.choice(list(self.btns.keys())) for _ in range(self.dificultad_actual)]
        self.secuencia_usuario = []
        for i, color in enumerate(self.patron): QTimer.singleShot((i+1)*600, lambda x=color: self.flash(x))
        QTimer.singleShot((len(self.patron)+1)*600, self.activar_btns)

    def flash(self, c):
        orig = self.btns[c].styleSheet()
        self.btns[c].setStyleSheet(orig.replace("border:5px solid #000", "border:5px solid white"))
        QTimer.singleShot(250, lambda: self.btns[c].setStyleSheet(orig))

    def render_biblioteca(self):
        self.tabs.clear()
        cats = sorted(list(set([x['cat'] for x in self.trivias])))
        for cat in cats:
            sc = QScrollArea(); w = QWidget(); g = QGridLayout(w)
            for i, it in enumerate([x for x in self.trivias if x['cat'] == cat]):
                btn = QPushButton(f"{it['tit']}\n{it['costo']}M")
                btn.setFixedSize(115, 65)
                if cat == " Socios 🤝":
                    btn.setStyleSheet("background:gold; color:black; font-weight:bold; border:2px solid black;")
                btn.clicked.connect(lambda _, x=it: QDesktopServices.openUrl(QUrl(x['url'])))
                g.addWidget(btn, i//2, i%2)
            sc.setWidget(w); self.tabs.addTab(sc, cat)

    def actualizar_ranking_ui(self, r):
        if r:
            self.rank_box.setText(f"🏆 LÍDER: {r[0]['user']} ({r[0]['puntos']} XP)")

    def actualizar_datos_locales(self, stats):
        self.puntos, self.monedas = stats['puntos'], stats['monedas']
        self.lbl_stats.setText(f"💎 {self.monedas} | XP: {self.puntos} | Nv: {self.dificultad_actual}")

    def conectar_servidor(self):
        try: self.sio.connect("https://gamemaravilla-production.up.railway.app")
        except: pass

    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}, timeout=5).json()
            self.actualizar_datos_locales(r['stats'])
            self.trivias = r['trivias']; self.render_biblioteca()
        except: pass

    def activar_btns(self): [b.setEnabled(True) for b in self.btns.values()]
    def reset(self): [b.setEnabled(False) for b in self.btns.values()]; self.btn_gen.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv); ex = MaravillaGame(); ex.show(); sys.exit(app.exec_())
