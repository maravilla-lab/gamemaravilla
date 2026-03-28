import sys, random, requests, socketio, threading, time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# --- ESTILOS CSS ORIGINALES (Recuperados) ---
STYLE_SHEET = """
QWidget { background-color: black; color: white; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
QLabel { color: white; border: none; }
QPushButton { background-color: #25f4ee; color: black; border: none; border-radius: 5px; font-weight: bold; padding: 8px; }
QPushButton:hover { background-color: #20d4ce; }
QPushButton:pressed { background-color: #fe2c55; color: white; }
QLineEdit { background-color: #1a1a1a; border: 1px solid #333; border-radius: 3px; padding: 5px; color: white; }
QListWidget { background-color: #1a1a1a; border: 1px solid #333; border-radius: 3px; color: #ccc; }
QTextEdit { background-color: #1a1a1a; border: 1px solid #333; border-radius: 3px; color: #ccc; }
QProgressBar { border: 1px solid #333; border-radius: 3px; text-align: center; color: black; }
QProgressBar::chunk { background-color: #3fb950; }
"""

class MaravillaGame(QWidget):
    # Señales para comunicación segura entre hilos
    signal_resultado = pyqtSignal(dict)
    signal_chat = pyqtSignal(dict)
    signal_ranking = pyqtSignal(list)
    signal_online = pyqtSignal(int)
    signal_especial = pyqtSignal(dict)
    signal_nuevo_lider = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        # Configuración Compacta Original (Volvemos a 800x600 o similar)
        self.setFixedSize(950, 650) 
        self.setWindowTitle("Portal Maravilla Hub - Live 24H")
        self.setStyleSheet(STYLE_SHEET)

        self.uid = "portal.maravilla"
        self.puntos, self.monedas = 0, 0
        self.trivias, self.patron, self.secuencia_usuario = [], [], []
        self.sio = socketio.Client()
        self.dificultad_actual = 3

        # Conexiones de señales
        self.signal_resultado.connect(self.procesar_resultado)
        self.signal_chat.connect(self.agregar_mensaje_chat)
        self.signal_ranking.connect(self.actualizar_ranking_ui)
        self.signal_especial.connect(self.mostrar_especial)
        self.signal_nuevo_lider.connect(self.efecto_trofeo)

        self.init_ui()
        self.conectar_sio()
        self.conectar_datos()

        # Temporizador para el ciclo automático de 10 segundos
        self.timer_ciclo = QTimer()
        self.timer_ciclo.timeout.connect(self.generar_patron)
        self.timer_ciclo.start(10000) 

    def init_ui(self):
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        
        # --- HEADER (STATS) ---
        header = QHBoxLayout()
        self.lbl_user = QLabel(f"👤 {self.uid}")
        self.lbl_puntos = QLabel("XP: 0")
        self.lbl_monedas = QLabel("💰: 0")
        [l.setStyleSheet("font-weight: bold; color: #25f4ee;") for l in [self.lbl_user, self.lbl_puntos, self.lbl_monedas]]
        header.addWidget(self.lbl_user); header.addStretch(); header.addWidget(self.lbl_puntos); header.addWidget(self.lbl_monedas)
        left_layout.addLayout(header)

        # --- ÁREA CENTRAL (TROFEO Y LÍDER) ---
        self.trofeo = QLabel("🏆")
        self.trofeo.setAlignment(Qt.AlignCenter)
        self.trofeo.setStyleSheet("font-size: 70px; margin: 5px;")
        left_layout.addWidget(self.trofeo)

        self.lbl_lider = QLabel("LÍDER: ---")
        self.lbl_lider.setAlignment(Qt.AlignCenter)
        self.lbl_lider.setStyleSheet("color: #f1c40f; font-weight: bold; font-size: 18px;")
        left_layout.addWidget(self.lbl_lider)

        # --- VISUALIZADOR DE PATRÓN (Estilo Compacto Original) ---
        self.display_patron = QHBoxLayout()
        self.display_patron.setAlignment(Qt.AlignCenter)
        self.bolas = [QLabel() for _ in range(6)]
        for b in self.bolas:
            b.setFixedSize(50, 50); b.setStyleSheet("background: #1a1a1a; border-radius: 25px; border: 2px solid #333;")
            self.display_patron.addWidget(b)
        left_layout.addLayout(self.display_patron)

        self.leyenda = QLabel("1:ROJO | 2:AZUL | 3:VERDE | 4:AMARILLO")
        self.leyenda.setAlignment(Qt.AlignCenter)
        self.leyenda.setStyleSheet("color: #888; font-size: 12px; margin-top: 5px;")
        left_layout.addWidget(self.leyenda)

        # --- BOTONES DE COLORES (Colores TikTok) ---
        grid = QGridLayout()
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)
        self.btns = {}
        # Colores exactos de TikTok
        colores_hex = {"rojo": "#fe2c55", "azul": "#25f4ee", "verde": "#3fb950", "amarillo": "#f1c40f"}
        for i, (name, hex_c) in enumerate(colores_hex.items()):
            btn = QPushButton(f"{i+1}") 
            btn.setFixedSize(100, 100)
            # Volvemos al estilo original de los botones
            btn.setStyleSheet(f"background-color: {hex_c}; color: black; border-radius: 50px; font-size: 22px; font-weight: bold; border: 2px solid black;")
            btn.clicked.connect(lambda _, n=name: self.registrar_secuencia(n))
            self.btns[name] = btn
            grid.addWidget(btn, 0, i)
        left_layout.addLayout(grid)
        
        main_layout.addLayout(left_layout, 2)

        # --- PANEL DERECHO (BIBLIOTECA DE TRIVIAS Y RANKING) ---
        right_layout = QVBoxLayout()
        
        # Biblioteca de Trivias Maestras (Recuperada)
        lbl_trivias = QLabel("📚 BIBLIOTECA MAESTRA")
        lbl_trivias.setStyleSheet("font-weight: bold; color: #25f4ee; margin-top: 10px;")
        right_layout.addWidget(lbl_trivias)
        self.lista_trivias = QListWidget()
        right_layout.addWidget(self.lista_trivias)

        # Ranking Global
        lbl_rank = QLabel("🏆 RANKING GLOBAL")
        lbl_rank.setStyleSheet("font-weight: bold; color: #f1c40f; margin-top: 10px;")
        right_layout.addWidget(lbl_rank)
        self.lista_rank = QListWidget()
        right_layout.addWidget(self.lista_rank)

        main_layout.addLayout(right_layout, 1)
        self.setLayout(main_layout)

    # --- LÓGICA DE CONEXIÓN (Inyectada silenciosamente) ---
    def conectar_sio(self):
        @self.sio.on('connect')
        def on_connect(): print("SIO: Conectado a Railway")

        @self.sio.on('update_ranking')
        def on_rank(data): self.signal_ranking.emit(data)

        @self.sio.on('intento_usuario')
        def on_intento(data):
            # Recibe lo que la gente escribe en TikTok
            self.signal_chat.emit({'user': data['user'], 'msg': f"marcó {data['color']}"})

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
            self.trivias = r.get('trivias', []) # Recuperamos las trivias
            self.signal_ranking.emit(r.get('ranking', []))
            self.actualizar_ui()
            self.render_biblioteca() # Renderizamos las trivias
        except: pass

    # --- MECÁNICAS DE JUEGO (Recuperado el parpadeo en blanco) ---
    def generar_patron(self):
        self.secuencia_usuario = []
        self.patron = [random.choice(["rojo", "azul", "verde", "amarillo"]) for _ in range(self.dificultad_actual)]
        self.mostrar_secuencia(0)

    def mostrar_secuencia(self, index):
        if index < len(self.patron):
            color = self.patron[index]
            # Usamos los colores exactos de TikTok para el patrón
            hex_c = {"rojo": "#fe2c55", "azul": "#25f4ee", "verde": "#3fb950", "amarillo": "#f1c40f"}[color]
            
            # Recuperado el efecto de parpadeo en blanco original
            self.bolas[index].setStyleSheet(f"background: white; border-radius: 25px; border: 2px solid white;")
            
            # Volver al color original después de un breve momento
            QTimer.singleShot(250, lambda i=index, hc=hex_c: self.bolas[i].setStyleSheet(f"background: {hc}; border-radius: 25px; border: 2px solid white;"))
            
            # Siguiente color después de un intervalo
            QTimer.singleShot(600, lambda: self.mostrar_secuencia(index + 1))
        else:
            # Ocultar patrón después de mostrarlo para que memoricen
            QTimer.singleShot(500, self.ocultar_patron)

    def ocultar_patron(self):
        for b in self.bolas: b.setStyleSheet("background: #1a1a1a; border-radius: 25px; border: 2px solid #333;")

    def registrar_secuencia(self, color):
        self.secuencia_usuario.append(color)
        # Mostrar visualmente el clic
        idx = len(self.secuencia_usuario) - 1
        if idx < len(self.bolas):
            hex_c = {"rojo": "#fe2c55", "azul": "#25f4ee", "verde": "#3fb950", "amarillo": "#f1c40f"}[color]
            self.bolas[idx].setStyleSheet(f"background: {hex_c}; border-radius: 25px; border: 2px solid white;")

        if len(self.secuencia_usuario) == len(self.patron):
            exito = self.secuencia_usuario == self.patron
            # Envía el resultado al servidor para actualizar XP y Monedas
            self.sio.emit('actualizar_progreso_memoria', {'user': self.uid, 'exito': exito})
            QTimer.singleShot(800, self.conectar_datos) # Refrescar stats

    def procesar_resultado(self, data):
        self.puntos = data['stats']['puntos']
        self.monedas = data['stats']['monedas']
        self.actualizar_ui()
        # Puedes añadir un mensaje temporal aquí si quieres

    def actualizar_ui(self):
        self.lbl_puntos.setText(f"XP: {self.puntos}")
        self.lbl_monedas.setText(f"💰: {self.monedas}")

    def render_biblioteca(self):
        # Recuperado el renderizado de trivias original
        self.lista_trivias.clear()
        for t in self.trivias:
            item = QListWidgetItem(f"{t['cat']} - {t['tit']} ({t['costo']}💰)")
            self.lista_trivias.addItem(item)

    def actualizar_ranking_ui(self, rank):
        self.lista_rank.clear()
        for i, item in enumerate(rank):
            self.lista_rank.addItem(f"{i+1}. {item['user']} - {item['puntos']} XP")
            if i == 0:
                self.signal_nuevo_lider.emit(item['user'])

    def efecto_trofeo(self, user):
        if self.lbl_lider.text() != f"LÍDER: {user}":
            self.lbl_lider.setText(f"LÍDER: {user}")
            # Efecto visual original recuperado
            self.trofeo.setStyleSheet("font-size: 85px; margin: 0px; color: #f1c40f;")
            QTimer.singleShot(600, lambda: self.trofeo.setStyleSheet("font-size: 70px; margin: 5px; color: white;"))

    def mostrar_especial(self, data):
        # Puedes añadir notificaciones especiales aquí si quieres
        pass

    # Función vacía necesaria para que no de error la señal, aunque no la usemos visualmente
    def agregar_mensaje_chat(self, data):
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Estilo base limpio
    game = MaravillaGame()
    game.show()
    sys.exit(app.exec_())
