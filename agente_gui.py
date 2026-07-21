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
DEFAULT_API_URL = os.environ.get("PRISMA_SERVER_URL", "http://192.170.0.241:8999/api/coleta/")

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
        "django_api_url": DEFAULT_API_URL,
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
        return cls._config.get("django_api_url", DEFAULT_API_URL)
        
    @classmethod
    def get_server_url(cls):
        url = cls.get_api_url()
        return "/".join(url.split("/")[:3])
        
    @classmethod
    def get_cliente_nome(cls):
        return cls._config.get("cliente_nome", "Sem Cliente Associado")
        
    @classmethod
    def get_cliente_id(cls):
        return cls._config.get("cliente_id")
        
    @classmethod
    def update_cliente(cls, cliente_nome, cliente_id):
        cls._config["cliente_nome"] = cliente_nome
        cls._config["cliente_id"] = cliente_id
        salvar_config_servidor(cls._config)

def carregar_do_json():
    """Carrega as impressoras cadastradas do arquivo JSON local."""
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
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
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

        self.title("PRISMA Agente - Coleta SNMP")
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

        # Ícones Dinâmicos
        self.icon_toggle = criar_imagem_icone("menu", "#ffffff")
        self.icon_dashboard = criar_imagem_icone("dashboard", "#ffffff")
        self.icon_cliente = criar_imagem_icone("cliente", "#ffffff")
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

        # Nav: Selecionar Cliente
        self.btn_nav_cliente = ctk.CTkButton(self.frame_sidebar, text="Selecionar Cliente", image=self.icon_cliente, compound="left", font=("Inter", 12, "bold"), text_color="#ffffff", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=lambda: self.show_view("vincular_cliente"))

        # Nav: Login / Auth
        self.btn_nav_auth = ctk.CTkButton(self.frame_sidebar, text="Fazer Login", image=self.icon_login, compound="left", font=("Inter", 12, "bold"), text_color="#10b981", fg_color="transparent", hover_color="#1d1e26", anchor="w", width=40, height=40, corner_radius=8, command=self.alternar_auth)
        self.btn_nav_auth.pack(fill="x", padx=10, pady=(20, 2))

        # --- INITIALIZE SUB-VIEWS ---
        self.init_view_dashboard()
        self.init_view_vincular_cliente()
        self.init_view_login()

        # Reconstruir os cards do Dashboard com as impressoras cadastradas
        self.reconstruir_cards_dashboard(disparar=True)

        # Show Dashboard initially
        self.show_view("dashboard")

        self.configurar_automacao()
        self.atualizar_botoes_auth()
        self.iniciar_tray_icon()

    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar_expanded = False
            self.sidebar_current_width = 60
            self.frame_sidebar.configure(width=60)
            self.btn_toggle.configure(text="", image=self.icon_toggle, anchor="center")
            self.btn_nav_dashboard.configure(text="", anchor="center")
            self.btn_nav_cliente.configure(text="", anchor="center")
            self.btn_nav_auth.configure(text="", anchor="center")
        else:
            self.sidebar_expanded = True
            self.sidebar_current_width = 220
            self.frame_sidebar.configure(width=220)
            self.btn_toggle.configure(text="PRISMA", image=self.icon_toggle, anchor="w")
            self.btn_nav_dashboard.configure(text="Dashboard", anchor="w")
            self.btn_nav_cliente.configure(text="Selecionar Cliente", anchor="w")
            if Session.is_authenticated:
                self.btn_nav_auth.configure(text="Desconectar", image=self.icon_logout, text_color="#ef4444", anchor="w")
            else:
                self.btn_nav_auth.configure(text="Fazer Login", image=self.icon_login, text_color="#10b981", anchor="w")

    def show_view(self, name):
        self.view_dashboard.pack_forget()
        self.view_vincular_cliente.pack_forget()
        self.view_login.pack_forget()

        self.active_view = name

        if name == "dashboard":
            self.view_dashboard.pack(fill="both", expand=True, padx=35, pady=25)
            self.frame_scroll.pack(fill="both", expand=True, padx=0, pady=(5, 10))
            if not getattr(self, "cards_ui", None):
                self.reconstruir_cards_dashboard(disparar=False)
        elif name == "vincular_cliente":
            self.view_vincular_cliente.pack(fill="both", expand=True, padx=35, pady=25)
            self.carregar_clientes_na_view()
        elif name == "login":
            self.view_login.pack(fill="both", expand=True, padx=35, pady=25)

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
        
        self.btn_nav_cliente.pack_forget()
        self.btn_nav_auth.pack_forget()

        if Session.is_authenticated:
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

    def card_kpi(self, parent, col, titulo, valor, icone, cor_val="#ffffff"):
        card = ctk.CTkFrame(parent, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        card.grid(row=0, column=col, padx=5, pady=0, sticky="ew")

        sub = ctk.CTkFrame(card, fg_color="transparent")
        sub.pack(fill="x", padx=15, pady=12)

        left = ctk.CTkFrame(sub, fg_color="transparent")
        left.pack(side="left")

        lbl_t = ctk.CTkLabel(left, text=titulo, font=("Inter", 10, "bold"), text_color="#64748b")
        lbl_t.pack(anchor="w")

        lbl_v = ctk.CTkLabel(left, text=valor, font=("Inter", 22, "bold"), text_color=cor_val)
        lbl_v.pack(anchor="w", pady=(2, 0))

        lbl_ic = ctk.CTkLabel(sub, text=icone, font=("Inter", 18), text_color="#475569")
        lbl_ic.pack(side="right")

        return lbl_v

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

    def reconstruir_cards_dashboard(self, disparar=True):
        for widget in self.frame_grid_dispositivos.winfo_children():
            widget.destroy()

        self.cards_ui = {}
        for index, imp in enumerate(self.impressoras_cadastradas):
            col = index % 4
            row = index // 4
            
            marca = str(imp.get("marca", "")).lower()
            if "canon" in marca:
                card_data = self.criar_card_canon(self.frame_grid_dispositivos, imp)
            else:
                card_data = self.criar_card_epson(self.frame_grid_dispositivos, imp)
                
            card_data["frame"].grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.cards_ui[imp["id"]] = card_data

        self.kpi_total.configure(text=str(len(self.impressoras_cadastradas)))
        if disparar:
            self.disparar_coleta()

    def criar_card_canon(self, parent, imp):
        card = ctk.CTkFrame(parent, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(12, 5))

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left")
        
        lbl_nome = ctk.CTkLabel(info, text=imp["nome"], font=("Inter", 14, "bold"), text_color="#ffffff")
        lbl_nome.pack(anchor="w")
        
        lbl_mod = ctk.CTkLabel(info, text=f"{imp['modelo']} • {imp['ip']}", font=("Inter", 11), text_color="#64748b")
        lbl_mod.pack(anchor="w")

        badge = ctk.CTkLabel(top, text="• Aguardando", font=("Inter", 10, "bold"), text_color="#f59e0b", fg_color="#451a03", corner_radius=12, padx=8, pady=2)
        badge.pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=15, pady=5)

        lbl_c_val = ctk.CTkLabel(body, text="---", font=("Inter", 22, "bold"), text_color="#ffffff")
        lbl_c_val.pack(anchor="w")
        
        lbl_c_txt = ctk.CTkLabel(body, text="Contador Geral", font=("Inter", 10), text_color="#64748b")
        lbl_c_txt.pack(anchor="w")

        grid_info = ctk.CTkFrame(card, fg_color="transparent")
        grid_info.pack(fill="x", padx=15, pady=4)
        grid_info.columnconfigure(0, weight=1)
        grid_info.columnconfigure(1, weight=1)

        lbl_up_head = ctk.CTkLabel(grid_info, text="Uptime", font=("Inter", 9, "bold"), text_color="#64748b")
        lbl_up_head.grid(row=0, column=0, sticky="w")
        
        lbl_ser_head = ctk.CTkLabel(grid_info, text="Nº de Série", font=("Inter", 9, "bold"), text_color="#64748b")
        lbl_ser_head.grid(row=0, column=1, sticky="e")
        
        lbl_up = ctk.CTkLabel(grid_info, text="---", font=("Inter", 11, "bold"), text_color="#cbd5e1")
        lbl_up.grid(row=1, column=0, sticky="w")
        
        lbl_ser = ctk.CTkLabel(grid_info, text="---", font=("Inter", 11, "bold"), text_color="#cbd5e1")
        lbl_ser.grid(row=1, column=1, sticky="e")

        supr = ctk.CTkFrame(card, fg_color="transparent")
        supr.pack(fill="x", padx=15, pady=(5, 10))

        supr_top = ctk.CTkFrame(supr, fg_color="transparent")
        supr_top.pack(fill="x")
        
        ctk.CTkLabel(supr_top, text="Toner Preto (K)", font=("Inter", 10, "bold"), text_color="#94a3b8").pack(side="left")
        lbl_toner_pct = ctk.CTkLabel(supr_top, text="---", font=("Inter", 10, "bold"), text_color="#ffffff")
        lbl_toner_pct.pack(side="right")

        bar = ctk.CTkProgressBar(supr, height=6, fg_color="#1e293b", progress_color="#ffffff")
        bar.pack(fill="x", pady=(4, 0))
        bar.set(0)

        painel = ctk.CTkFrame(card, fg_color="#181920", corner_radius=6)
        painel.pack(fill="x", padx=10, pady=(0, 10))
        
        lbl_msg = ctk.CTkLabel(painel, text="Aguardando varredura...", font=("Inter", 10), text_color="#94a3b8")
        lbl_msg.pack(padx=10, pady=5)

        return {
            "frame": card, "badge": badge, "lbl_contador": lbl_c_val, "lbl_uptime": lbl_up,
            "lbl_serial": lbl_ser, "lbl_toner_pct": lbl_toner_pct, "barra_toner": bar,
            "lbl_painel_msg": lbl_msg, "modelo_tipo": "canon"
        }

    def criar_card_epson(self, parent, imp):
        card = ctk.CTkFrame(parent, fg_color="#111218", border_color="#1d1e26", border_width=1, corner_radius=12)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(12, 5))

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left")
        
        lbl_nome = ctk.CTkLabel(info, text=imp["nome"], font=("Inter", 14, "bold"), text_color="#ffffff")
        lbl_nome.pack(anchor="w")
        
        lbl_mod = ctk.CTkLabel(info, text=f"{imp['modelo']} • {imp['ip']}", font=("Inter", 11), text_color="#64748b")
        lbl_mod.pack(anchor="w")

        badge = ctk.CTkLabel(top, text="• Aguardando", font=("Inter", 10, "bold"), text_color="#f59e0b", fg_color="#451a03", corner_radius=12, padx=8, pady=2)
        badge.pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=15, pady=5)

        lbl_c_val = ctk.CTkLabel(body, text="---", font=("Inter", 22, "bold"), text_color="#ffffff")
        lbl_c_val.pack(anchor="w")
        
        lbl_c_txt = ctk.CTkLabel(body, text="Contador Geral", font=("Inter", 10), text_color="#64748b")
        lbl_c_txt.pack(anchor="w")

        grid_sub = ctk.CTkFrame(card, fg_color="transparent")
        eh_plotter = "sc-p" in str(imp.get("modelo","")).lower() or "surecolor" in str(imp.get("modelo","")).lower()
        
        if not eh_plotter:
            grid_sub.pack(fill="x", padx=15, pady=2)
            lbl_a4 = ctk.CTkLabel(grid_sub, text="---", font=("Inter", 11, "bold"), text_color="#ffffff")
            lbl_a4.grid(row=0, column=0, sticky="w", padx=(0, 10))
            
            lbl_a3 = ctk.CTkLabel(grid_sub, text="---", font=("Inter", 11, "bold"), text_color="#ffffff")
            lbl_a3.grid(row=0, column=1, sticky="w", padx=(0, 10))
            
            lbl_a5 = ctk.CTkLabel(grid_sub, text="---", font=("Inter", 11, "bold"), text_color="#ffffff")
            lbl_a5.grid(row=0, column=2, sticky="w")
        else:
            lbl_a4, lbl_a3, lbl_a5 = None, None, None

        grid_info = ctk.CTkFrame(card, fg_color="transparent")
        grid_info.pack(fill="x", padx=15, pady=4)
        grid_info.columnconfigure(0, weight=1)
        grid_info.columnconfigure(1, weight=1)

        lbl_up_head2 = ctk.CTkLabel(grid_info, text="Uptime", font=("Inter", 9, "bold"), text_color="#64748b")
        lbl_up_head2.grid(row=0, column=0, sticky="w")
        
        lbl_ser_head2 = ctk.CTkLabel(grid_info, text="Nº de Série", font=("Inter", 9, "bold"), text_color="#64748b")
        lbl_ser_head2.grid(row=0, column=1, sticky="e")
        
        lbl_up = ctk.CTkLabel(grid_info, text="---", font=("Inter", 11, "bold"), text_color="#cbd5e1")
        lbl_up.grid(row=1, column=0, sticky="w")
        
        lbl_ser = ctk.CTkLabel(grid_info, text="---", font=("Inter", 11, "bold"), text_color="#cbd5e1")
        lbl_ser.grid(row=1, column=1, sticky="e")

        supr = ctk.CTkFrame(card, fg_color="transparent")
        supr.pack(fill="x", padx=15, pady=(5, 10))

        def add_bar(parent_frame, label, color_bar):
            f = ctk.CTkFrame(parent_frame, fg_color="transparent")
            f.pack(fill="x", pady=2)
            
            lbl_t = ctk.CTkLabel(f, text=label, font=("Inter", 9, "bold"), text_color="#94a3b8", width=15, anchor="w")
            lbl_t.pack(side="left")
            
            bar = ctk.CTkProgressBar(f, height=5, fg_color="#1e293b", progress_color=color_bar)
            bar.pack(side="left", fill="x", expand=True, padx=5)
            bar.set(0)
            
            lbl_pct = ctk.CTkLabel(f, text="---", font=("Inter", 9, "bold"), text_color="#ffffff", width=30, anchor="e")
            lbl_pct.pack(side="right")
            return bar, lbl_pct

        bar_bk, lbl_bk = add_bar(supr, "K", "#ffffff")
        bar_c, lbl_c = add_bar(supr, "C", "#06b6d4")
        bar_m, lbl_m = add_bar(supr, "M", "#ec4899")
        bar_y, lbl_y = add_bar(supr, "Y", "#eab308")
        bar_manut, lbl_manut = add_bar(supr, "MT", "#8b5cf6")

        painel = ctk.CTkFrame(card, fg_color="#181920", corner_radius=6)
        painel.pack(fill="x", padx=10, pady=(0, 10))
        
        lbl_msg = ctk.CTkLabel(painel, text="Aguardando varredura...", font=("Inter", 10), text_color="#94a3b8")
        lbl_msg.pack(padx=10, pady=5)

        return {
            "frame": card, "badge": badge, "lbl_contador": lbl_c_val, "lbl_a4": lbl_a4,
            "lbl_a3": lbl_a3, "lbl_a5": lbl_a5, "lbl_uptime": lbl_up, "lbl_serial": lbl_ser,
            "bar_bk": bar_bk, "lbl_bk": lbl_bk, "bar_c": bar_c, "lbl_c": lbl_c,
            "bar_m": bar_m, "lbl_m": lbl_m, "bar_y": bar_y, "lbl_y": lbl_y,
            "bar_manut": bar_manut, "lbl_manut": lbl_manut, "lbl_painel_msg": lbl_msg,
            "modelo_tipo": "epson"
        }

    def configurar_automacao(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None

        try:
            val = int(self.entry_tempo.get().strip())
            unidade = self.combo_unidade.get()
            if unidade == "Minutos": val *= 60
            elif unidade == "Horas": val *= 3600
            val = max(5, val)
        except ValueError:
            val = 30
            self.entry_tempo.delete(0, "end")
            self.entry_tempo.insert(0, "30")

        ms = val * 1000
        self.timer_job = self.after(ms, self.executar_loop_automacao)

    def executar_loop_automacao(self):
        self.disparar_coleta()
        self.configurar_automacao()

    def disparar_coleta(self):
        threading.Thread(target=lambda: asyncio.run(self.coletar_e_enviar_todas()), daemon=True).start()

    async def coletar_e_enviar_todas(self):
        async with httpx.AsyncClient() as client:
            tasks = [self.processar_impressora(client, imp) for imp in self.impressoras_cadastradas]
            await asyncio.gather(*tasks)
            self.after(0, self.recalcular_kpis_globais)

    async def processar_impressora(self, client, imp):
        ip = imp["ip"]
        id_imp = imp["id"]
        modelo = imp.get("modelo", "")
        
        eh_canon = "canon" in str(imp.get("marca", "")).lower() or "mb5410" in str(modelo).lower()
        eh_epson = not eh_canon
        eh_plotter = "sc-p" in str(modelo).lower() or "surecolor" in str(modelo).lower()

        oids_custom = imp.get("oids", {})
        
        # Mapeamento de OIDs Padrão SNMP
        oids_default = {
            "uptime": "1.3.6.1.2.1.1.3.0",
            "serial": "1.3.6.1.2.1.43.5.1.1.17.1",
            "painel": "1.3.6.1.2.1.43.16.5.1.2.1.1",
            "contador_total": "1.3.6.1.2.1.43.10.2.1.4.1.1"
        }
        
        if eh_canon:
            oids_default.update({
                "toner_atual": "1.3.6.1.2.1.43.11.1.1.9.1.1",
                "toner_full": "1.3.6.1.2.1.43.11.1.1.8.1.1"
            })
        else:
            oids_default.update({
                "contador_a4": "1.3.6.1.4.1.1248.1.2.2.44.1.1.2.1",
                "contador_a3": "1.3.6.1.4.1.1248.1.2.2.44.1.1.2.2",
                "tinta_preta": "1.3.6.1.4.1.1248.1.2.2.44.1.1.3.1",
                "tinta_ciano": "1.3.6.1.4.1.1248.1.2.2.44.1.1.3.2",
                "tinta_magenta": "1.3.6.1.4.1.1248.1.2.2.44.1.1.3.3",
                "tinta_amarela": "1.3.6.1.4.1.1248.1.2.2.44.1.1.3.4",
                "caixa_manutencao": "1.3.6.1.4.1.1248.1.2.2.44.1.1.3.5"
            })

        oids_finais = {**oids_default, **oids_custom}

        # 1. Testar Uptime / Status Online
        uptime_raw = await snmp_safe_get(ip, oids_finais["uptime"])
        is_online = (uptime_raw != "N/A" and uptime_raw is not None)
        uptime = formatar_uptime(uptime_raw)

        if not is_online:
            self.after(0, lambda: self.atualizar_ui_offline(id_imp))
            payload = {
                "ip": ip,
                "serial": imp.get("serial_inicial", f"OFFLINE-{ip}"),
                "modelo": modelo,
                "status": "Offline",
                "mensagem_painel": "Inacessível"
            }
            await self.enviar_payload_django(client, payload)
            return

        # 2. Ler OIDs SNMP
        resultados = {}
        for chave, oid in oids_finais.items():
            decode = (chave in ["serial", "painel"])
            resultados[chave] = await snmp_safe_get(ip, oid, decode=decode)

        # 3. Formatar valores lidos
        serial_detectado = str(resultados.get("serial", "N/A"))
        if serial_detectado in ("N/A", "", "None"):
            serial_detectado = imp.get("serial_inicial", f"NO-SERIAL-{ip}")

        painel = formatar_painel(resultados.get("painel"))
        contador_total_val = resultados.get("contador_total")
        if contador_total_val == "N/A": contador_total_val = None

        # 4. Formatar Suprimentos e Atualizar UI
        if eh_canon:
            toner_atual = resultados.get("toner_atual")
            toner_full = resultados.get("toner_full")
            
            try:
                if str(toner_atual).endswith("%"):
                    pct_toner = float(str(toner_atual).replace("%","").strip())
                elif isinstance(toner_atual, (int, float)) and isinstance(toner_full, (int, float)) and toner_full > 0:
                    pct_toner = round((toner_atual / toner_full) * 100, 1)
                    pct_toner = max(0.0, min(100.0, pct_toner))
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

    async def enviar_payload_django(self, client, payload):
        try:
            url = AppConfig.get_api_url()
            await client.post(url, json=payload, timeout=5.0)
        except Exception as e:
            print(f"[Erro API Django] Falha ao enviar payload para {payload.get('ip')}: {e}")

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
    import sys
    if sys.platform != 'win32':
        return
        
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PrismaMonitor"
        
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}"'
        else:
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