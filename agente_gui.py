import asyncio
import threading
import uuid
import customtkinter as ctk
import httpx
import json
import os
from tkinter import messagebox
from puresnmp import Client, V2C, PyWrapper

# Bibliotecas para rodar em segundo plano / System Tray
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# Configuração global de aparência
ctk.set_appearance_mode("dark")

ARQUIVO_JSON = "impressoras.json"
CONFIG_SERVIDORES_JSON = "config_servidor.json"

def get_agent_id():
    """Obtém o ID único do agente (persiste localmente em .agent_token se não existir)."""
    agent_id = os.environ.get("PRISMA_AGENT_ID")
    if agent_id:
        return agent_id.strip()
    
    token_file = ".agent_token"
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    return token
        except Exception:
            pass
            
    mac = uuid.getnode()
    generated_id = f"AGENT-{uuid.UUID(int=mac)}"
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(generated_id)
    except Exception as e:
        print(f"[Erro Token] Falha ao salvar: {e}")
    return generated_id

def carregar_config_servidor():
    """Carrega as configurações do JSON. Retorna valores default se não existir."""
    default_config = {
        "django_api_url": "http://192.170.0.241:8999/api/coleta/",
        "cliente_nome": "Sem Cliente Associado",
        "cliente_id": None
    }
    if os.path.exists(CONFIG_SERVIDORES_JSON):
        try:
            with open(CONFIG_SERVIDORES_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in default_config.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            pass
    return default_config

def salvar_config_servidor(config_dict):
    try:
        with open(CONFIG_SERVIDORES_JSON, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Erro Config] Falha ao salvar: {e}")

class AppConfig:
    _config = carregar_config_servidor()
    
    @classmethod
    def get_api_url(cls):
        return cls._config.get("django_api_url")
        
    @classmethod
    def get_server_url(cls):
        return "/".join(cls._config.get("django_api_url").split("/")[:3])
        
    @classmethod
    def get_cliente_nome(cls):
        return cls._config.get("cliente_nome", "Sem Cliente Associado")
        
    @classmethod
    def get_cliente_id(cls):
        return cls._config.get("cliente_id")
        
    @classmethod
    def update(cls, url):
        cls._config["django_api_url"] = url
        salvar_config_servidor(cls._config)
        
    @classmethod
    def update_cliente(cls, cliente_nome, cliente_id):
        cls._config["cliente_nome"] = cliente_nome
        cls._config["cliente_id"] = cliente_id
        salvar_config_servidor(cls._config)

def carregar_do_json():
    """Carrega as impressoras cadastradas do arquivo JSON. Se não existir, retorna a base default."""
    if os.path.exists(ARQUIVO_JSON):
        try:
            with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Erro JSON] Falha ao ler arquivo: {e}")
    
    dados_iniciais = [
        {
            "id": "CANON_MB5410_REC",
            "nome": "Recepção Canon",
            "ip": "192.168.50.12",
            "modelo": "Canon Maxify",
            "marca": "Canon",
            "serial_inicial": "CANON_MB5410_REC",
            "oids": {}
        },
        {
            "id": "EPSON_L15160_GTR",
            "nome": "Técnico Epson",
            "ip": "192.168.50.10",
            "modelo": "Epson L15160",
            "marca": "Epson",
            "serial_inicial": "EPSON_L15160_GTR",
            "oids": {}
        }
    ]
    salvar_no_json(dados_iniciais)
    return dados_iniciais

def salvar_no_json(dados):
    """Salva a lista de impressoras diretamente no arquivo JSON."""
    try:
        with open(ARQUIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Erro JSON] Falha ao salvar arquivo: {e}")

def formatar_uptime(timeticks):
    if timeticks is None or str(timeticks) == "N/A": return "N/A"
    if ":" in str(timeticks): return str(timeticks).split(".")[0]
    return str(timeticks)

def formatar_painel(mensagem):
    if not mensagem or str(mensagem).strip() == "" or mensagem == "N/A": return "Pronta para Impressão"
    msg_clean = str(mensagem).strip().lower()
    if any(t in msg_clean for t in ["ready", "pronta", "idle", "sleep", "online", "ok"]): return "Pronta para Impressão"
    return str(mensagem).strip()

async def snmp_safe_get(ip, oid, decode=False):
    client = PyWrapper(Client(ip, V2C("public")))
    try:
        value = await asyncio.wait_for(client.get(oid), timeout=2.0)
        if decode and isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore").strip()
        return value
    except Exception:
        return "N/A"


class Session:
    is_authenticated = False
    token = None

def criar_imagem_icone(tipo, cor_hex):
    # Imagem RGBA de alta resolução 64x64 (redimensionada para 20x20)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Converte cor hex para tuple RGBA
    cor = tuple(int(cor_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
    
    def draw_rounded_rect(coords, r, f=None, o=None, w=1):
        try:
            draw.rounded_rectangle(coords, radius=r, fill=f, outline=o, width=w)
        except AttributeError:
            draw.rectangle(coords, fill=f, outline=o, width=w)

    if tipo == "menu":
        draw_rounded_rect([10, 14, 54, 20], r=3, f=cor)
        draw_rounded_rect([10, 29, 54, 35], r=3, f=cor)
        draw_rounded_rect([10, 44, 54, 50], r=3, f=cor)
        
    elif tipo == "dashboard":
        draw_rounded_rect([8, 8, 26, 26], r=4, f=cor)
        draw_rounded_rect([38, 8, 56, 26], r=4, f=cor)
        draw_rounded_rect([8, 38, 26, 56], r=4, f=cor)
        draw_rounded_rect([38, 38, 56, 56], r=4, f=cor)
        
    elif tipo == "config":
        draw.ellipse([14, 14, 50, 50], outline=cor, width=6)
        draw.ellipse([26, 26, 38, 38], outline=cor, width=4)
        import math
        for angulo in range(0, 360, 45):
            rad = math.radians(angulo)
            x1 = int(32 + 18 * math.cos(rad))
            y1 = int(32 + 18 * math.sin(rad))
            x2 = int(32 + 28 * math.cos(rad))
            y2 = int(32 + 28 * math.sin(rad))
            draw.line([x1, y1, x2, y2], fill=cor, width=6)
        
    elif tipo == "gerenciar":
        draw_rounded_rect([16, 8, 48, 20], r=2, o=cor, w=4)
        draw.rectangle([24, 14, 40, 22], fill=cor)
        draw_rounded_rect([8, 22, 56, 46], r=4, f=cor)
        draw_rounded_rect([18, 38, 46, 56], r=2, o=cor, w=4)
        draw.rectangle([24, 42, 40, 50], fill=cor)
        
    elif tipo == "cliente":
        draw_rounded_rect([16, 8, 48, 56], r=4, o=cor, w=4)
        for y in [16, 26, 36, 46]:
            for x in [22, 30, 38]:
                draw.rectangle([x, y, x+4, y+4], fill=cor)
                
    elif tipo == "login":
        draw_rounded_rect([16, 26, 48, 56], r=5, f=cor)
        draw.arc([22, 10, 42, 32], 180, 0, fill=cor, width=5)
        draw.ellipse([29, 36, 35, 42], fill=(0, 0, 0, 0))
        draw.rectangle([31, 42, 33, 48], fill=(0, 0, 0, 0))
        
    elif tipo == "logout":
        draw.line([16, 8, 16, 56], fill=cor, width=4)
        draw.line([16, 8, 44, 8], fill=cor, width=4)
        draw.line([16, 56, 44, 56], fill=cor, width=4)
        draw.line([26, 32, 52, 32], fill=cor, width=4)
        draw.line([44, 24, 52, 32], fill=cor, width=4)
        draw.line([44, 40, 52, 32], fill=cor, width=4)
        
    return ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))


