import sys
import os
import traceback
import urllib.request
import json
import time
import socket
import random
import concurrent.futures
from dataclasses import dataclass

def show_error_popup(title, message):
    """Exibe pop-ups de erro críticos em qualquer sistema (Windows/Linux)"""
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    else:
        # Fallback cross-platform usando Tkinter nativo do Python
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message)
        except:
            print(f"[{title}] {message}")

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def global_exception_handler(exctype, value, tb):
    """Proteção Anti-Crash: Mostra erro em pop-up se algo der errado no .exe"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    try:
        with open(os.path.join(get_base_path(), "crash_log.txt"), "w", encoding="utf-8") as f:
            f.write(error_msg)
    except:
        pass
    
    show_error_popup("Erro - JJMC Proxy", f"Erro Fatal Detectado!\n\n{error_msg[:400]}...")
    sys.exit(1)

sys.excepthook = global_exception_handler

try:
    import subprocess
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QPushButton, QLabel, QSystemTrayIcon, QMenu, QMessageBox,
        QRadioButton, QLineEdit, QGroupBox, QFormLayout
    )
    from PyQt6.QtGui import QIcon, QAction
    from PyQt6.QtCore import QThread, pyqtSignal, Qt
except Exception as e:
    error_text = f"Falta instalar bibliotecas!\n\nRode: pip install PyQt6\n\nErro: {str(e)}"
    show_error_popup("Erro Fatal", error_text)
    sys.exit(1)

@dataclass
class ProxyInfo:
    ip: str
    port: str
    protocol: str = 'http'
    ping_ms: float = 9999.0
    is_working: bool = False

class ConfigManager:
    """Salva e carrega as configurações do usuário em um arquivo JSON"""
    def __init__(self):
        self.config_path = os.path.join(get_base_path(), "jjmc_config.json")
        self.config = self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    # Se for um config antigo, adiciona a lista de favoritos
                    if "favorites" not in data:
                        data["favorites"] = []
                    return data
            except:
                pass
        return {"mode": "auto", "manual_ip": "", "manual_port": "", "favorites": []}

    def save(self, mode, ip, port):
        self.config["mode"] = mode
        self.config["manual_ip"] = ip
        self.config["manual_port"] = port
        self._write()

    def add_favorite(self, ip, port):
        favs = self.config.get("favorites", [])
        new_fav = {"ip": ip, "port": port}
        # Se já existe, remove para colocar no topo como mais recente
        if new_fav in favs: 
            favs.remove(new_fav)
        favs.insert(0, new_fav)
        # Guarda no máximo o histórico dos 10 melhores
        self.config["favorites"] = favs[:10] 
        self._write()
        
    def _write(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f)
        except Exception as e:
            print(f"Erro ao salvar configs: {e}")

class DiscordProxyManager:
    """Responsável por derrubar e reiniciar o Discord com compatibilidade Linux/Windows."""
    def __init__(self):
        self.is_windows = os.name == 'nt'
        if self.is_windows:
            self.local_app_data = os.getenv('LOCALAPPDATA')
            self.discord_dir = os.path.join(self.local_app_data, 'Discord') if self.local_app_data else ""
        else:
            self.discord_dir = "" # No Linux/Mac, o binário costuma estar no PATH global

    def _get_discord_executable(self) -> str:
        if self.is_windows:
            if not os.path.exists(self.discord_dir): return ""
            folders = [f for f in os.listdir(self.discord_dir) if f.startswith('app-')]
            if not folders: return ""
            folders.sort(reverse=True)
            return os.path.join(self.discord_dir, folders[0], "Discord.exe")
        else:
            return "discord" # Comando padrão do Linux

    def _kill_existing_discord(self):
        if self.is_windows:
            creationflags = 0x08000000 
            subprocess.run(["taskkill", "/F", "/IM", "Discord.exe", "/T"], 
                           creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "discord"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)

    def launch_discord(self, ip: str, port: str) -> bool:
        discord_exe = self._get_discord_executable()
        if not discord_exe: return False
        
        self._kill_existing_discord()
        
        if self.is_windows and not os.path.exists(discord_exe):
            return False
            
        proxy_url = f"{ip}:{port}"
        env = os.environ.copy()
        # Injeta variáveis de ambiente para garantir que uploads de arquivos passem pelo proxy
        env["HTTP_PROXY"] = f"http://{proxy_url}"
        env["HTTPS_PROXY"] = f"http://{proxy_url}"
        env["http_proxy"] = f"http://{proxy_url}"
        env["https_proxy"] = f"http://{proxy_url}"
        env["NO_PROXY"] = "127.0.0.1,localhost,.discord.media"
        env["no_proxy"] = "127.0.0.1,localhost,.discord.media"
        
        args = [
            discord_exe,
            f'--proxy-server=http={proxy_url};https={proxy_url}',
            '--proxy-bypass-list=127.0.0.1,localhost,<-loopback>,*.discord.media',
            '--disable-quic' # Importante para não bloquear imagens
        ]
        
        try:
            subprocess.Popen(args, env=env)
            return True
        except FileNotFoundError:
            return False

    def launch_discord_normal(self):
        discord_exe = self._get_discord_executable()
        if discord_exe:
            self._kill_existing_discord()
            if self.is_windows and not os.path.exists(discord_exe):
                return
            try:
                subprocess.Popen([discord_exe])
            except FileNotFoundError:
                pass

class ProxySniperWorker(QThread):
    """Motor V7: VIP Fast Track (Histórico de Campeões) + Busca LatAm"""
    status_update = pyqtSignal(str)
    proxy_found = pyqtSignal(object)
    proxy_failed = pyqtSignal(str)

    # Variáveis de classe (Memória Global)
    _cached_raw_ips = set()
    _last_fetch_time = 0

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager

    def _test_batch(self, proxy_list, timeout=2.0):
        """Função auxiliar isolada para testar qualquer lista de proxies"""
        def test_single(proxy):
            start = time.perf_counter()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((proxy.ip, int(proxy.port)))
                sock.close()
                if result != 0: return proxy
                
                proxy_support = urllib.request.ProxyHandler({'http': f"{proxy.ip}:{proxy.port}", 'https': f"{proxy.ip}:{proxy.port}"})
                opener = urllib.request.build_opener(proxy_support)
                req = urllib.request.Request("http://clients3.google.com/generate_204", headers={'User-Agent': 'Mozilla/5.0'})
                with opener.open(req, timeout=timeout) as resp:
                    if resp.status == 204:
                        proxy.ping_ms = (time.perf_counter() - start) * 1000
                        proxy.is_working = True
            except: pass
            return proxy

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(test_single, proxy_list))
        
        working = [p for p in results if p.is_working]
        working.sort(key=lambda x: x.ping_ms)
        return working

    def run(self):
        # ======================================================
        # ETAPA 1: O "Fast Track" (Testa os Favoritos Salvos)
        # ======================================================
        favs = self.config_manager.config.get("favorites", [])
        if favs:
            self.status_update.emit(f"Testando Campeões Salvos...")
            vip_list = [ProxyInfo(ip=f["ip"], port=f["port"]) for f in favs]
            
            # Damos apenas 1.0s de tolerância. Se for lento, nem passa pelo teste!
            working_vips = self._test_batch(vip_list, timeout=1.0)
            
            if working_vips:
                campeao = working_vips[0]
                
                # A REGRA DE OURO (Anti-Vício): Só aceita se for realmente rápido!
                # Se for maior que 300ms, ele está degradado. Rejeitamos o Fast Track.
                if campeao.ping_ms <= 300.0:
                    self.config_manager.add_favorite(campeao.ip, campeao.port)
                    self.proxy_found.emit(campeao)
                    return # Encerra aqui, proxy excelente confirmado!
                else:
                    self.status_update.emit(f"Proxy VIP lento ({campeao.ping_ms:.0f}ms). Buscando novos...")

        # ======================================================
        # ETAPA 2: A Busca na Internet (Radar LatAm)
        # ======================================================
        current_time = time.time()
        raw_ips = set()

        if self.__class__._cached_raw_ips and (current_time - self.__class__._last_fetch_time < 300):
            self.status_update.emit("Usando Radar em Cache (Anti-Block)...")
            raw_ips = set(self.__class__._cached_raw_ips)
        else:
            self.status_update.emit("Baixando Radar da América Latina...")
            
            sources = [
                "https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=http,socks4,socks5&timeout=1500&country=AR,CL,UY,PY,BR,CO,PE&proxy_format=protocolipport&format=text",
                "https://proxylist.geonode.com/api/proxy-list?protocols=socks5,socks4,http&limit=500&country=AR,CL,UY,PY,BR,CO,PE&speed=fast&sort_by=lastChecked&sort_type=desc",
                "https://proxio.io/api/list?protocol=socks5,http,https&country=AR,CL,UY,BR,CO,PE" 
            ]
            
            for url in sources:
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8) as response:
                        data = response.read().decode('utf-8')
                        if 'geonode' in url or 'proxio' in url:
                            try:
                                json_data = json.loads(data)
                                if 'data' in json_data and isinstance(json_data['data'], list):
                                    for item in json_data['data']:
                                        if 'ip' in item and 'port' in item:
                                            raw_ips.add(f"{item['ip']}:{item['port']}")
                                elif isinstance(json_data, list):
                                    for item in json_data:
                                       if 'ip' in item and 'port' in item:
                                            raw_ips.add(f"{item['ip']}:{item['port']}")
                            except: pass
                        else:
                            for line in data.splitlines():
                                if '://' in line: line = line.split('://')[1]
                                if ':' in line: raw_ips.add(line.strip())
                except: pass

            if raw_ips:
                self.__class__._cached_raw_ips = set(raw_ips)
                self.__class__._last_fetch_time = current_time

        proxy_list = []
        for item in raw_ips:
            try:
                ip, port = item.split(':')
                proxy_list.append(ProxyInfo(ip=ip, port=port))
            except: pass

        if not proxy_list:
            self.proxy_failed.emit("APIs bloqueadas temporariamente e sem cache. Tente daqui a 5 minutos.")
            return

        random.shuffle(proxy_list)
        test_batch = proxy_list[:200]
        self.status_update.emit(f"Testando {len(test_batch)} novos alvos (Timeout 2.0s)...")
        
        working_proxies = self._test_batch(test_batch, timeout=2.0)

        if working_proxies:
            campeao = working_proxies[0]
            # Salva o novo campeão no JSON para o futuro!
            self.config_manager.add_favorite(campeao.ip, campeao.port)
            self.proxy_found.emit(campeao)
        else:
            self.proxy_failed.emit("Nenhum proxy sul-americano respondeu a tempo. Tente novamente.")

class ProxyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JJMC Proxy Automator")
        self.setFixedSize(400, 320)
        self.config_manager = ConfigManager()
        self.discord_manager = DiscordProxyManager()
        self.is_running = False
        
        self._init_ui()
        self._init_system_tray()
        self._load_saved_config()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Status: Parado")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")
        layout.addWidget(self.status_label)

        mode_group = QGroupBox("Modo de Operação")
        mode_layout = QVBoxLayout()
        
        self.radio_auto = QRadioButton("Modo Automático (Busca Proxies LatAm)")
        self.radio_auto.toggled.connect(self._toggle_manual_fields)
        self.radio_manual = QRadioButton("Modo Manual (Proxy Privado / Pago)")
        
        mode_layout.addWidget(self.radio_auto)
        mode_layout.addWidget(self.radio_manual)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.manual_group = QGroupBox("Configuração Manual")
        form_layout = QFormLayout()
        
        self.input_ip = QLineEdit()
        self.input_ip.setPlaceholderText("Ex: 179.41.11.138")
        self.input_port = QLineEdit()
        self.input_port.setPlaceholderText("Ex: 8080")
        
        form_layout.addRow("IP / Host:", self.input_ip)
        form_layout.addRow("Porta:", self.input_port)
        self.manual_group.setLayout(form_layout)
        layout.addWidget(self.manual_group)

        self.btn_toggle = QPushButton("Ligar Proxy")
        self.btn_toggle.setFixedHeight(45)
        self.btn_toggle.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle_proxy)
        layout.addWidget(self.btn_toggle)

    def _init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)

        self.tray_menu = QMenu()
        self.action_toggle = QAction("Ligar Proxy", self)
        self.action_toggle.triggered.connect(self.toggle_proxy)
        self.action_show = QAction("Opções Avançadas", self)
        self.action_show.triggered.connect(self.show)
        self.action_quit = QAction("Sair", self)
        self.action_quit.triggered.connect(self.quit_app)

        self.tray_menu.addAction(self.action_toggle)
        self.tray_menu.addAction(self.action_show)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.action_quit)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("JJMC Proxy", "Rodando em segundo plano.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _toggle_manual_fields(self):
        self.manual_group.setEnabled(self.radio_manual.isChecked())

    def _load_saved_config(self):
        config = self.config_manager.config
        self.input_ip.setText(config.get("manual_ip", ""))
        self.input_port.setText(config.get("manual_port", ""))
        if config.get("mode") == "manual":
            self.radio_manual.setChecked(True)
        else:
            self.radio_auto.setChecked(True)
        self._toggle_manual_fields()

    def toggle_proxy(self):
        mode = "manual" if self.radio_manual.isChecked() else "auto"
        self.config_manager.save(mode, self.input_ip.text(), self.input_port.text())

        if not self.is_running:
            self.start_proxy()
        else:
            self.stop_proxy()

    def start_proxy(self):
        self.btn_toggle.setEnabled(False)
        self.action_toggle.setEnabled(False)
        
        if self.radio_manual.isChecked():
            ip = self.input_ip.text().strip()
            port = self.input_port.text().strip()
            if not ip or not port:
                QMessageBox.warning(self, "Erro", "Preencha IP e Porta no modo manual!")
                self.btn_toggle.setEnabled(True)
                self.action_toggle.setEnabled(True)
                return
            self.inject_and_connect(ip, port)
        else:
            self.status_label.setText("Iniciando Motor Automático...")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff9800;")
            
            # Passamos o config_manager para que a Thread possa ler/salvar os favoritos
            self.worker = ProxySniperWorker(self.config_manager)
            self.worker.status_update.connect(self.on_worker_status)
            self.worker.proxy_found.connect(self.on_proxy_found)
            self.worker.proxy_failed.connect(self.on_proxy_failed)
            self.worker.start()

    def on_worker_status(self, msg):
        self.status_label.setText(msg)

    def on_proxy_found(self, proxy):
        self.status_label.setText("Injetando no Discord...")
        self.inject_and_connect(proxy.ip, proxy.port, ping=proxy.ping_ms)

    def on_proxy_failed(self, error_msg):
        self.status_label.setText("Falha na Busca")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")
        self.btn_toggle.setEnabled(True)
        self.action_toggle.setEnabled(True)
        QMessageBox.warning(self, "Erro do Motor", error_msg)

    def inject_and_connect(self, ip, port, ping=None):
        if self.discord_manager.launch_discord(ip, port):
            self.is_running = True
            ping_text = f" ({ping:.0f}ms)" if ping else ""
            self.status_label.setText(f"Conectado: {ip}{ping_text}")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4caf50;")
            
            self.btn_toggle.setText("Desligar Proxy")
            self.btn_toggle.setEnabled(True)
            self.action_toggle.setText("Desligar Proxy")
            self.action_toggle.setEnabled(True)
            self.tray_icon.showMessage("Conectado", f"Discord injetado no IP {ip}.", QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self.on_proxy_failed("Discord não encontrado ou falha ao iniciar.")

    def stop_proxy(self):
        self.is_running = False
        self.status_label.setText("Desligando... Reiniciando Discord.")
        
        self.discord_manager.launch_discord_normal()
        
        self.status_label.setText("Status: Parado")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")
        self.btn_toggle.setText("Ligar Proxy")
        self.action_toggle.setText("Ligar Proxy")
        self.tray_icon.showMessage("Desativado", "Conexão limpa. Discord reiniciado.", QSystemTrayIcon.MessageIcon.Information, 3000)

    def quit_app(self):
        if self.is_running:
            self.discord_manager.launch_discord_normal()
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Erro", "Sistema Tray não suportado.")
        sys.exit(1)
    window = ProxyApp()
    window.show()
    sys.exit(app.exec())