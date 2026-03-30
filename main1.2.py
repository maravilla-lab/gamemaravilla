import sys, random, requests, socketio, threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class MaravillaGame(QWidget):
    signal_res = pyqtSignal(dict)
    signal_rank = pyqtSignal(list)
    signal_esp = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.muted = False
        self.uid, ok = QInputDialog.getText(self, "Maravilla Hub", "Usuario Admin:")
        if not ok or not self.uid: self.uid = "Invitado"
        
        self.puntos, self.monedas, self.dificultad_actual = 0, 0, 3
        self.trivias, self.logros_usuario, self.patron, self.secuencia_usuario = [], [], [], []
        self.sio = socketio.Client(reconnection=True)
        
        # Conexión de Señales
        self.signal_res.connect(self.procesar_resultado)
        self.signal_rank.connect(self.actualizar_ranking_ui)
        self.signal_esp.connect(lambda d: self.chat_view.append(f"<b style='color:gold;'>🎁 {d['user']} {d['msg']}</b>"))

        @self.sio.on('update_stats')
        def on_s(d): self.signal_res.emit(d)
        @self.sio.on('resultado_trivia')
        def on_tr(d): self.signal_res.emit(d)
        @self.sio.on('comando_mision')
        def on_cmd(d): self.sio.emit('verificar_trivia', {'user': d['user'], 'trivia_id': d['tid'], 'respuesta': d['res']})
        @self.sio.on('update_ranking')
        def on_rk(d): self.signal_rank.emit(d)
        @self.sio.on('evento_especial')
        def on_e(d): self.signal_esp.emit(d)

        self.init_ui()
        threading.Thread(target=self.conectar_servidor, daemon=True).start()
        self.conectar_datos()
        
        # Timer de Rotación Automática (20 segundos)
        self.timer_rotar = QTimer()
        self.timer_rotar.timeout.connect(self.rotar_biblioteca)
        self.timer_rotar.start(20000)

    def init_ui(self):
        self.setWindowTitle("Maravilla Hub")
        self.setFixedSize(450, 750) # Tamaño solicitado
        self.setStyleSheet("QWidget { background-color: #050505; color: white; font-family: 'Segoe UI'; }")
        lay = QVBoxLayout(self)

        # Ranking en dos líneas (Top 5)
        self.rank_box = QLabel("🏆 RANKING..."); self.rank_box.setFixedHeight(70); self.rank_box.setAlignment(Qt.AlignCenter)
        self.rank_box.setStyleSheet("background:#111; color:#ffee00; border:2px solid #ffee00; border-radius:10px; font-weight:bold; font-size:10pt;")
        lay.addWidget(self.rank_box)

        # Header con Mute y Recarga
        header = QFrame(); header.setFixedHeight(50); header.setStyleSheet("background:#111; border:1px solid #00ffcc; border-radius:10px;")
        h_lay = QHBoxLayout(header)
        self.lbl_stats = QLabel(); h_lay.addWidget(self.lbl_stats)
        self.btn_mute = QPushButton("🔊"); self.btn_mute.setFixedSize(35, 30); self.btn_mute.clicked.connect(self.toggle_mute); h_lay.addWidget(self.btn_mute)
        btn_pay = QPushButton("💲 RECARGAR"); btn_pay.setStyleSheet("background:#ff0050; font-weight:bold;"); btn_pay.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://PayPal.me/JohnnyOrregoVallejo"))); h_lay.addWidget(btn_pay)
        lay.addWidget(header)

        # Matriz de Botones
        grid = QGridLayout()
        self.btns = {}
        for i, (n, c) in enumerate([("Rojo","#ff0050"), ("Azul","#00f2ea"), ("Verde","#00ff88"), ("Amarillo","#ffee00")]):
            b = QPushButton(n); b.setFixedSize(110, 110); b.setEnabled(False)
            b.setStyleSheet(f"background:{c}; color:black; border-radius:55px; border:4px solid #000; font-weight:bold;")
            b.clicked.connect(lambda _, x=n: self.clic_color(x)); self.btns[n] = b; grid.addWidget(b, i//2, i%2)
        lay.addLayout(grid)

        self.btn_gen = QPushButton("GENERAR PATRÓN (ENTER)"); self.btn_gen.setFixedHeight(45); self.btn_gen.clicked.connect(self.iniciar_secuencia); lay.addWidget(self.btn_gen)
        
        # Biblioteca de Trivias
        self.tabs = QTabWidget(); self.tabs.setStyleSheet("QTabBar::tab { background:#111; color:white; padding:8px; } QTabBar::tab:selected { border-bottom: 2px solid #00ffcc; }")
        lay.addWidget(self.tabs)

        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True); self.chat_view.setFixedHeight(100); lay.addWidget(self.chat_view)

    def clic_color(self, c):
        if not self.muted: QApplication.beep()
        self.flash(c); self.secuencia_usuario.append(c)
        idx = len(self.secuencia_usuario) - 1
        if self.secuencia_usuario[idx].lower() != self.patron[idx].lower():
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': False}); self.reset()
        elif len(self.secuencia_usuario) == len(self.patron):
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': True}); self.reset()

    def procesar_resultado(self, d):
        if 'stats' in d:
            self.puntos, self.monedas = d['stats']['puntos'], d['stats']['monedas']
            self.logros_usuario = d['stats'].get('logros', [])
            if 'dificultad' in d: self.dificultad_actual = d['dificultad']
            self.lbl_stats.setText(f"💎 {self.monedas} | XP: {self.puntos} | Nv: {self.dificultad_actual}")
            self.render_biblioteca()

    def render_biblioteca(self):
        curr = self.tabs.currentIndex()
        self.tabs.clear()
        cats = sorted(list(set([x['cat'] for x in self.trivias])))
        for cat in cats:
            sc = QScrollArea(); sc.setWidgetResizable(True); w = QWidget(); g = QGridLayout(w); w.setStyleSheet("background:#000;")
            for i, it in enumerate([x for x in self.trivias if x['cat'] == cat]):
                ya = it['id'] in self.logros_usuario
                btn = QPushButton(f"{it['tit']}\n[OK]" if ya else f"{it['tit']}\n{it['costo']}M")
                btn.setFixedSize(110, 55); btn.setStyleSheet(f"background:{'#004422' if ya else '#111'}; color:white; border:1px solid #00ff88; border-radius:5px;")
                g.addWidget(btn, i//2, i%2)
            sc.setWidget(w); self.tabs.addTab(sc, cat)
        if curr >= 0: self.tabs.setCurrentIndex(curr)

    def rotar_biblioteca(self):
        count = self.tabs.count()
        if count > 0:
            next_idx = (self.tabs.currentIndex() + 1) % count
            self.tabs.setCurrentIndex(next_idx)

    def actualizar_ranking_ui(self, rank_list):
        if not rank_list: return
        l1 = "🏆 " + " | ".join([f"#{i+1} {e['user']}({e['puntos']})" for i, e in enumerate(rank_list[:2])])
        l2 = " | ".join([f"#{i+3} {e['user']}({e['puntos']})" for i, e in enumerate(rank_list[2:])])
        self.rank_box.setText(f"{l1}\n{l2}")

    def toggle_mute(self): self.muted = not self.muted; self.btn_mute.setText("🔇" if self.muted else "🔊")
    def flash(self, c):
        orig = self.btns[c].styleSheet()
        self.btns[c].setStyleSheet(orig.replace("border:4px solid #000", "border:4px solid white"))
        QTimer.singleShot(250, lambda: self.btns[c].setStyleSheet(orig))
    def conectar_servidor(self): 
        try: self.sio.connect("https://gamemaravilla-production.up.railway.app")
        except: pass
    def conectar_datos(self):
        try:
            r = requests.post("https://gamemaravilla-production.up.railway.app/login", json={"id": self.uid}, timeout=5).json()
            self.procesar_resultado(r); self.actualizar_ranking_ui(r['ranking'])
        except: pass
    def iniciar_secuencia(self):
        self.btn_gen.setEnabled(False); self.patron = [random.choice(list(self.btns.keys())) for _ in range(self.dificultad_actual)]
        self.secuencia_usuario = []
        for i, color in enumerate(self.patron): QTimer.singleShot((i+1)*600, lambda x=color: self.flash(x))
        QTimer.singleShot((len(self.patron)+1)*600, lambda: [b.setEnabled(True) for b in self.btns.values()])
    def reset(self): [b.setEnabled(False) for b in self.btns.values()]; self.btn_gen.setEnabled(True); self.btn_gen.setText("GENERAR PATRÓN")

if __name__ == '__main__':
    app = QApplication(sys.argv); ex = MaravillaGame(); ex.show(); sys.exit(app.exec_())