class DashboardFinal(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PRISMA - Monitoramento Local Avançado")
        self.geometry("1350x850")
        self.configure(fg_color="#090a0f")

        self.impressoras_cadastradas = carregar_do_json()
        self.cards_ui = {}
        self.timer_job = None
        self.sidebar_animation_job = None
        self.sidebar_expanded = True
        self.sidebar_current_width = 220
        self.active_view = "dashboard"
        
        self.protocol("WM_DELETE_WINDOW", self.minimizar_para_tray)

        # Dynamic clean graphics icons
        self.icon_toggle = criar_imagem_icone("menu", "#ffffff")
        self.icon_dashboard = criar_imagem_icone("dashboard", "#ffffff")
        self.icon_gerenciamento = criar_imagem_icone("gerenciar", "#ffffff")
        self.icon_cliente = criar_imagem_icone("cliente", "#ffffff")
        self.icon_config = criar_imagem_icone("config", "#ffffff")
        self.icon_login = criar_imagem_icone("login", "#10b981")
        self.icon_logout = criar_imagem_icone("logout", "#ef4444")

        # --- SIDEBAR & MAIN CONTAINER LAYOUT ---
        self.frame_main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_main_container.pack(fill="both", expand=True)

        # Left Sidebar Frame
        self.frame_sidebar = ctk.CTkFrame(self.frame_main_container, width=220, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=0)
        self.frame_sidebar.pack(side="left", fill="y")
        self.frame_sidebar.pack_propagate(False)

        # Right Content Frame
        self.frame_content = ctk.CTkFrame(self.frame_main_container, fg_color="transparent")
        self.frame_content.pack(side="right", fill="both", expand=True)

        # --- SIDEBAR WIDGETS ---
        # Toggle Button / Title
        self.btn_toggle = ctk.CTkButton(self.frame_sidebar, text="PRISMA", image=self.icon_toggle, compound="left", font=("Inter", 14, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=45, corner_radius=8, command=self.toggle_sidebar)
        self.btn_toggle.pack(fill="x", padx=10, pady=(15, 20))

        # Nav: Dashboard
        self.btn_nav_dashboard = ctk.CTkButton(self.frame_sidebar, text="Dashboard", image=self.icon_dashboard, compound="left", font=("Inter", 12, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=lambda: self.show_view("dashboard"))
        self.btn_nav_dashboard.pack(fill="x", padx=10, pady=2)

        # Nav: Gerenciamento Cache
        self.btn_nav_gerenciamento = ctk.CTkButton(self.frame_sidebar, text="Gerenciar Cache", image=self.icon_gerenciamento, compound="left", font=("Inter", 12, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=lambda: self.show_view("gerenciamento"))

        # Nav: Selecionar Cliente
        self.btn_nav_cliente = ctk.CTkButton(self.frame_sidebar, text="Selecionar Cliente", image=self.icon_cliente, compound="left", font=("Inter", 12, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=lambda: self.show_view("vincular_cliente"))

        # Nav: Configurar Servidor
        self.btn_nav_config = ctk.CTkButton(self.frame_sidebar, text="Config Servidor", image=self.icon_config, compound="left", font=("Inter", 12, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=lambda: self.show_view("config_servidor"))
        self.btn_nav_config.pack(fill="x", padx=10, pady=2)

        # Nav: Login / Auth
        self.btn_nav_auth = ctk.CTkButton(self.frame_sidebar, text="Fazer Login", image=self.icon_login, compound="left", font=("Inter", 12, "bold"), text_color="#10b981", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=self.alternar_auth)
        self.btn_nav_auth.pack(fill="x", padx=10, pady=(20, 2))

        # --- INITIALIZE ALL SUB-VIEWS ---
        self.init_view_dashboard()
        self.init_view_config_servidor()
        self.init_view_vincular_cliente()
        self.init_view_login()
        self.init_view_gerenciamento()

        # Reconstruir os cards do Dashboard com as impressoras cadastradas
        self.reconstruir_cards_dashboard(disparar=True)

        # Show Dashboard initially
        self.show_view("dashboard")

        self.configurar_automacao()
        self.atualizar_botoes_auth()
        self.iniciar_tray_icon()

    def toggle_sidebar(self):
        is_dashboard = getattr(self, "active_view", "dashboard") == "dashboard"
        
        if is_dashboard:
            # Suspend layout of scroll frame to avoid expensive recursive card redraws
            self.frame_scroll.pack_forget()
        
        if self.sidebar_expanded:
            # Clear text instantly before collapsing to prevent clipping/wrapping artifacts during slide
            self.btn_toggle.configure(text="", image=self.icon_toggle, anchor="center")
            self.btn_nav_dashboard.configure(text="", anchor="center")
            self.btn_nav_gerenciamento.configure(text="", anchor="center")
            self.btn_nav_cliente.configure(text="", anchor="center")
            self.btn_nav_config.configure(text="", anchor="center")
            self.btn_nav_auth.configure(text="", anchor="center")
            
            self.sidebar_expanded = False
            
            if is_dashboard:
                # Instant transition to avoid Tkinter layout recalculation lag on heavy scroll frame/cards
                if self.sidebar_animation_job:
                    self.after_cancel(self.sidebar_animation_job)
                    self.sidebar_animation_job = None
                self.sidebar_current_width = 60
                self.frame_sidebar.configure(width=60)
            else:
                self.animate_sidebar(60)
        else:
            self.sidebar_expanded = True
            
            if is_dashboard:
                # Instant transition to avoid Tkinter layout recalculation lag on heavy scroll frame/cards
                if self.sidebar_animation_job:
                    self.after_cancel(self.sidebar_animation_job)
                    self.sidebar_animation_job = None
                self.sidebar_current_width = 220
                self.frame_sidebar.configure(width=220)
                # Set expanded labels instantly
                self.btn_toggle.configure(text="PRISMA", image=self.icon_toggle, anchor="w")
                self.btn_nav_dashboard.configure(text="Dashboard", anchor="w")
                self.btn_nav_gerenciamento.configure(text="Gerenciar Cache", anchor="w")
                self.btn_nav_cliente.configure(text="Selecionar Cliente", anchor="w")
                self.btn_nav_config.configure(text="Config Servidor", anchor="w")
                if Session.is_authenticated:
                    self.btn_nav_auth.configure(text="Desconectar", image=self.icon_logout, text_color="#ef4444", anchor="w")
                else:
                    self.btn_nav_auth.configure(text="Fazer Login", image=self.icon_login, text_color="#10b981", anchor="w")
            else:
                self.animate_sidebar(220)
                
        if is_dashboard:
            # Re-pack scroll frame after the sidebar has resized
            self.frame_scroll.pack(fill="both", expand=True, padx=0, pady=(5, 10))
            self.update_idletasks()

    def animate_sidebar(self, target_width):
        if self.sidebar_animation_job:
            self.after_cancel(self.sidebar_animation_job)
            self.sidebar_animation_job = None
            
        if not hasattr(self, "sidebar_current_width"):
            self.sidebar_current_width = 220 if not self.sidebar_expanded else 60
            
        current_width = self.sidebar_current_width
        
        diff = target_width - current_width
        step_size = 32  # snappy steps to minimize total redraws
        delay = 12      # ms delay
        
        if abs(diff) <= step_size:
            self.sidebar_current_width = target_width
            self.frame_sidebar.configure(width=target_width)
            self.update_idletasks()
            self.sidebar_animation_job = None
            if self.sidebar_expanded:
                # Finished expanding, set the labels
                self.btn_toggle.configure(text="PRISMA", image=self.icon_toggle, anchor="w")
                self.btn_nav_dashboard.configure(text="Dashboard", anchor="w")
                self.btn_nav_gerenciamento.configure(text="Gerenciar Cache", anchor="w")
                self.btn_nav_cliente.configure(text="Selecionar Cliente", anchor="w")
                self.btn_nav_config.configure(text="Config Servidor", anchor="w")
                if Session.is_authenticated:
                    self.btn_nav_auth.configure(text="Desconectar", image=self.icon_logout, text_color="#ef4444", anchor="w")
                else:
                    self.btn_nav_auth.configure(text="Fazer Login", image=self.icon_login, text_color="#10b981", anchor="w")

            if getattr(self, "active_view", "dashboard") == "dashboard":
                self.frame_scroll.pack(fill="both", expand=True, padx=0, pady=(5, 10))
        else:
            step = step_size if diff > 0 else -step_size
            new_width = current_width + step
            self.sidebar_current_width = new_width
            self.frame_sidebar.configure(width=new_width)
            self.update_idletasks()
            self.sidebar_animation_job = self.after(delay, lambda: self.animate_sidebar(target_width))

    def show_view(self, name):
        # Unpack all views
        self.view_dashboard.pack_forget()
        self.view_config_servidor.pack_forget()
        self.view_vincular_cliente.pack_forget()
        self.view_login.pack_forget()
        self.view_gerenciamento.pack_forget()

        self.active_view = name

        # Pack target
        if name == "dashboard":
            self.view_dashboard.pack(fill="both", expand=True, padx=35, pady=25)
            self.frame_scroll.pack(fill="both", expand=True, padx=0, pady=(5, 10))
            if not getattr(self, "cards_ui", None):
                self.reconstruir_cards_dashboard(disparar=False)
        elif name == "config_servidor":
            self.view_config_servidor.pack(fill="both", expand=True, padx=35, pady=25)
        elif name == "vincular_cliente":
            self.view_vincular_cliente.pack(fill="both", expand=True, padx=35, pady=25)
            self.carregar_clientes_na_view()
        elif name == "login":
            self.view_login.pack(fill="both", expand=True, padx=35, pady=25)
        elif name == "gerenciamento":
            self.view_gerenciamento.pack(fill="both", expand=True, padx=35, pady=25)
            self.atualizar_lista_gerenciamento()

    def alternar_auth(self):
        if Session.is_authenticated:
            self.desconectar_usuario()
        else:
            self.show_view("login")

    def desconectar_usuario(self):
        Session.is_authenticated = False
        Session.token = None
        messagebox.showinfo("Logout", "Você foi desconectado.")
        self.atualizar_botoes_auth()
        self.show_view("dashboard")

    def atualizar_botoes_auth(self):
        self.lbl_cliente_associado.configure(text=f"Cliente Monitorado: {AppConfig.get_cliente_nome()}")
        
        self.btn_nav_gerenciamento.pack_forget()
        self.btn_nav_cliente.pack_forget()
        self.btn_nav_auth.pack_forget()

        if Session.is_authenticated:
            self.btn_nav_gerenciamento.pack(fill="x", padx=10, pady=2)
            self.btn_nav_cliente.pack(fill="x", padx=10, pady=2)
            
            if self.sidebar_expanded:
                self.btn_nav_auth.configure(text="Desconectar", image=self.icon_logout, text_color="#ef4444", anchor="w")
            else:
                self.btn_nav_auth.configure(text="", image=self.icon_logout, text_color="#ef4444", anchor="center")
        else:
            if self.sidebar_expanded:
                self.btn_nav_auth.configure(text="Fazer Login", image=self.icon_login, text_color="#10b981", anchor="w")
            else:
                self.btn_nav_auth.configure(text="", image=self.icon_login, text_color="#10b981", anchor="center")
                
        self.btn_nav_auth.pack(fill="x", padx=10, pady=(20, 2))

    # --- VIEW INITS AND LOGICS ---
    def init_view_dashboard(self):
        self.view_dashboard = ctk.CTkFrame(self.frame_content, fg_color="transparent")
        
        self.frame_top = ctk.CTkFrame(self.view_dashboard, fg_color="transparent")
        self.frame_top.pack(fill="x", padx=0, pady=(0, 10))

        self.frame_titulos = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.frame_titulos.pack(side="left")
        
        self.lbl_titulo = ctk.CTkLabel(self.frame_titulos, text="Métricas das Impressoras", font=("Inter", 24, "bold"), text_color="#ffffff")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_sub = ctk.CTkLabel(self.frame_titulos, text="Gerenciamento multiescala de tempo e pooling dinâmico via SNMP", font=("Inter", 12), text_color="#94a3b8")
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        self.lbl_agent_id = ctk.CTkLabel(self.frame_titulos, text=f"ID do Agente: {get_agent_id()}", font=("Inter", 11, "bold"), text_color="#10b981")
        self.lbl_agent_id.pack(anchor="w", pady=(2, 0))

        self.lbl_cliente_associado = ctk.CTkLabel(self.frame_titulos, text=f"Cliente Monitorado: {AppConfig.get_cliente_nome()}", font=("Inter", 11, "bold"), text_color="#3b82f6")
        self.lbl_cliente_associado.pack(anchor="w", pady=(2, 0))

        self.frame_config_tempo = ctk.CTkFrame(self.frame_top, fg_color="#111218", corner_radius=8, border_color="#1d1e26", border_width=1, height=45)
        self.frame_config_tempo.pack(side="right", padx=(15, 0))

        ctk.CTkLabel(self.frame_config_tempo, text="Auto-atualizar:", font=("Inter", 11, "bold"), text_color="#94a3b8").pack(side="left", padx=(10, 5))
        self.entry_tempo = ctk.CTkEntry(self.frame_config_tempo, width=45, height=28, fg_color="#181920", border_color="#282933", text_color="#ffffff", justify="center")
        self.entry_tempo.insert(0, "30")
        self.entry_tempo.pack(side="left", padx=2)

        self.combo_unidade = ctk.CTkComboBox(self.frame_config_tempo, values=["Segundos", "Minutos", "Horas"], width=100, height=28, fg_color="#181920", border_color="#282933")
        self.combo_unidade.set("Segundos")
        self.combo_unidade.pack(side="left", padx=4)

        self.btn_aplicar_tempo = ctk.CTkButton(self.frame_config_tempo, text="Agendar", width=65, height=28, fg_color="#181920", hover_color="#282933", text_color="#ffffff", font=("Inter", 11, "bold"), command=self.configurar_automacao)
        self.btn_aplicar_tempo.pack(side="left", padx=(2, 10))

        self.btn_atualizar = ctk.CTkButton(self.frame_top, text="Forçar Atualização", width=135, height=32, fg_color="#181920", hover_color="#282933", text_color="#ffffff", font=("Inter", 11, "bold"), command=self.disparar_coleta)
        self.btn_atualizar.pack(side="right", padx=6)

        self.frame_kpis = ctk.CTkFrame(self.view_dashboard, fg_color="transparent")
        self.frame_kpis.pack(fill="x", padx=0, pady=10)
        self.frame_kpis.columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        self.kpi_total = self.card_kpi(self.frame_kpis, 0, "TOTAL IMPRESSORAS", "0", "🖨️")
        self.kpi_online = self.card_kpi(self.frame_kpis, 1, "ONLINE", "0", "✓", cor_val="#10b981")
        self.kpi_offline = self.card_kpi(self.frame_kpis, 2, "OFFLINE / INATIVAS", "0", "⚠", cor_val="#f87171")
        self.kpi_alerta_toner = self.card_kpi(self.frame_kpis, 3, "SUPRIMENTOS < 15%", "0", "⚡", cor_val="#f59e0b")

        self.frame_scroll = ctk.CTkScrollableFrame(self.view_dashboard, fg_color="transparent")
        self.frame_scroll.pack(fill="both", expand=True, padx=0, pady=(5, 10))
        
        self.frame_grid_dispositivos = ctk.CTkFrame(self.frame_scroll, fg_color="transparent")
        self.frame_grid_dispositivos.pack(fill="both", expand=True)
        for i in range(4):
            self.frame_grid_dispositivos.columnconfigure(i, weight=1, minsize=290)

    def init_view_config_servidor(self):
        self.view_config_servidor = ctk.CTkFrame(self.frame_content, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        container = ctk.CTkFrame(self.view_config_servidor, fg_color="transparent")
        container.pack(expand=True)
        
        lbl_titulo = ctk.CTkLabel(container, text="CONFIGURAR SERVIDOR DJANGO", font=("Inter", 16, "bold"), text_color="#ffffff")
        lbl_titulo.pack(pady=(0, 20))

        lbl_url = ctk.CTkLabel(container, text="URL da API de Coleta (ex: http://192.170.0.241:8999/api/coleta/)", font=("Inter", 11), text_color="#94a3b8")
        lbl_url.pack(anchor="w", padx=10)
        
        self.entry_url = ctk.CTkEntry(container, width=460, height=35, fg_color="#181920", border_color="#282933", text_color="#ffffff")
        self.entry_url.insert(0, AppConfig.get_api_url())
        self.entry_url.pack(pady=(5, 20))

        frame_botoes = ctk.CTkFrame(container, fg_color="transparent")
        frame_botoes.pack()

        btn_cancelar = ctk.CTkButton(frame_botoes, text="Voltar ao Dashboard", width=160, height=35, fg_color="#4b5563", hover_color="#374151", font=("Inter", 11, "bold"), command=lambda: self.show_view("dashboard"))
        btn_cancelar.pack(side="left", padx=10)

        btn_salvar = ctk.CTkButton(frame_botoes, text="Salvar URL", width=160, height=35, fg_color="#10b981", hover_color="#059669", font=("Inter", 11, "bold"), command=self.salvar_config_servidor)
        btn_salvar.pack(side="left", padx=10)

    def salvar_config_servidor(self):
        nova_url = self.entry_url.get().strip()
        if not nova_url:
            messagebox.showerror("Erro", "A URL do servidor não pode ficar vazia.")
            return
        if not (nova_url.startswith("http://") or nova_url.startswith("https://")):
            messagebox.showerror("Erro", "A URL deve começar com http:// ou https://")
            return
            
        AppConfig.update(nova_url)
        messagebox.showinfo("Sucesso", "Endereço do servidor atualizado com sucesso!")
        self.show_view("dashboard")

    def init_view_vincular_cliente(self):
        self.view_vincular_cliente = ctk.CTkFrame(self.frame_content, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        container = ctk.CTkFrame(self.view_vincular_cliente, fg_color="transparent")
        container.pack(expand=True)
        
        lbl_titulo = ctk.CTkLabel(container, text="SELECIONAR CLIENTE DO AGENTE", font=("Inter", 16, "bold"), text_color="#ffffff")
        lbl_titulo.pack(pady=(0, 10))

        lbl_info = ctk.CTkLabel(container, text="Este agente coletará dados apenas das impressoras\nlocadas no cliente selecionado.", font=("Inter", 12), text_color="#94a3b8", justify="center")
        lbl_info.pack(pady=(0, 20))

        self.combo_clientes = ctk.CTkComboBox(container, values=["Carregando..."], width=320, height=35, fg_color="#181920", border_color="#282933", text_color="#ffffff")
        self.combo_clientes.pack(pady=10)

        frame_botoes = ctk.CTkFrame(container, fg_color="transparent")
        frame_botoes.pack(pady=15)

        btn_cancelar = ctk.CTkButton(frame_botoes, text="Voltar ao Dashboard", width=150, height=35, fg_color="#4b5563", hover_color="#374151", font=("Inter", 11, "bold"), command=lambda: self.show_view("dashboard"))
        btn_cancelar.pack(side="left", padx=10)

        self.btn_salvar_cliente = ctk.CTkButton(frame_botoes, text="Salvar Cliente", width=150, height=35, fg_color="#10b981", hover_color="#059669", font=("Inter", 11, "bold"), command=self.salvar_associacao_cliente_thread)
        self.btn_salvar_cliente.pack(side="left", padx=10)
        
        self.clientes_list = []
        self.clientes_map = {}

    def carregar_clientes_na_view(self):
        threading.Thread(target=lambda: asyncio.run(self.buscar_clientes_view_async()), daemon=True).start()

    async def buscar_clientes_view_async(self):
        url = f"{AppConfig.get_server_url()}/api/v1/clientes/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    self.clientes_list = response.json()
                    self.clientes_map = {c["nome"]: c["id"] for c in self.clientes_list}
                    nomes = list(self.clientes_map.keys())
                    self.after(0, lambda: self.atualizar_combobox_view(nomes))
                else:
                    self.after(0, lambda: messagebox.showerror("Erro", f"Erro ao buscar clientes: {response.status_code}"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro de Conexão", f"Falha de rede ao buscar clientes: {e}"))

    def atualizar_combobox_view(self, nomes):
        self.combo_clientes.configure(values=nomes)
        current_client = AppConfig.get_cliente_nome()
        if current_client in nomes:
            self.combo_clientes.set(current_client)
        elif nomes:
            self.combo_clientes.set(nomes[0])

    def salvar_associacao_cliente_thread(self):
        selected_name = self.combo_clientes.get()
        selected_id = self.clientes_map.get(selected_name)
        if not selected_id:
            messagebox.showerror("Erro", "Selecione um cliente válido.")
            return

        self.btn_salvar_cliente.configure(state="disabled", text="Salvando...")
        threading.Thread(target=lambda: asyncio.run(self.salvar_associacao_cliente_async(selected_name, selected_id)), daemon=True).start()

    async def salvar_associacao_cliente_async(self, name, cid):
        url = f"{AppConfig.get_server_url()}/api/v1/agente/vincular/"
        payload = {
            "agent_id": get_agent_id(),
            "cliente_id": cid
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    AppConfig.update_cliente(name, cid)
                    self.after(0, self.tratar_sucesso_vinculo_view)
                else:
                    self.after(0, lambda: self.tratar_erro_vinculo_view(f"Erro ao salvar: Código {response.status_code}"))
        except Exception as e:
            self.after(0, lambda: self.tratar_erro_vinculo_view(f"Erro de conexão: {e}"))

    def tratar_sucesso_vinculo_view(self):
        messagebox.showinfo("Sucesso", f"Agente vinculado ao cliente com sucesso!\nCliente: {AppConfig.get_cliente_nome()}")
        self.btn_salvar_cliente.configure(state="normal", text="Salvar Cliente")
        self.lbl_cliente_associado.configure(text=f"Cliente Monitorado: {AppConfig.get_cliente_nome()}")
        self.show_view("dashboard")
        self.disparar_coleta()

    def tratar_erro_vinculo_view(self, msg):
        messagebox.showerror("Erro", msg)
        self.btn_salvar_cliente.configure(state="normal", text="Salvar Cliente")

    def init_view_login(self):
        self.view_login = ctk.CTkFrame(self.frame_content, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        container = ctk.CTkFrame(self.view_login, fg_color="transparent")
        container.pack(expand=True)
        
        lbl_titulo = ctk.CTkLabel(container, text="AUTENTICAÇÃO DO TÉCNICO", font=("Inter", 16, "bold"), text_color="#ffffff")
        lbl_titulo.pack(pady=(0, 20))

        self.entry_user = ctk.CTkEntry(container, width=300, height=38, placeholder_text="Usuário", fg_color="#181920", border_color="#282933", text_color="#ffffff")
        self.entry_user.pack(pady=8)

        self.entry_pass = ctk.CTkEntry(container, width=300, height=38, placeholder_text="Senha", show="*", fg_color="#181920", border_color="#282933", text_color="#ffffff")
        self.entry_pass.pack(pady=8)

        frame_botoes = ctk.CTkFrame(container, fg_color="transparent")
        frame_botoes.pack(pady=(15, 10))

        btn_cancelar = ctk.CTkButton(frame_botoes, text="Voltar ao Dashboard", width=140, height=35, fg_color="#4b5563", hover_color="#374151", font=("Inter", 11, "bold"), command=lambda: self.show_view("dashboard"))
        btn_cancelar.pack(side="left", padx=8)

        self.btn_entrar = ctk.CTkButton(frame_botoes, text="Entrar", width=140, height=35, fg_color="#10b981", hover_color="#059669", font=("Inter", 11, "bold"), command=self.efetuar_login_thread)
        self.btn_entrar.pack(side="left", padx=8)

    def efetuar_login_thread(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        if not username or not password:
            messagebox.showerror("Erro", "Preencha todos os campos.")
            return

        self.btn_entrar.configure(state="disabled", text="Autenticando...")
        threading.Thread(target=lambda: asyncio.run(self.executar_login_view_async(username, password)), daemon=True).start()

    async def executar_login_view_async(self, username, password):
        url = f"{AppConfig.get_server_url()}/api/login/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"username": username, "password": password}, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    Session.is_authenticated = True
                    Session.token = data.get("token")
                    self.after(0, self.tratar_sucesso_login_view)
                elif response.status_code in (401, 403):
                    self.after(0, lambda: self.tratar_erro_login_view("Credenciais inválidas. Verifique seu usuário e senha."))
                else:
                    self.after(0, lambda: self.tratar_erro_login_view(f"Erro no servidor: Código {response.status_code}"))
        except Exception as e:
            self.after(0, lambda: self.tratar_erro_login_view(f"Falha de conexão com o servidor: {e}"))

    def tratar_sucesso_login_view(self):
        messagebox.showinfo("Sucesso", "Autenticação realizada com sucesso!")
        self.btn_entrar.configure(state="normal", text="Entrar")
        self.entry_user.delete(0, "end")
        self.entry_pass.delete(0, "end")
        self.atualizar_botoes_auth()
        self.show_view("dashboard")

    def tratar_erro_login_view(self, msg):
        messagebox.showerror("Erro de Login", msg)
        self.btn_entrar.configure(state="normal", text="Entrar")

    def init_view_gerenciamento(self):
        self.view_gerenciamento = ctk.CTkFrame(self.frame_content, fg_color="transparent")
        
        self.impressora_editando_id = None
        self.dados_servidor = None
        self.perfis_cache = {}

        self.frame_info_agente = ctk.CTkFrame(self.view_gerenciamento, fg_color="#064e3b", border_color="#10b981", border_width=1, corner_radius=8)
        self.frame_info_agente.pack(fill="x", padx=20, pady=(5, 0))
        
        lbl_info = ctk.CTkLabel(
            self.frame_info_agente,
            text=f"Orquestração Centralizada Ativa • ID do Agente: {get_agent_id()}\nAs impressoras devem ser cadastradas e associadas a este agente no painel administrativo do Django.",
            font=("Inter", 11, "bold"),
            text_color="#34d399",
            justify="center"
        )
        lbl_info.pack(pady=10)

        self.frame_form = ctk.CTkFrame(self.view_gerenciamento, fg_color="#111218", border_color="#1d1e26", border_width=1)
        self.frame_form.pack(fill="x", padx=20, pady=(10, 15))

        self.lbl_form = ctk.CTkLabel(self.frame_form, text="ADICIONAR / EDITAR DISPOSITIVO", font=("Inter", 11, "bold"), text_color="#94a3b8")
        self.lbl_form.grid(row=0, column=0, columnspan=5, padx=15, pady=(10, 5), sticky="w")

        self.entry_serial = ctk.CTkEntry(self.frame_form, placeholder_text="Número de Série (Ex: CANON_MB5410_REC)", width=250, fg_color="#181920", border_color="#282933")
        self.entry_serial.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.btn_buscar = ctk.CTkButton(self.frame_form, text="Buscar no Servidor", width=150, fg_color="#3b82f6", hover_color="#1d4ed8", font=("Inter", 11, "bold"), command=self.buscar_no_servidor_thread)
        self.btn_buscar.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.frame_passo2 = ctk.CTkFrame(self.frame_form, fg_color="transparent")
        
        self.entry_nome = ctk.CTkEntry(self.frame_passo2, placeholder_text="Setor / Nome Local", width=180, fg_color="#181920", border_color="#282933")
        self.entry_nome.grid(row=0, column=0, padx=4, pady=10, sticky="w")

        self.entry_ip = ctk.CTkEntry(self.frame_passo2, placeholder_text="IP Address / Hostname", width=130, fg_color="#181920", border_color="#282933")
        self.entry_ip.grid(row=0, column=1, padx=4, pady=10, sticky="w")

        self.combo_perfil_oid = ctk.CTkComboBox(self.frame_passo2, values=["Carregando perfis..."], width=180, fg_color="#181920", border_color="#282933")
        self.combo_perfil_oid.grid(row=0, column=2, padx=4, pady=10, sticky="w")

        self.btn_salvar = ctk.CTkButton(self.frame_passo2, text="Salvar", width=90, fg_color="#10b981", hover_color="#059669", font=("Inter", 11, "bold"), command=self.salvar_impressora)
        self.btn_salvar.grid(row=0, column=3, padx=4, pady=10, sticky="w")

        ctk.CTkLabel(self.view_gerenciamento, text="DISPOSITIVOS CADASTRADOS (CACHE LOCAL)", font=("Inter", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=20, pady=(5, 5))
        
        self.frame_footer = ctk.CTkFrame(self.view_gerenciamento, fg_color="transparent")
        self.frame_footer.pack(side="bottom", fill="x", padx=20, pady=(10, 15))
        
        self.btn_exportar = ctk.CTkButton(self.frame_footer, text="Exportar Configurações", width=160, height=30, fg_color="#374151", hover_color="#1f2937", font=("Inter", 11, "bold"), command=self.exportar_configuracoes)
        self.btn_exportar.pack(side="left", padx=(0, 10))
        
        self.btn_importar = ctk.CTkButton(self.frame_footer, text="Importar Configurações", width=160, height=30, fg_color="#374151", hover_color="#1f2937", font=("Inter", 11, "bold"), command=self.importar_configuracoes)
        self.btn_importar.pack(side="left")
        
        self.scroll_lista = ctk.CTkScrollableFrame(self.view_gerenciamento, fg_color="#111218", border_color="#1d1e26", border_width=1)
        self.scroll_lista.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        
        threading.Thread(target=lambda: asyncio.run(self.carregar_perfis_oid_async()), daemon=True).start()
        
        self.atualizar_lista_gerenciamento()

    def buscar_no_servidor_thread(self):
        serial = self.entry_serial.get().strip()
        if not serial:
            messagebox.showerror("Erro", "Insira um número de série.")
            return

        self.btn_buscar.configure(state="disabled", text="Buscando...")
        threading.Thread(target=lambda: asyncio.run(self.executar_busca_servidor_async(serial)), daemon=True).start()

    async def executar_busca_servidor_async(self, serial):
        url = f"{AppConfig.get_server_url()}/api/printer/search/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"serial": serial}, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    self.after(0, lambda: self.tratar_sucesso_busca(data))
                else:
                    self.after(0, lambda: self.tratar_erro_busca(f"Impressora não localizada no servidor: {response.status_code}"))
        except Exception as e:
            self.after(0, lambda: self.tratar_erro_busca(f"Erro de rede: {e}"))

    def tratar_sucesso_busca(self, data):
        self.btn_buscar.configure(state="normal", text="Buscar no Servidor")
        self.dados_servidor = data
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, data.get("nome_local", ""))
        self.entry_ip.delete(0, "end")
        self.entry_ip.insert(0, data.get("ip_address", ""))
        
        self.frame_passo2.pack(fill="x", padx=20, pady=(0, 10))
        
        perfil = data.get("nome_perfil", "")
        if perfil:
            self.combo_perfil_oid.set(perfil)
        
        messagebox.showinfo("Sucesso", f"Impressora localizada!\nMarca: {data.get('marca')}\nModelo: {data.get('modelo')}")

    def tratar_erro_busca(self, msg):
        self.btn_buscar.configure(state="normal", text="Buscar no Servidor")
        messagebox.showerror("Erro", msg)

    async def carregar_perfis_oid_async(self):
        url = f"{AppConfig.get_server_url()}/api/perfis-oid/listar/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    perfis = response.json()
                    self.perfis_cache = {p["nome"]: p for p in perfis}
                    nomes = list(self.perfis_cache.keys())
                    self.after(0, lambda: self.atualizar_combobox_perfis(nomes))
                else:
                    self.after(0, lambda: self.combo_perfil_oid.configure(values=["Erro ao carregar"]))
        except Exception:
            self.after(0, lambda: self.combo_perfil_oid.configure(values=["Erro de rede"]))

    def atualizar_combobox_perfis(self, nomes):
        self.combo_perfil_oid.configure(values=nomes)
        if nomes:
            self.combo_perfil_oid.set(nomes[0])

    def salvar_impressora(self):
        state_orig = self.entry_serial.cget("state")
        self.entry_serial.configure(state="normal")
        serial = self.entry_serial.get().strip()
        self.entry_serial.configure(state=state_orig)

        nome = self.entry_nome.get().strip()
        ip = self.entry_ip.get().strip()
        perfil = self.combo_perfil_oid.get()

        if not serial or not nome or not ip:
            messagebox.showerror("Erro", "Preencha todos os campos do Passo 2.")
            return

        perfil_dados = self.perfis_cache.get(perfil, {})
        oids = perfil_dados.get("oids", {})

        if self.impressora_editando_id:
            confirm = messagebox.askyesno(
                "Confirmar Alterações",
                f"Tem certeza de que deseja salvar as alterações para a impressora?\n\n"
                f"• Número de Série: {serial}\n"
                f"• Nome/Setor: {nome}\n"
                f"• IP: {ip}\n"
                f"• Perfil OID: {perfil}"
            )
            if not confirm:
                return

            for imp in self.impressoras_cadastradas:
                if imp["id"] == self.impressora_editando_id:
                    imp["nome"] = nome
                    imp["ip"] = ip
                    imp["serial_inicial"] = serial
                    imp["perfil_oid"] = perfil
                    imp["oids"] = oids
                    if self.dados_servidor:
                        imp["marca"] = self.dados_servidor.get("marca", imp.get("marca", "Canon"))
                        imp["modelo"] = self.dados_servidor.get("modelo", imp.get("modelo", "Generic"))
                    break
            self.impressora_editando_id = None
            self.btn_salvar.configure(text="Salvar")
        else:
            if any(imp["ip"] == ip for imp in self.impressoras_cadastradas):
                messagebox.showerror("Erro", "Já existe uma impressora com este IP Address.")
                return

            confirm = messagebox.askyesno(
                "Confirmar Cadastro",
                f"Tem certeza de que deseja cadastrar este novo dispositivo?\n\n"
                f"• Número de Série: {serial}\n"
                f"• Nome/Setor: {nome}\n"
                f"• IP: {ip}\n"
                f"• Perfil OID: {perfil}"
            )
            if not confirm:
                return

            marca = "Canon"
            modelo = "Generic"
            if self.dados_servidor:
                marca = self.dados_servidor.get("marca", "Canon")
                modelo = self.dados_servidor.get("modelo", "Generic")

            nova = {
                "id": ip,
                "nome": nome,
                "ip": ip,
                "serial_inicial": serial,
                "marca": marca,
                "modelo": modelo,
                "perfil_oid": perfil,
                "oids": oids
            }
            self.impressoras_cadastradas.append(nova)

        salvar_no_json(self.impressoras_cadastradas)
        self.entry_serial.configure(state="normal")
        self.entry_serial.delete(0, "end")
        self.entry_nome.delete(0, "end")
        self.entry_ip.delete(0, "end")
        self.dados_servidor = None

        self.atualizar_lista_gerenciamento()
        self.reconstruir_cards_dashboard()
        messagebox.showinfo("Sucesso", "Dispositivo gravado com sucesso no cache local!")

    def atualizar_lista_gerenciamento(self):
        for widget in self.scroll_lista.winfo_children():
            widget.destroy()

        for imp in self.impressoras_cadastradas:
            linha = ctk.CTkFrame(self.scroll_lista, fg_color="transparent")
            linha.pack(fill="x", padx=10, pady=5)

            ctk.CTkLabel(linha, text=f"{imp['nome']} - {imp['modelo']} ({imp['ip']})", font=("Inter", 11), text_color="#ffffff").pack(side="left")

            btn_del = ctk.CTkButton(linha, text="Remover", width=70, height=24, fg_color="#ef4444", hover_color="#dc2626", font=("Inter", 10, "bold"), command=lambda i=imp["id"]: self.deletar_impressora(i))
            btn_del.pack(side="right", padx=5)

            btn_edit = ctk.CTkButton(linha, text="Editar", width=70, height=24, fg_color="#3b82f6", hover_color="#1d4ed8", font=("Inter", 10, "bold"), command=lambda i=imp: self.editar_impressora(i))
            btn_edit.pack(side="right")

    def deletar_impressora(self, id_imp):
        imp_obj = next((i for i in self.impressoras_cadastradas if i["id"] == id_imp), None)
        nome_imp = imp_obj["nome"] if imp_obj else id_imp
        
        confirm = messagebox.askyesno(
            "Confirmar Remoção",
            f"Tem certeza de que deseja remover a impressora '{nome_imp}' ({id_imp}) do cache local?"
        )
        if not confirm:
            return

        self.impressoras_cadastradas = [i for i in self.impressoras_cadastradas if i["id"] != id_imp]
        salvar_no_json(self.impressoras_cadastradas)
        self.atualizar_lista_gerenciamento()
        self.reconstruir_cards_dashboard()

    def editar_impressora(self, imp):
        self.impressora_editando_id = imp["id"]
        self.entry_serial.configure(state="normal")
        self.entry_serial.delete(0, "end")
        self.entry_serial.insert(0, imp.get("serial_inicial", ""))
        self.entry_serial.configure(state="disabled")
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, imp.get("nome", ""))
        self.entry_ip.delete(0, "end")
        self.entry_ip.insert(0, imp.get("ip", ""))
        if imp.get("perfil_oid"):
            self.combo_perfil_oid.set(imp["perfil_oid"])
        self.btn_salvar.configure(text="Atualizar")

    def exportar_configuracoes(self):
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title="Exportar Configurações do Prisma"
        )
        if not file_path:
            return
            
        try:
            url = AppConfig.get_api_url()
            impressoras = self.impressoras_cadastradas
            
            data = {
                "version": "1.0",
                "django_api_url": url,
                "impressoras": impressoras
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            messagebox.showinfo("Sucesso", "Configurações exportadas com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar configurações: {e}")

    def importar_configuracoes(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")],
            title="Importar Configurações do Prisma"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "django_api_url" not in data or "impressoras" not in data:
                messagebox.showerror("Erro", "Arquivo de configuração inválido.")
                return
                
            AppConfig.update(data["django_api_url"])
            self.impressoras_cadastradas = data["impressoras"]
            salvar_no_json(self.impressoras_cadastradas)
            
            self.atualizar_lista_gerenciamento()
            self.reconstruir_cards_dashboard()
            messagebox.showinfo("Sucesso", "Configurações importadas com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao importar configurações: {e}")

    def card_kpi(self, pai, col, titulo, valor, icone, cor_val="#ffffff"):
        f = ctk.CTkFrame(pai, fg_color="#111218", corner_radius=10, border_color="#1d1e26", border_width=1, height=85)
        f.grid(row=0, column=col, padx=6, sticky="nsew")
        f.pack_propagate(False)
        lbl_t = ctk.CTkLabel(f, text=titulo, font=("Inter", 10, "bold"), text_color="#94a3b8")
        lbl_t.pack(anchor="w", padx=15, pady=(12, 0))
        lbl_v = ctk.CTkLabel(f, text=valor, font=("Inter", 24, "bold"), text_color=cor_val)
        lbl_v.pack(side="left", padx=15, pady=(0, 10))
        lbl_i = ctk.CTkLabel(f, text=icone, font=("Inter", 14), text_color="#444650", fg_color="#181920", width=32, height=32, corner_radius=6)
        lbl_i.pack(side="right", padx=15, pady=(0, 10))
        return lbl_v



    def reconstruir_cards_dashboard(self, disparar=True):
        for widget in self.frame_grid_dispositivos.winfo_children():
            widget.destroy()
        self.cards_ui.clear()

        for index, imp in enumerate(self.impressoras_cadastradas):
            row = index // 4
            col = index % 4
            
            marca_lower = str(imp.get("marca", "")).lower()
            modelo_lower = str(imp.get("modelo", "")).lower()
            
            if "epson" in marca_lower or "epson" in modelo_lower:
                self.criar_card_epson_dinamico(imp["id"], imp, row, col, ocultar_sub_contadores=("plotter" in marca_lower or "plotter" in modelo_lower))
            else:
                self.criar_card_canon_dinamico(imp["id"], imp, row, col)

        self.kpi_total.configure(text=str(len(self.impressoras_cadastradas)))
        if disparar:
            self.disparar_coleta()

    def criar_card_canon_dinamico(self, id_imp, dados, r, c):
        card = ctk.CTkFrame(self.frame_grid_dispositivos, fg_color="#111218", corner_radius=12, border_color="#1d1e26", border_width=1)
        card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(15, 2))
        ctk.CTkLabel(head, text=dados["nome"], font=("Inter", 13, "bold"), text_color="#ffffff").pack(side="left")
        badge = ctk.CTkLabel(head, text="• Status", font=("Inter", 9, "bold"), text_color="#94a3b8", fg_color="#1d1e26", corner_radius=12, width=60, height=20)
        badge.pack(side="right")

        ctk.CTkLabel(card, text=f"{dados.get('marca', 'Canon')} {dados.get('modelo', 'Maxify')}", font=("Inter", 11), text_color="#94a3b8").pack(anchor="w", padx=18)
        
        g = ctk.CTkFrame(card, fg_color="transparent")
        g.pack(fill="x", padx=18, pady=(10, 0))
        self.bloco(g, "Endereço IP", dados["ip"], "left")
        _, lbl_serial = self.bloco(g, "Nº de Série", dados["serial_inicial"], "right")

        ctk.CTkFrame(card, fg_color="#1d1e26", height=1).pack(fill="x", padx=18, pady=12)
        g2 = ctk.CTkFrame(card, fg_color="transparent")
        g2.pack(fill="x", padx=18)
        _, lbl_contador = self.bloco(g2, "CONTADOR GERAL", "---", "left", dest=True)
        _, lbl_uptime = self.bloco(g2, "UPTIME", "---", "right", dest=True)

        ctk.CTkFrame(card, fg_color="#1d1e26", height=1).pack(fill="x", padx=18, pady=12)
        f_t = ctk.CTkFrame(card, fg_color="transparent")
        f_t.pack(fill="x", padx=18, pady=(2, 0))
        ctk.CTkLabel(f_t, text="● Black Toner", font=("Inter", 11), text_color="#ffffff").pack(side="left")
        lbl_toner_pct = ctk.CTkLabel(f_t, text="---", font=("Inter", 11, "bold"), text_color="#ffffff")
        lbl_toner_pct.pack(side="right")

        barra_toner = ctk.CTkProgressBar(card, height=6, fg_color="#1c1d24", progress_color="#ffffff", corner_radius=4)
        barra_toner.set(0)
        barra_toner.pack(fill="x", padx=18, pady=(4, 12))

        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=18, pady=(0, 12))
        self.bloco(foot, "MENSAGEM DE PAINEL", "Aguardando...", "left")
        lbl_painel_msg = foot.winfo_children()[-1].winfo_children()[-1]

        self.cards_ui[id_imp] = {
            "badge": badge, "lbl_serial": lbl_serial, "lbl_contador": lbl_contador,
            "lbl_uptime": lbl_uptime, "lbl_toner_pct": lbl_toner_pct, "barra_toner": barra_toner,
            "lbl_painel_msg": lbl_painel_msg, "modelo_tipo": "canon"
        }

    def criar_card_epson_dinamico(self, id_imp, dados, r, c, ocultar_sub_contadores=False):
        card = ctk.CTkFrame(self.frame_grid_dispositivos, fg_color="#111218", corner_radius=12, border_color="#1d1e26", border_width=1)
        card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(15, 2))
        ctk.CTkLabel(head, text=dados["nome"], font=("Inter", 13, "bold"), text_color="#ffffff").pack(side="left")
        badge = ctk.CTkLabel(head, text="• Status", font=("Inter", 9, "bold"), text_color="#94a3b8", fg_color="#1d1e26", corner_radius=12, width=60, height=20)
        badge.pack(side="right")

        ctk.CTkLabel(card, text=f"{dados.get('marca', 'Epson')} {dados.get('modelo', 'L15160')}", font=("Inter", 11), text_color="#94a3b8").pack(anchor="w", padx=18)

        g = ctk.CTkFrame(card, fg_color="transparent")
        g.pack(fill="x", padx=18, pady=(10, 0))
        self.bloco(g, "Endereço IP", dados["ip"], "left")
        _, lbl_serial = self.bloco(g, "Nº de Série", dados["serial_inicial"], "right")

        ctk.CTkFrame(card, fg_color="#1d1e26", height=1).pack(fill="x", padx=18, pady=8)
        g2 = ctk.CTkFrame(card, fg_color="transparent")
        g2.pack(fill="x", padx=18)
        _, lbl_contador = self.bloco(g2, "CONTADOR TOTAL", "---", "left", dest=True)
        _, lbl_uptime = self.bloco(g2, "UPTIME", "---", "right", dest=True)

        lbl_a4, lbl_a3, lbl_a5 = None, None, None
        if not ocultar_sub_contadores:
            g3 = ctk.CTkFrame(card, fg_color="transparent")
            g3.pack(fill="x", padx=18, pady=(6, 0))
            _, lbl_a4 = self.bloco(g3, "A4", "---", "left")
            _, lbl_a3 = self.bloco(g3, "A3", "---", "left")
            _, lbl_a5 = self.bloco(g3, "A5", "---", "right")

        ctk.CTkFrame(card, fg_color="#1d1e26", height=1).pack(fill="x", padx=18, pady=8)
        lbl_bk, bar_bk = self.criar_linha_suprimento(card, "● Black", "#ffffff")
        lbl_c, bar_c = self.criar_linha_suprimento(card, "● Cyan", "#22d3ee")
        lbl_m, bar_m = self.criar_linha_suprimento(card, "● Magenta", "#ec4899")
        lbl_y, bar_y = self.criar_linha_suprimento(card, "● Yellow", "#facc15")
        lbl_manut, bar_manut = self.criar_linha_suprimento(card, "⚙ Cx. Manut.", "#a855f7")

        ctk.CTkFrame(card, fg_color="#1d1e26", height=1).pack(fill="x", padx=18, pady=6)
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=18, pady=(0,10))
        self.bloco(foot, "MENSAGEM DE PAINEL", "Aguardando...", "left")
        lbl_painel_msg = foot.winfo_children()[-1].winfo_children()[-1]

        self.cards_ui[id_imp] = {
            "badge": badge, "lbl_serial": lbl_serial, "lbl_contador": lbl_contador, "lbl_uptime": lbl_uptime,
            "lbl_a4": lbl_a4, "lbl_a3": lbl_a3, "lbl_a5": lbl_a5, "lbl_painel_msg": lbl_painel_msg,
            "lbl_bk": lbl_bk, "bar_bk": bar_bk, "lbl_c": lbl_c, "bar_c": bar_c, "lbl_m": lbl_m, "bar_m": bar_m,
            "lbl_y": lbl_y, "bar_y": bar_y, "lbl_manut": lbl_manut, "bar_manut": bar_manut, "modelo_tipo": "epson"
        }

    def criar_linha_suprimento(self, card, nome, cor_progresso):
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=1)
        ctk.CTkLabel(f, text=nome, font=("Inter", 10), text_color="#ffffff").pack(side="left")
        lbl_p = ctk.CTkLabel(f, text="---", font=("Inter", 10, "bold"), text_color="#ffffff")
        lbl_p.pack(side="right")
        bar = ctk.CTkProgressBar(card, height=4, fg_color="#1c1d24", progress_color=cor_progresso, corner_radius=2)
        bar.set(0)
        bar.pack(fill="x", padx=18, pady=(0, 2))
        return lbl_p, bar

    def bloco(self, pai, t, v, lado, dest=False):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(side=lado, fill="x", expand=True)
        align = "w" if lado == "left" else "e"
        lbl_t = ctk.CTkLabel(f, text=t, font=("Inter", 10, "bold" if dest else "normal"), text_color="#94a3b8", anchor=align)
        lbl_t.pack(fill="x")
        lbl_v = ctk.CTkLabel(f, text=v, font=("Inter", 14 if dest else 11, "bold" if dest else "normal"), text_color="#ffffff", anchor=align)
        lbl_v.pack(fill="x")
        return lbl_t, lbl_v

    def configurar_automacao(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
        try:
            valor = float(self.entry_tempo.get())
            if valor < 1: valor = 1
        except ValueError:
            valor = 30.0

        unidade = self.combo_unidade.get()
        if unidade == "Segundos":
            multiplicador = 1000
        elif unidade == "Minutos":
            multiplicador = 60 * 1000
        else:
            multiplicador = 60 * 60 * 1000
            
        ms = int(valor * multiplicador)
        self.loop_automacao(ms)

    def loop_automacao(self, tempo_ms):
        self.disparar_coleta()
        self.timer_job = self.after(tempo_ms, lambda: self.loop_automacao(tempo_ms))

    def disparar_coleta(self):
        self.btn_atualizar.configure(state="disabled", text="Pooling...")
        threading.Thread(target=lambda: asyncio.run(self.executar_todas_coletas_async()), daemon=True).start()

    async def executar_todas_coletas_async(self):
        # 1. Buscar impressoras do servidor (Orquestração Centralizada)
        agent_id = get_agent_id()
        url_tasks = f"{AppConfig.get_server_url()}/api/v1/tarefas/"
        
        printers_list = []
        sucesso_busca = False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url_tasks, params={"agent_id": agent_id}, timeout=10.0)
                if response.status_code == 200:
                    printers_list = response.json()
                    sucesso_busca = True
                else:
                    print(f"[Erro API] Falha ao buscar tarefas (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"[Erro API] Falha de conexão ao buscar tarefas: {e}")
            
        if sucesso_busca and isinstance(printers_list, list):
            seriais_remotos = {
                p.get("serial_number") or p.get("serial_inicial")
                for p in printers_list if (p.get("serial_number") or p.get("serial_inicial"))
            }
            ips_remotos = {
                p.get("ip") or p.get("ip_ou_hostname")
                for p in printers_list if (p.get("ip") or p.get("ip_ou_hostname"))
            }

            novas_impressoras = []

            # 1. Filtra impressoras que pertencem a este cliente: se foram removidas do cliente no servidor web, remove do agente
            for existing in self.impressoras_cadastradas:
                s_exist = existing.get("serial_inicial")
                ip_exist = existing.get("ip")

                if AppConfig.get_cliente_id():
                    estava_no_servidor = (s_exist in seriais_remotos) or (ip_exist in ips_remotos)
                    # Se foi desassociada/removida no servidor web, remove também do agente local
                    if not estava_no_servidor:
                        continue

                novas_impressoras.append(existing)

            # 2. Adiciona/atualiza impressoras enviadas pelo servidor
            mapa_novas_serial = {imp.get("serial_inicial"): imp for imp in novas_impressoras if imp.get("serial_inicial")}
            mapa_novas_ip = {imp.get("ip"): imp for imp in novas_impressoras if imp.get("ip")}

            for p in printers_list:
                ip = p.get("ip") or p.get("ip_ou_hostname") or ""
                modelo = p.get("modelo") or "Genérica"
                serial_number = p.get("serial_number") or p.get("serial_inicial") or (f"MOCK_{ip.replace('.', '_')}" if ip else "NO_SERIAL")
                nome = p.get("nome") or f"{modelo} ({ip if ip else serial_number})"
                marca = p.get("marca") or "Generic"
                perfil_oid = p.get("perfil_oid") or ""

                cache_imp = mapa_novas_serial.get(serial_number) or (mapa_novas_ip.get(ip) if ip else None)

                if cache_imp:
                    if ip and cache_imp.get("ip") != ip:
                        cache_imp["ip"] = ip
                    if modelo and cache_imp.get("modelo") in ("Genérica", "Generic", ""):
                        cache_imp["modelo"] = modelo
                    if perfil_oid and not cache_imp.get("perfil_oid"):
                        cache_imp["perfil_oid"] = perfil_oid
                else:
                    nova_entry = {
                        "id": ip or serial_number,
                        "nome": nome,
                        "ip": ip,
                        "modelo": modelo,
                        "marca": marca,
                        "serial_inicial": serial_number,
                        "perfil_oid": perfil_oid,
                        "oids": {}
                    }
                    novas_impressoras.append(nova_entry)
                    mapa_novas_serial[serial_number] = nova_entry
                    if ip:
                        mapa_novas_ip[ip] = nova_entry

            mudou = (len(novas_impressoras) != len(self.impressoras_cadastradas) or
                     any(novas_impressoras[i] != self.impressoras_cadastradas[i] for i in range(len(novas_impressoras))))

            if mudou:
                self.impressoras_cadastradas = novas_impressoras
                salvar_no_json(self.impressoras_cadastradas)
                self.after(0, lambda: self.reconstruir_cards_dashboard(disparar=False))

        async with httpx.AsyncClient() as client:
            tarefas = []
            for imp in self.impressoras_cadastradas:
                tarefas.append(self.executar_coleta_dinamica(client, imp))
            
            resultados = []
            if tarefas:
                resultados = await asyncio.gather(*tarefas)
                
        modificado = False
        reconstruir = False
        novas_impressoras = list(self.impressoras_cadastradas)
        
        for res in resultados:
            if not res:
                continue
            if res.get("status") == "delete":
                id_to_del = res["id"]
                novas_impressoras = [i for i in novas_impressoras if i["id"] != id_to_del]
                modificado = True
                reconstruir = True
            elif res.get("status") == "update":
                id_to_up = res["id"]
                for imp in novas_impressoras:
                    if imp["id"] == id_to_up:
                        imp["marca"] = res["marca"]
                        imp["modelo"] = res["modelo"]
                        imp["oids"] = res["oids"]
                        imp["perfil_oid"] = res["perfil_oid"]
                        modificado = True
                        break
                        
        if modificado:
            self.impressoras_cadastradas = novas_impressoras
            salvar_no_json(self.impressoras_cadastradas)
            
        if reconstruir:
            self.after(0, lambda: self.reconstruir_cards_dashboard(disparar=False))
            
        self.after(0, lambda: self.btn_atualizar.configure(state="normal", text="Forçar Atualização"))
        self.after(0, self.recalcular_kpis_globais)

    async def enviar_payload_django(self, client, payload):
        try:
            res = await client.post(AppConfig.get_api_url(), json=payload, timeout=5.0)
            if res.status_code not in (200, 201):
                print(f"[Erro API] Código de status do servidor: {res.status_code} - {res.text}")
            else:
                print(f"[Sucesso API] Dados enviados com sucesso para {payload['ip']}.")
        except Exception as e:
            print(f"[Erro API] Falha na conexão com o servidor Django: {e}")

    async def executar_coleta_dinamica(self, client, imp):
        ip = imp["ip"]
        id_imp = imp["id"]
        
        # Tenta obter o Serial Number real via SNMP (OID: 1.3.6.1.2.1.43.5.1.1.17.1)
        serial_detectado = await snmp_safe_get(ip, "1.3.6.1.2.1.43.5.1.1.17.1", decode=True)
        
        # Se falhar ou for N/A, tentamos usar o cache local (serial_inicial) ou gerar um mock
        if not serial_detectado or serial_detectado == "N/A":
            serial_detectado = imp.get("serial_inicial")
            if not serial_detectado or serial_detectado.startswith("MOCK_") or serial_detectado == "N/A":
                modelo_limpo = imp.get("modelo", "Generic")
                serial_detectado = f"SIM_{modelo_limpo.upper().replace(' ', '_')}_{ip.replace('.', '_')}"
                
        imp["serial_inicial"] = serial_detectado
        serial_inicial = serial_detectado
        
        # 1. Buscar configurações de OID do Django
        url = f"{AppConfig.get_server_url()}/api/printer/search/"
        oids = {}
        marca = imp.get("marca", "Canon")
        modelo = imp.get("modelo", "Generic")
        perfil_oid = imp.get("perfil_oid", "")
        
        acao_retorno = {"status": "no_change"}
        
        try:
            response = await client.get(url, params={"serial": serial_inicial}, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                marca = data.get("marca", marca)
                modelo = data.get("modelo", modelo)
                oids_raw = data.get("oids", {})
                perfil_oid = data.get("nome_perfil", perfil_oid)
                
                # --- NORMALIZAÇÃO CRUCIAL DE OIDs ---
                oids = {}
                mapeamento_chaves = {
                    "oid_toner_level": "toner_atual",
                    "oid_toner_full": "toner_full",
                    "oid_tinta_preta": "tinta_preta",
                    "oid_tinta_ciano": "tinta_ciano",
                    "oid_tinta_magenta": "tinta_magenta",
                    "oid_tinta_amarela": "tinta_amarela",
                    "oid_caixa_manutencao": "caixa_manutencao",
                    "oid_counter_total": "contador_total",
                    "oid_counter_mono": "contador_a4",
                    "oid_counter_color": "contador_a3",
                    "oid_serial_number": "N_S",
                    "oid_tempo_ligada": "tempo_ligada",
                    "oid_mensagem_painel": "mensagem_painel"
                }
                
                for k, v in oids_raw.items():
                    if k in mapeamento_chaves:
                        oids[mapeamento_chaves[k]] = v
                    oids[k] = v

                imp["oids"] = oids
                
                if (imp.get("marca") != marca or 
                    imp.get("modelo") != modelo or 
                    imp.get("perfil_oid") != perfil_oid):
                    
                    acao_retorno = {
                        "status": "update",
                        "id": id_imp,
                        "marca": marca,
                        "modelo": modelo,
                        "oids": oids,
                        "perfil_oid": perfil_oid
                    }
                    imp["marca"] = marca
                    imp["modelo"] = modelo
                    imp["perfil_oid"] = perfil_oid
            elif response.status_code == 404:
                print(f"[Aviso API] Impressora {serial_inicial} não encontrada no servidor (404). Marcando para remoção.")
                self.after(0, lambda: self.atualizar_ui_offline(id_imp))
                return {"status": "delete", "id": id_imp}
            else:
                oids = imp.get("oids", {})
                print(f"[Aviso API] Status {response.status_code} ao buscar {serial_inicial}. Usando cache local.")
        except Exception as e:
            oids = imp.get("oids", {})
            print(f"[Erro API] Falha de rede ao buscar {serial_inicial}: {e}. Usando cache local.")
            
        if not oids:
            self.after(0, lambda: self.atualizar_ui_offline(id_imp))
            return acao_retorno
            
        # 2. Coletar dados via SNMP
        chaves_alvo = ["contador_total", "tempo_ligada", "N_S", "mensagem_painel", "toner_atual", "toner_full", 
                       "tinta_preta", "tinta_ciano", "tinta_magenta", "tinta_amarela", "caixa_manutencao", "contador_a4", "contador_a3"]
                       
        tarefas_snmp = []
        chaves_coletadas = []
        for chave in chaves_alvo:
            oid = oids.get(chave)
            if oid:
                decode = (chave in ("N_S", "mensagem_painel"))
                tarefas_snmp.append(snmp_safe_get(ip, oid, decode=decode))
                chaves_coletadas.append(chave)
            
        resultados_snmp = await asyncio.gather(*tarefas_snmp)
        resultados = dict(zip(chaves_coletadas, resultados_snmp))
        
        is_online = any(v != "N/A" for v in resultados_snmp)
        
        marca_lower = marca.lower()
        modelo_lower = modelo.lower()
        eh_epson = "epson" in marca_lower or "epson" in modelo_lower
        eh_canon = "canon" in marca_lower or "canon" in modelo_lower
        eh_plotter = "plotter" in marca_lower or "plotter" in modelo_lower
        
        # Sem simulação para impressoras offline, permitindo o fluxo seguro de desconexão.

        # 3. Formatar dados coletados
        uptime = formatar_uptime(resultados.get("tempo_ligada", "N/A"))
        painel = formatar_painel(resultados.get("mensagem_painel", "N/A"))
        serial_detectado = resultados.get("N_S")
        if not serial_detectado or serial_detectado == "N/A":
            serial_detectado = serial_inicial
            
        contador_total = resultados.get("contador_total")
        contador_total_val = int(contador_total) if (is_online and str(contador_total).isdigit()) else None
        
        suprimentos_payload = {}
        
        # 4. Atualizar UI
        if eh_canon:
            toner_atual = resultados.get("toner_atual")
            toner_full = resultados.get("toner_full")
            
            pct_toner = 0.0
            
            # --- TRATAMENTO ROBUSTO PARA VALORES DE TONER CANON (Especiais / Negativos) ---
            try:
                if isinstance(toner_atual, str) and toner_atual.isdigit():
                    toner_atual = int(toner_atual)
                if isinstance(toner_full, str) and toner_full.isdigit():
                    toner_full = int(toner_full)

                # Se a impressora retorna valores de status de marcador especiais (-3 = baixo, -2 = ok, etc.)
                if isinstance(toner_atual, (int, float)) and toner_atual < 0:
                    if toner_atual == -3:
                        pct_toner = 10.0
                    else:
                        pct_toner = 0.0
                elif isinstance(toner_atual, (int, float)) and isinstance(toner_full, (int, float)) and toner_full > 0:
                    pct_toner = round((toner_atual / toner_full) * 100, 1)
                    pct_toner = max(0.0, min(100.0, pct_toner))
                else:
                    # Fallback para tinta preta se toner_atual falhar
                    bk_val = resultados.get("tinta_preta")
                    if bk_val is not None and bk_val != "N/A":
                        pct_toner = max(0.0, float(bk_val))
                    else:
                        pct_toner = 0.0
            except Exception:
                pct_toner = 0.0
                
            self.after(0, lambda: self.atualizar_ui_canon_card(id_imp, is_online, contador_total_val or "---", uptime, serial_detectado, painel, pct_toner))
            
            suprimentos_payload = {
                "black": pct_toner if is_online else None,
                "cyan": None,
                "magenta": None,
                "yellow": None,
                "caixa_manutencao": None
            }
        else:
            a4 = resultados.get("contador_a4", 0)
            a3 = resultados.get("contador_a3", 0)
            try:
                a4_val = int(a4) if str(a4).isdigit() else 0
                a3_val = int(a3) if str(a3).isdigit() else 0
                total_val = int(contador_total_val) if contador_total_val else 0
                a5_val = max(0, total_val - (a4_val + a3_val))
            except Exception:
                a4_val, a3_val, a5_val = 0, 0, 0
                
            def clean_pct(v):
                try:
                    if v != "N/A" and v is not None:
                        val = float(v)
                        return max(0.0, val)
                    return None
                except Exception:
                    return None
                    
            bk = clean_pct(resultados.get("tinta_preta"))
            cy = clean_pct(resultados.get("tinta_ciano"))
            mg = clean_pct(resultados.get("tinta_magenta"))
            yl = clean_pct(resultados.get("tinta_amarela"))
            mt = clean_pct(resultados.get("caixa_manutencao"))
            
            self.after(0, lambda: self.atualizar_ui_epson_card(
                id_imp, is_online,
                contador_total_val or "---",
                a4_val if not eh_plotter else "---",
                a3_val if not eh_plotter else "---",
                a5_val if not eh_plotter else "---",
                uptime, serial_detectado, painel,
                bk if bk is not None else 0.0,
                cy if cy is not None else 0.0,
                mg if mg is not None else 0.0,
                yl if yl is not None else 0.0,
                mt if mt is not None else 0.0
            ))
            
            suprimentos_payload = {
                "black": bk,
                "cyan": cy,
                "magenta": mg,
                "yellow": yl,
                "caixa_manutencao": mt
            }
            
        # 5. Enviar ao Django
        payload = {
            "ip": ip,
            "serial": serial_detectado,
            "modelo": modelo,
            "status": "Online" if is_online else "Offline",
            "contador_total": contador_total_val,
            "contador_geral": contador_total_val,
            "contador_a4": int(a4) if (eh_epson and not eh_plotter and str(a4).isdigit()) else None,
            "contador_a3": int(a3) if (eh_epson and not eh_plotter and str(a3).isdigit()) else None,
            "contador_a5": a5_val if (eh_epson and not eh_plotter) else None,
            "uptime": uptime if is_online else None,
            "mensagem_painel": painel if is_online else "Inacessível",
            "suprimentos": suprimentos_payload
        }
        
        await self.enviar_payload_django(client, payload)
        return acao_retorno

    def atualizar_ui_canon_card(self, uid, is_online, contador, uptime, serial, painel, pct_toner):
        if uid not in self.cards_ui: return
        ui = self.cards_ui[uid]
        if is_online:
            ui["badge"].configure(text="• Online", text_color="#10b981", fg_color="#064e3b")
            ui["lbl_contador"].configure(text=str(contador))
            ui["lbl_uptime"].configure(text=str(uptime))
            ui["lbl_serial"].configure(text=str(serial))
            ui["lbl_painel_msg"].configure(text=str(painel))
            ui["lbl_toner_pct"].configure(text=f"{pct_toner}%")
            ui["barra_toner"].configure(progress_color="#f59e0b" if pct_toner < 15.0 else "#ffffff")
            ui["barra_toner"].set(pct_toner / 100)
        else:
            self.atualizar_ui_offline(uid)

    def atualizar_ui_epson_card(self, uid, is_online, total, a4, a3, a5, uptime, serial, painel, bk, cy, mg, yl, mt):
        if uid not in self.cards_ui: return
        ui = self.cards_ui[uid]
        if is_online:
            ui["badge"].configure(text="• Online", text_color="#10b981", fg_color="#064e3b")
            ui["lbl_contador"].configure(text=str(total)); ui["lbl_uptime"].configure(text=str(uptime))
            ui["lbl_serial"].configure(text=str(serial))
            if ui["lbl_a4"]: ui["lbl_a4"].configure(text=str(a4))
            if ui["lbl_a3"]: ui["lbl_a3"].configure(text=str(a3))
            if ui["lbl_a5"]: ui["lbl_a5"].configure(text=str(a5))
            ui["lbl_painel_msg"].configure(text=str(painel))
            ui["lbl_bk"].configure(text=f"{bk}%"); ui["bar_bk"].set(bk/100.0)
            ui["lbl_c"].configure(text=f"{cy}%"); ui["bar_c"].set(cy/100.0)
            ui["lbl_m"].configure(text=f"{mg}%"); ui["bar_m"].set(mg/100.0)
            ui["lbl_y"].configure(text=f"{yl}%"); ui["bar_y"].set(yl/100.0)
            ui["lbl_manut"].configure(text=f"{mt}%"); ui["bar_manut"].set(mt/100.0)
        else:
            self.atualizar_ui_offline(uid)

    def atualizar_ui_offline(self, uid):
        if uid not in self.cards_ui: return
        ui = self.cards_ui[uid]
        ui["badge"].configure(text="• Offline", text_color="#f87171", fg_color="#7f1d1d")
        ui["lbl_contador"].configure(text="---"); ui["lbl_uptime"].configure(text="---")
        ui["lbl_painel_msg"].configure(text="Inacessível")
        if ui["modelo_tipo"] == "canon":
            ui["lbl_toner_pct"].configure(text="---")
            ui["barra_toner"].set(0)
        else:
            for k in ["lbl_bk", "lbl_c", "lbl_m", "lbl_y", "lbl_manut"]:
                if k in ui and ui[k]: ui[k].configure(text="---")
            for b in ["bar_bk", "bar_c", "bar_m", "bar_y", "bar_manut"]:
                if b in ui and ui[b]: ui[b].set(0)

    def recalcular_kpis_globais(self):
        on = 0; off = 0; alerta = 0
        for uid, ui in self.cards_ui.items():
            status = ui["badge"].cget("text")
            if "Online" in status:
                on += 1
                if ui["modelo_tipo"] == "canon":
                    txt = ui["lbl_toner_pct"].cget("text").replace("%","")
                    try:
                        if float(txt) < 15.0: alerta += 1
                    except ValueError:
                        pass
                elif ui["modelo_tipo"] == "epson":
                    for k in ["lbl_bk", "lbl_c", "lbl_m", "lbl_y", "lbl_manut"]:
                        txt = ui[k].cget("text").replace("%","")
                        try:
                            if float(txt) < 15.0:
                                alerta += 1
                                break
                        except ValueError:
                            pass
            else:
                off += 1

        self.kpi_online.configure(text=str(on))
        self.kpi_offline.configure(text=str(off))
        self.kpi_alerta_toner.configure(text=str(alerta))

    # --- MÉTODOS DO SYSTEM TRAY / BACKGROUND ---
    def gerar_icone_pillow(self):
        """Gera uma imagem simples para servir de ícone na bandeja."""
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        d.rectangle([(12, 24), (52, 48)], fill="#10b981")
        d.rectangle([(20, 12), (44, 24)], fill="#ffffff")
        d.rectangle([(20, 44), (44, 56)], fill="#ffffff")
        return image

    def iniciar_tray_icon(self):
        def criar_tray():
            menu = (
                item('Abrir Prisma', self.restaurar_janela, default=True),
                item('Forçar Atualização', self.disparar_coleta),
                item('Desconectar / Logout', self.logout_tray),
                pystray.Menu.SEPARATOR,
                item('Encerrar Sistema', self.encerrar_sistema_definitivo)
            )
            self.tray = pystray.Icon("PrismaMonitor", self.gerar_icone_pillow(), "PRISMA Monitoramento", menu)
            self.tray.run()
        
        threading.Thread(target=criar_tray, daemon=True).start()

    def logout_tray(self, icon=None, item=None):
        self.after(0, self.desconectar_usuario)

    def minimizar_para_tray(self):
        self.withdraw()

    def restaurar_janela(self, icon=None, item=None):
        self.after(0, self.deiconify)

    def encerrar_sistema_definitivo(self, icon=None, item=None):
        if self.timer_job: self.after_cancel(self.timer_job)
        self.tray.stop()
        self.quit()


def configurar_inicializacao_windows(habilitar=True):
    """Adiciona ou remove o executável/script do registro do Windows para iniciar junto com o sistema."""
    import sys
    if sys.platform != 'win32':
        return
        
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PrismaMonitor"
        
        if getattr(sys, 'frozen', False):
            # Executável empacotado (.exe)
            cmd = f'"{sys.executable}"'
        else:
            # Script Python executado diretamente
            script_path = os.path.abspath(sys.argv[0])
            cmd = f'"{sys.executable}" "{script_path}"'
            
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        if habilitar:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            print(f"[Autostart] Configurado para iniciar com Windows: {cmd}")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                print("[Autostart] Removido da inicialização do Windows.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[Autostart] Erro ao configurar registro: {e}")


if __name__ == "__main__":
    configurar_inicializacao_windows(True)
    app = DashboardFinal()
    app.mainloop()