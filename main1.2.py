import sys, random, requests, socketio, threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class MaravillaGame(QWidget):
    signal_resultado = pyqtSignal(dict)
    signal_chat = pyqtSignal(dict)
    signal_ranking = pyqtSignal(list)
    signal_online = pyqtSignal(int)
    signal_especial = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.dificultad_actual = 3
        self.muted = False
        self.uid, ok = QInputDialog.getText(self, "Maravilla Hub", "Usuario TikTok:")
        if not ok or not self.uid: self.uid = "Invitado"

        self.puntos, self.monedas = 0, 0
        self.trivias, self.logros_usuario, self.patron, self.secuencia_usuario = [], [], [], []
        self.sio = socketio.Client(reconnection=True)
        
        # Conexiones de señales
        self.signal_resultado.connect(self.procesar_resultado)
        self.signal_chat.connect(self.agregar_mensaje_chat)
        self.signal_ranking.connect(self.actualizar_ranking_ui)
        self.signal_online.connect(lambda c: self.lbl_online.setText(f"👥 Online: {c}"))
        self.signal_especial.connect(self.ejecutar_evento_especial)

        @self.sio.on('evento_especial')
        def on_esp(d): self.signal_especial.emit(d)
        @self.sio.on('update_ranking')
        def on_rank(d): self.signal_ranking.emit(d)
        @self.sio.on('resultado_trivia')
        def on_res(d): self.signal_resultado.emit(d)
        @self.sio.on('usuarios_online')
        def on_online(c): self.signal_online.emit(c)

        self.init_ui()
        threading.Thread(target=self.conectar_servidor, daemon=True).start()
        self.conectar_datos()

    def init_ui(self):
        self.setWindowTitle(f"Maravilla Hub - @{self.uid}")
        self.setFixedSize(450, 850)
        self.setStyleSheet("QWidget { background-color: #050505; color: white; font-family: 'Segoe UI'; }")
        lay = QVBoxLayout(self)

        # Ranking
        self.rank_box = QLabel("🏆 RANKING"); self.rank_box.setFixedHeight(60); self.rank_box.setAlignment(Qt.AlignCenter)
        self.rank_box.setStyleSheet("background:#0a0a0a; color:#ffee00; border:1px solid #ffee00; border-radius:10px; font-weight:bold; font-size:11pt;")
        lay.addWidget(self.rank_box)

        self.lbl_online = QLabel("👥 Online: 1"); self.lbl_online.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_online)

        # Header Stats
        header = QFrame(); header.setFixedHeight(50); header.setStyleSheet("background:#111; border-radius:10px; border:1px solid #00ffcc;")
        h_lay = QHBoxLayout(header)
        self.lbl_stats = QLabel(); h_lay.addWidget(self.lbl_stats)
        
        self.btn_mute = QPushButton("🔊"); self.btn_mute.setFixedSize(35, 30); self.btn_mute.clicked.connect(self.toggle_mute)
        h_lay.addWidget(self.btn_mute)

        btn_pay = QPushButton("💲 RECARGAR"); btn_pay.setStyleSheet("background:#ff0050; color:white; font-weight:bold; border-radius:5px; padding:5px;")
        btn_pay.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://PayPal.me/JohnnyOrregoVallejo")))
        h_lay.addWidget(btn_pay); lay.addWidget(header)

        # Matriz de botones (Donde estaba el error de clic_color)
        grid = QGridLayout()
        self.btns = {}
        colores = [("Rojo","#ff0050"), ("Azul","#00f2ea"), ("Verde","#00ff88"), ("Amarillo","#ffee00")]
        for i, (n, c) in enumerate(colores):
            b = QPushButton(n); b.setFixedSize(110, 110); b.setEnabled(False)
            b.setStyleSheet(f"background:{c}; color:black; border-radius:55px; border:4px solid #000; font-weight:bold;")
            # CORRECCIÓN: Llamada limpia al método clic_color
            b.clicked.connect(lambda _, x=n: self.clic_color(x))
            self.btns[n] = b; grid.addWidget(b, i//2, i%2)
        lay.addLayout(grid)

        self.btn_gen = QPushButton("GENERAR PATRÓN (ENTER)"); self.btn_gen.clicked.connect(self.iniciar_secuencia)
        self.btn_gen.setStyleSheet("background:white; color:black; font-weight:bold; height:45px; border-radius:10px;")
        lay.addWidget(self.btn_gen)

        # Biblioteca con Pestañas
        self.tabs = QTabWidget(); self.tabs.setStyleSheet("QTabBar::tab { background: #111; color: white; padding: 8px; } QTabBar::tab:selected { border-bottom: 2px solid #00ffcc; }")
        lay.addWidget(self.tabs)

        # Chat
        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True); self.chat_view.setFixedHeight(100)
        self.chat_in = QLineEdit(); self.chat_in.setPlaceholderText("Escribe aquí..."); self.chat_in.returnPressed.connect(self.enviar_chat)
        lay.addWidget(self.chat_view); lay.addWidget(self.chat_in)

    # --- MÉTODO CORREGIDO ---
    def clic_color(self, c):
        if not self.muted: QApplication.beep()
        self.flash(c)
        self.secuencia_usuario.append(c)
        
        # Lógica de validación
        idx = len(self.secuencia_usuario) - 1
        if self.secuencia_usuario[idx].capitalize() != self.patron[idx].capitalize():
            if self.sio.connected: self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': False})
            self.reset()
        elif len(self.secuencia_usuario) == len(self.patron):
            if self.sio.connected: self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': True})
            self.dificultad_actual += 1
            self.reset()

    def keyPressEvent(self, event):
        teclas = {Qt.Key_1: "Rojo", Qt.Key_2: "Azul", Qt.Key_3: "Verde", Qt.Key_4: "Amarillo"}
        if event.key() in teclas:
            color = teclas[event.key()]
            if self.btns[color].isEnabled(): self.clic_color(color)
        elif event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            if self.btn_gen.isEnabled(): self.iniciar_secuencia()

    def flash(self, c):
        orig = self.btns[c].styleSheet()
        self.btns[c].setStyleSheet(orig.replace("border:4px solid #000", "border:4px solid white"))
        QTimer.singleShot(250, lambda: self.btns[c].setStyleSheet(orig))

    def iniciar_secuencia(self):
        self.btn_gen.setEnabled(False)
        self.patron = [random.choice(list(self.btns.keys())) for _ in range(self.dificultad_actual)]
        self.secuencia_usuario = []
        for i, color in enumerate(self.patron): 
            QTimer.singleShot((i+1)*600, lambda x=color: self.flash(x))
        QTimer.singleShot((len(self.patron)+1)*600, self.activar_btns)

    def activar_btns(self): 
        for b in self.btns.values(): b.setEnabled(True)

    def reset(self): 
        for b in self.btns.values(): b.setEnabled(False)
        self.btn_gen.setEnabled(True)
        self.btn_gen.setText("GENERAR PATRÓN")

    def render_biblioteca(self):
        self.tabs.clear()
        cats = sorted(list(set([x['cat'] for x in self.trivias])))
        for cat in cats:
            sc = QScrollArea(); sc.setWidgetResizable(True); w = QWidget(); g = QGridLayout(w); w.setStyleSheet("background: #000;")
            for i, item in enumerate([x for x in self.trivias if x['cat'] == cat]):
                ya = item['id'] in self.logros_usuario
                btn = QPushButton(f"{item['tit']}\n[OK]" if ya else f"{item['tit']}\n{item['costo']}M")
                btn.setFixedSize(110, 55)
                btn.setStyleSheet(f"background:{'#004422' if ya else '#111'}; color:white; border:1px solid #00ff88; border-radius:5px;")
                if not ya: btn.clicked.connect(lambda _, x=item: self.pedir_trivia(x))
                g.addWidget(btn, i//2, i%2)
            sc.setWidget(w); self.tabs.addTab(sc, cat)

    def pedir_trivia(self, item):
        if self.monedas >= item['costo']:
            QDesktopServices.openUrl(QUrl(item['url']))
            res, ok = QInputDialog.getText(self, "Trivia", item['preg'])
            if ok and res and self.sio.connected: 
                self.sio.emit('verificar_trivia', {'user': self.uid, 'trivia_id': item['id'], 'respuesta': res})

    def actualizar_ranking_ui(self, rank_list):

        if not rank_list: return

        l1 = "🏆 " + " | ".join([f"#{i+1} {e['user']}({e['puntos']})" for i, e in enumerate(rank_list[:2])])
        l2 = " | ".join([f"#{i+3} {e['user']}({e['puntos']})" for i, e in enumerate(rank_list[2:])])
        self.rank_box.setText(f"{l1}\n{l2}")
        
    def actualizar_ui(self): 
        self.lbl_stats.setText(f"💎 {self.monedas} | XP: {self.puntos} | Nivel: {self.dificultad_actual}")

    def toggle_mute(self): 
        self.muted = not self.muted
        self.btn_mute.setText("🔇" if self.muted else "🔊")

    def procesar_resultado(self, d):
        if d.get('success'):
            self.puntos, self.monedas = d['stats']['puntos'], d['stats']['monedas']
            if d.get('id_completado'): self.logros_usuario.append(d['id_completado'])
            self.actualizar_ui(); self.render_biblioteca()

    def agregar_mensaje_chat(self, d): 
        self.chat_view.append(f"<b>{d['user']}:</b> {d['msg']}")

    def ejecutar_evento_especial(self, d):
        if d['tipo'] == 'regalo': 
            self.chat_view.append(f"<b style='color:gold;'>🎁 {d['user']} {d['msg']}</b>")

    def enviar_chat(self):
        if self.chat_in.text() and self.sio.connected:
            self.sio.emit('enviar_mensaje', {'user': self.uid, 'msg': self.chat_in.text()})
            self.chat_in.clear()

    def conectar_servidor(self): 
        try: self.sio.connect("https://gamemaravilla-production.up.railway.app")
        except: pass

    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}).json()
            self.puntos, self.monedas = r['stats']['puntos'], r['stats']['monedas']
            self.logros_usuario, self.trivias = r['stats'].get('logros', []), r.get('trivias', [])
            self.actualizar_ui(); self.render_biblioteca()
        except: pass

if __name__ == '__main__':
    app = QApplication(sys.argv); ex = MaravillaGame(); ex.show(); sys.exit(app.exec_())
