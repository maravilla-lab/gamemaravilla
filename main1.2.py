import sys, random, requests, socketio, threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class MaravillaGame(QWidget):
    signal_resultado = pyqtSignal(dict)
    signal_ranking = pyqtSignal(list)
    signal_chat = pyqtSignal(dict)
    signal_auto_click = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.muted = False
        self.uid, ok = QInputDialog.getText(self, "Maravilla Hub", "Usuario Admin TikTok:")
        self.uid = self.uid.lower().strip() if ok else "invitado"
        
        self.puntos, self.monedas, self.dificultad_actual = 0, 0, 3
        self.trivias, self.logros_usuario, self.patron, self.secuencia_usuario = [], [], [], []
        
        self.init_ui()
        
        self.sio = socketio.Client(reconnection=True)
        self.signal_resultado.connect(self.procesar_resultado)
        self.signal_ranking.connect(self.actualizar_ranking_ui)
        self.signal_chat.connect(lambda d: self.chat_view.append(f"<b>{d['user']}:</b> {d['msg']}"))
        self.signal_auto_click.connect(self.iniciar_secuencia)

        @self.sio.on('update_stats')
        def on_s(d): self.signal_resultado.emit(d)
        @self.sio.on('update_ranking')
        def on_rk(d): self.signal_ranking.emit(d)
        @self.sio.on('toggle_auto')
        def on_auto(d): 
            if d['active']: self.timer_auto.start(15000)
            else: self.timer_auto.stop()
        @self.sio.on('recibir_mensaje')
        def on_msg(d): self.signal_chat.emit(d)
        @self.sio.on('evento_especial')
        def on_e(d): self.chat_view.append(f"<b style='color:#00ffcc;'>✨ {d['msg']}</b>")

        threading.Thread(target=self.conectar_servidor, daemon=True).start()
        self.conectar_datos()

        self.timer_rotar = QTimer(); self.timer_rotar.timeout.connect(self.rotar_biblioteca); self.timer_rotar.start(20000)
        self.timer_auto = QTimer(); self.timer_auto.timeout.connect(lambda: self.signal_auto_click.emit())

    def init_ui(self):
        self.setWindowTitle(f"Maravilla Hub - @{self.uid}")
        self.setFixedSize(450, 780)
        self.setStyleSheet("QWidget { background-color: #050505; color: white; font-family: 'Segoe UI'; }")
        lay = QVBoxLayout(self)

        # Ranking
        self.rank_box = QLabel("🏆 RANKING..."); self.rank_box.setFixedHeight(80); self.rank_box.setAlignment(Qt.AlignCenter)
        self.rank_box.setStyleSheet("background:#111; color:#ffee00; border:2px solid #ffee00; border-radius:10px; font-weight:bold;")
        lay.addWidget(self.rank_box)

        # Stats + Mute
        header = QFrame(); header.setFixedHeight(50); header.setStyleSheet("background:#111; border:1px solid #00ffcc; border-radius:10px;")
        h_lay = QHBoxLayout(header)
        self.lbl_stats = QLabel("💎 -- | XP: --"); h_lay.addWidget(self.lbl_stats)
        
        self.btn_mute = QPushButton("🔊"); self.btn_mute.setFixedSize(40, 40); self.btn_mute.clicked.connect(self.toggle_mute)
        self.btn_mute.setStyleSheet("background:#222; border-radius:5px;")
        h_lay.addWidget(self.btn_mute)
        
        btn_pay = QPushButton("💲 RECARGAR"); btn_pay.setStyleSheet("background:#ff0050; font-weight:bold; color:white; border-radius:5px;"); btn_pay.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://PayPal.me/JohnnyOrregoVallejo"))); h_lay.addWidget(btn_pay)
        lay.addWidget(header)

        # Botones de juego
        grid = QGridLayout()
        self.btns = {}
        colores = [("Rojo","#ff0050"), ("Azul","#00f2ea"), ("Verde","#00ff88"), ("Amarillo","#ffee00")]
        for i, (n, c) in enumerate(colores):
            b = QPushButton(n); b.setFixedSize(110, 110); b.setEnabled(False)
            b.setStyleSheet(f"background:{c}; color:black; border-radius:55px; border:4px solid #000; font-weight:bold;")
            b.clicked.connect(lambda _, x=n: self.clic_color(x)); self.btns[n] = b; grid.addWidget(b, i//2, i%2)
        lay.addLayout(grid)

        self.btn_gen = QPushButton("GENERAR PATRÓN (ENTER)"); self.btn_gen.setFixedHeight(45); self.btn_gen.clicked.connect(self.iniciar_secuencia); lay.addWidget(self.btn_gen)
        
        # Biblioteca (Negro)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #333; } QTabBar::tab { background: #000; color: #fff; padding: 10px; } QTabBar::tab:selected { background: #111; border-bottom: 2px solid #00ffcc; }")
        lay.addWidget(self.tabs)
        
        # Chat e Input
        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True); self.chat_view.setFixedHeight(100); lay.addWidget(self.chat_view)
        self.chat_in = QLineEdit(); self.chat_in.setPlaceholderText("Chat..."); self.chat_in.returnPressed.connect(self.enviar_chat); lay.addWidget(self.chat_in)

    def toggle_mute(self):
        self.muted = not self.muted
        self.btn_mute.setText("🔇" if self.muted else "🔊")

    def clic_color(self, c):
        if not self.muted: QApplication.beep()
        self.flash(c); self.secuencia_usuario.append(c)
        if self.secuencia_usuario[-1].lower() != self.patron[len(self.secuencia_usuario)-1].lower():
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': False}); self.reset()
        elif len(self.secuencia_usuario) == len(self.patron):
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': True}); self.reset()

    def procesar_resultado(self, d):
        if 'stats' in d:
            self.puntos, self.monedas = d['stats']['puntos'], d['stats']['monedas']
            self.logros_usuario = d['stats'].get('logros', [])
            self.dificultad_actual = d.get('dificultad', self.dificultad_actual)
            self.lbl_stats.setText(f"💎 {self.monedas} | XP: {self.puntos} | Nv: {self.dificultad_actual}"); self.render_biblioteca()

    def render_biblioteca(self):
        curr = self.tabs.currentIndex(); self.tabs.clear()
        cats = sorted(list(set([x['cat'] for x in self.trivias])))
        for cat in cats:
            sc = QScrollArea(); sc.setWidgetResizable(True); w = QWidget(); g = QGridLayout(w); w.setStyleSheet("background:#000;")
            for i, it in enumerate([x for x in self.trivias if x['cat'] == cat]):
                ya = it['id'] in self.logros_usuario
                btn = QPushButton(f"ID:{it['id']}\n{it['tit']}\n[OK]" if ya else f"ID:{it['id']}\n{it['tit']}\n{it['costo']}M")
                btn.setFixedSize(110, 55); btn.setStyleSheet(f"background:{'#004422' if ya else '#111'}; color:white; border:1px solid #00ff88; border-radius:5px;")
                g.addWidget(btn, i//2, i%2)
            sc.setWidget(w); self.tabs.addTab(sc, cat)
        if curr >= 0 and curr < self.tabs.count(): self.tabs.setCurrentIndex(curr)

    def actualizar_ranking_ui(self, r):
        if not r: return
        l1 = "🏆 " + " | ".join([f"#{i+1} {e['user']}({e['puntos']})" for i, e in enumerate(r[:2])])
        l2 = " | ".join([f"#{i+3} {e['user']}({e['puntos']})" for i, e in enumerate(r[2:])])
        self.rank_box.setText(f"{l1}\n{l2}")

    def flash(self, c):
        b = self.btns[c]; orig = b.styleSheet(); b.setStyleSheet(orig.replace("border:4px solid #000", "border:4px solid white"))
        QTimer.singleShot(250, lambda: b.setStyleSheet(orig))

    def iniciar_secuencia(self):
        if not self.btn_gen.isEnabled(): return
        self.btn_gen.setEnabled(False); self.patron = [random.choice(list(self.btns.keys())) for _ in range(self.dificultad_actual)]
        self.secuencia_usuario = []
        for i, color in enumerate(self.patron): QTimer.singleShot((i+1)*600, lambda x=color: self.flash(x))
        QTimer.singleShot((len(self.patron)+1)*600, self.activar_btns)

    def activar_btns(self):
        for b in self.btns.values(): b.setEnabled(True)

    def enviar_chat(self):
        txt = self.chat_in.text().strip()
        if txt.startswith("#97"):
            users = txt.split()[1:]
            self.sio.emit('comando_masivo_97', {'users': users})
        else:
            self.sio.emit('enviar_mensaje', {'user': self.uid, 'msg': txt})
        self.chat_in.clear()

    def reset(self): [b.setEnabled(False) for b in self.btns.values()]; self.btn_gen.setEnabled(True)
    def rotar_biblioteca(self):
        if self.tabs.count() > 0: self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())
    def conectar_servidor(self): 
        try: self.sio.connect("https://gamemaravilla-production.up.railway.app")
        except: pass
    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}, timeout=5).json()
            self.trivias = r.get('trivias', []); self.procesar_resultado(r)
        except: pass

if __name__ == '__main__':
    app = QApplication(sys.argv); ex = MaravillaGame(); ex.show(); sys.exit(app.exec_())
