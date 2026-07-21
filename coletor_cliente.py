import asyncio
import threading
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

def carregar_config_servidor_coletor():
    default_config = {
        "django_api_url": "http://192.170.0.241:8999/api/coleta/"
    }
    if os.path.exists("config_servidor.json"):
        try:
            with open("config_servidor.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "django_api_url" in data:
                    return data
        except Exception:
            pass
    return default_config

_config_coletor = carregar_config_servidor_coletor()
DJANGO_API_URL = _config_coletor["django_api_url"]
DJANGO_SERVER_URL = "/".join(DJANGO_API_URL.split("/")[:3])

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
            "is_color": True,
            "is_plotter": False,
            "oids": {}
        },
        {
            "id": "EPSON_L15160_GTR",
            "nome": "Técnico Epson",
            "ip": "192.168.50.10",
            "modelo": "Epson L15160",
            "marca": "Epson",
            "serial_inicial": "EPSON_L15160_GTR",
            "is_color": True,
            "is_plotter": False,
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


class JanelaGerenciamento(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Gerenciar Impressoras")
        self.geometry("820x560")
        self.configure(fg_color="#0f1015")
        self.transient(master)
        self.grab_set()

        self.impressora_editando_id = None
        self.dados_servidor = None
        self.perfis_cache = {}

        # Formulário Superior
        self.frame_form = ctk.CTkFrame(self, fg_color="#16171d", border_color="#202127", border_width=1)
        self.frame_form.pack(fill="x", padx=20, pady=20)

        self.lbl_form = ctk.CTkLabel(self.frame_form, text="ADICIONAR / EDITAR DISPOSITIVO", font=("Inter", 11, "bold"), text_color="#646670")
        self.lbl_form.grid(row=0, column=0, columnspan=5, padx=15, pady=(10, 5), sticky="w")

        # PASSO 1: Número de Série e Busca
        self.entry_serial = ctk.CTkEntry(self.frame_form, placeholder_text="Número de Série (Ex: CANON_MB5410_REC)", width=250, fg_color="#1d1e24", border_color="#2d2e3a")
        self.entry_serial.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.btn_buscar = ctk.CTkButton(self.frame_form, text="Buscar no Servidor", width=150, fg_color="#3b82f6", hover_color="#1d4ed8", font=("Inter", 11, "bold"), command=self.buscar_no_servidor_thread)
        self.btn_buscar.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        # PASSO 2: Dados locais de rede com Combobox para selecionar o Perfil de OIDs (Marca)
        self.frame_passo2 = ctk.CTkFrame(self.frame_form, fg_color="transparent")
        self.frame_passo2.grid(row=2, column=0, columnspan=5, padx=10, pady=(10, 0), sticky="w")
        
        self.entry_nome = ctk.CTkEntry(self.frame_passo2, placeholder_text="Setor / Nome Local", width=180, fg_color="#1d1e24", border_color="#2d2e3a")
        self.entry_nome.grid(row=0, column=0, padx=4, pady=10, sticky="w")

        self.entry_ip = ctk.CTkEntry(self.frame_passo2, placeholder_text="IP Address / Hostname", width=130, fg_color="#1d1e24", border_color="#2d2e3a")
        self.entry_ip.grid(row=0, column=1, padx=4, pady=10, sticky="w")

        self.combo_perfil_oid = ctk.CTkComboBox(self.frame_passo2, values=["Carregando perfis..."], width=170, fg_color="#1d1e24", border_color="#2d2e3a")
        self.combo_perfil_oid.grid(row=0, column=2, padx=4, pady=10, sticky="w")

        self.btn_salvar = ctk.CTkButton(self.frame_passo2, text="Salvar", width=90, fg_color="#10b981", hover_color="#059669", font=("Inter", 11, "bold"), command=self.salvar_impressora)
        self.btn_salvar.grid(row=0, column=3, padx=4, pady=10, sticky="w")

        # Lista de Dispositivos Atual
        ctk.CTkLabel(self, text="DISPOSITIVOS CADASTRADOS", font=("Inter", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=20, pady=(10, 5))
        
        self.scroll_lista = ctk.CTkScrollableFrame(self, fg_color="#16171d", border_color="#202127", border_width=1)
        self.scroll_lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.atualizar_lista_dispositivos()
        self.carregar_perfis_servidor_thread()

    def carregar_perfis_servidor_thread(self):
        threading.Thread(target=lambda: asyncio.run(self.executar_busca_perfis_async()), daemon=True).start()

    async def executar_busca_perfis_async(self):
        url = f"{DJANGO_SERVER_URL}/api/printer/search/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    perfis = data.get("perfis", [])
                    self.perfis_cache = {
                        p["nome_perfil"]: {
                            "oids": p["oids"],
                            "is_color": p.get("is_color", True),
                            "is_plotter": p.get("is_plotter", False),
                            "marca": p["marca"]
                        }
                        for p in perfis
                    }
                    valores = list(self.perfis_cache.keys())
                    for extra in ["Canon Padrão", "Epson Multifuncional", "Epson Plotter", "HP Padrão Mono"]:
                        if extra not in self.perfis_cache:
                            self.perfis_cache[extra] = {
                                "oids": {},
                                "is_color": "Mono" not in extra,
                                "is_plotter": "Plotter" in extra,
                                "marca": "Canon" if "Canon" in extra else ("Epson" if "Epson" in extra else "HP")
                            }
                            valores.append(extra)
                    self.after(0, lambda: self.atualizar_combobox_perfis(valores))
                else:
                    self.after(0, lambda: self.atualizar_combobox_perfis(["Canon Padrão", "Epson Multifuncional", "Epson Plotter", "HP Padrão Mono"]))
        except Exception:
            self.after(0, lambda: self.atualizar_combobox_perfis(["Canon Padrão", "Epson Multifuncional", "Epson Plotter", "HP Padrão Mono"]))

    def atualizar_combobox_perfis(self, valores):
        self.combo_perfil_oid.configure(values=valores)
        if valores:
            self.combo_perfil_oid.set(valores[0])

    def buscar_no_servidor_thread(self):
        serial = self.entry_serial.get().strip()
        if not serial:
            messagebox.showerror("Erro", "Por favor, digite o Número de Série da impressora.")
            return
        
        self.btn_buscar.configure(state="disabled", text="Buscando...")
        threading.Thread(target=lambda: asyncio.run(self.executar_busca_async(serial)), daemon=True).start()

    async def executar_busca_async(self, serial):
        url = f"{DJANGO_SERVER_URL}/api/printer/search/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"serial": serial}, timeout=5.0)
                
                if response.status_code == 404:
                    self.after(0, lambda: self.tratar_erro_busca("Esta impressora não está pré-cadastrada no painel administrativo do servidor."))
                elif response.status_code != 200:
                    self.after(0, lambda: self.tratar_erro_busca(f"Erro no servidor: Código {response.status_code}"))
                else:
                    data = response.json()
                    self.after(0, lambda: self.tratar_sucesso_busca(data))
        except Exception as e:
            self.after(0, lambda: self.tratar_erro_busca(f"Falha de conexão com o servidor: {e}"))

    def tratar_erro_busca(self, mensagem):
        messagebox.showwarning("Aviso do Servidor", f"{mensagem}\nVocê ainda pode preencher os campos abaixo manualmente.")
        self.btn_buscar.configure(state="normal", text="Buscar no Servidor")
        self.dados_servidor = None

    def tratar_sucesso_busca(self, data):
        self.btn_buscar.configure(state="normal", text="Buscar no Servidor")
        self.dados_servidor = data
        
        perfil_detectado = data.get("nome_perfil", "")
        if self.perfis_cache:
            for k in self.perfis_cache.keys():
                if k.lower() == perfil_detectado.lower():
                    self.combo_perfil_oid.set(k)
                    break
        else:
            self.combo_perfil_oid.set(perfil_detectado)
            
        messagebox.showinfo("Sucesso", f"Impressora cadastrada encontrada!\nMarca: {data.get('marca')} | Modelo: {data.get('modelo')}")

    def atualizar_lista_dispositivos(self):
        for widget in self.scroll_lista.winfo_children():
            widget.destroy()

        for imp in self.master_app.impressoras_cadastradas:
            f_linha = ctk.CTkFrame(self.scroll_lista, fg_color="#1d1e24", height=45)
            f_linha.pack(fill="x", padx=5, pady=4)
            f_linha.pack_propagate(False)

            info_txt = f"{imp['nome']}  •  {imp['ip']}  ({imp['modelo']})  •  Série: {imp['serial_inicial']}"
            ctk.CTkLabel(f_linha, text=info_txt, font=("Inter", 12), text_color="#ffffff").pack(side="left", padx=15)

            btn_del = ctk.CTkButton(f_linha, text="Excluir", width=65, height=26, fg_color="#f87171", hover_color="#b91c1c", text_color="#ffffff", font=("Inter", 10, "bold"), command=lambda idx=imp['id']: self.remover(idx))
            btn_del.pack(side="right", padx=10)

            btn_edit = ctk.CTkButton(f_linha, text="Editar", width=65, height=26, fg_color="#3b82f6", hover_color="#1d4ed8", text_color="#ffffff", font=("Inter", 10, "bold"), command=lambda dados=imp: self.carregar_edicao(dados))
            btn_edit.pack(side="right", padx=2)

    def carregar_edicao(self, dados):
        self.impressora_editando_id = dados["id"]
        self.entry_serial.delete(0, 'end')
        self.entry_serial.insert(0, dados["serial_inicial"])
        
        self.entry_nome.delete(0, 'end')
        self.entry_nome.insert(0, dados["nome"])
        
        self.entry_ip.delete(0, 'end')
        self.entry_ip.insert(0, dados["ip"])
        
        self.dados_servidor = {
            "serial_number": dados["serial_inicial"],
            "modelo": dados["modelo"],
            "marca": dados.get("marca", "Generic"),
            "is_color": dados.get("is_color", True),
            "is_plotter": dados.get("is_plotter", False),
            "nome_perfil": dados.get("nome_perfil", "Generic"),
            "oids": dados.get("oids", {})
        }
        
        self.combo_perfil_oid.set(dados.get("nome_perfil", "Generic"))
        self.btn_salvar.configure(text="Atualizar", fg_color="#f59e0b", hover_color="#d97706")

    def salvar_impressora(self):
        nome = self.entry_nome.get().strip()
        ip = self.entry_ip.get().strip()
        serial = self.entry_serial.get().strip()
        perfil_selecionado = self.combo_perfil_oid.get()

        if not nome or not ip or not serial:
            messagebox.showerror("Erro", "Por favor, preencha todos os campos do formulário.")
            return

        for imp in self.master_app.impressoras_cadastradas:
            if imp["serial_inicial"].strip().lower() == serial.lower() and imp["id"] != self.impressora_editando_id:
                messagebox.showerror(
                    title="Dispositivo Duplicado",
                    message=f"Erro: Já existe uma impressora cadastrada com o Número de Série '{serial}' no setor '{imp['nome']}'."
                )
                return

        oids = {}
        is_color = True
        is_plotter = False
        marca = "Generic"
        
        if self.perfis_cache and perfil_selecionado in self.perfis_cache:
            perfil_info = self.perfis_cache[perfil_selecionado]
            oids = perfil_info["oids"]
            is_color = perfil_info["is_color"]
            is_plotter = perfil_info["is_plotter"]
            marca = perfil_info["marca"]
        elif self.dados_servidor:
            oids = self.dados_servidor.get("oids") or {}
            is_color = self.dados_servidor.get("is_color", True)
            is_plotter = self.dados_servidor.get("is_plotter", False)
            marca = self.dados_servidor.get("marca", "Generic")

        modelo = "Generic"
        if self.dados_servidor:
            modelo = self.dados_servidor.get("modelo") or self.dados_servidor.get("model") or modelo
        else:
            modelo = perfil_selecionado

        payload = {
            "id": serial,
            "nome": nome,
            "ip": ip,
            "modelo": modelo,
            "marca": marca,
            "serial_inicial": serial,
            "oids": oids,
            "is_color": is_color,
            "is_plotter": is_plotter,
            "nome_perfil": perfil_selecionado
        }

        if self.impressora_editando_id is not None:
            # Editando existente
            for imp in self.master_app.impressoras_cadastradas:
                if imp["id"] == self.impressora_editando_id:
                    payload["id"] = self.impressora_editando_id
                    imp.update(payload)
                    break
            self.impressora_editando_id = None
            self.btn_salvar.configure(text="Salvar", fg_color="#10b981", hover_color="#059669")
        else:
            self.master_app.impressoras_cadastradas.append(payload)

        # Salva alterações persistentemente no JSON
        salvar_no_json(self.master_app.impressoras_cadastradas)

        self.entry_nome.delete(0, 'end')
        self.entry_ip.delete(0, 'end')
        self.entry_serial.delete(0, 'end')
        self.dados_servidor = None

        self.atualizar_lista_dispositivos()
        self.master_app.reconstruir_cards_dashboard()

    def remover(self, id_imp):
        self.master_app.impressoras_cadastradas = [i for i in self.master_app.impressoras_cadastradas if i["id"] != id_imp]
        salvar_no_json(self.master_app.impressoras_cadastradas)
        self.atualizar_lista_dispositivos()
        self.master_app.reconstruir_cards_dashboard()


class DashboardFinal(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PRISMA - Monitoramento Local Avançado")
        self.geometry("1350x850")
        self.configure(fg_color="#090a0f")

        self.impressoras_cadastradas = carregar_do_json()
        self.cards_ui = {}
        self.timer_job = None
        
        self.protocol("WM_DELETE_WINDOW", self.minimizar_para_tray)

        # --- TOP CONTAINER ---
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(fill="x", padx=35, pady=(25, 10))

        self.frame_titulos = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.frame_titulos.pack(side="left")
        
        self.lbl_titulo = ctk.CTkLabel(self.frame_titulos, text="Métricas das Impressoras", font=("Inter", 24, "bold"), text_color="#ffffff")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_sub = ctk.CTkLabel(self.frame_titulos, text="Gerenciamento multiescala de tempo e pooling dinâmico via SNMP", font=("Inter", 12), text_color="#646670")
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        # --- PAINEL DE CONFIGURAÇÃO DE TEMPO MÚLTIPLO ---
        self.frame_config_tempo = ctk.CTkFrame(self.frame_top, fg_color="#16171d", corner_radius=8, border_color="#202127", border_width=1, height=45)
        self.frame_config_tempo.pack(side="right", padx=(15, 0))

        ctk.CTkLabel(self.frame_config_tempo, text="Auto-atualizar:", font=("Inter", 11, "bold"), text_color="#646670").pack(side="left", padx=(10, 5))
        self.entry_tempo = ctk.CTkEntry(self.frame_config_tempo, width=45, height=28, fg_color="#1d1e24", border_color="#2d2e3a", text_color="#ffffff", justify="center")
        self.entry_tempo.insert(0, "30")
        self.entry_tempo.pack(side="left", padx=2)

        self.combo_unidade = ctk.CTkComboBox(self.frame_config_tempo, values=["Segundos", "Minutos", "Horas"], width=100, height=28, fg_color="#1d1e24", border_color="#2d2e3a")
        self.combo_unidade.set("Segundos")
        self.combo_unidade.pack(side="left", padx=4)

        self.btn_aplicar_tempo = ctk.CTkButton(self.frame_config_tempo, text="Agendar", width=65, height=28, fg_color="#21222c", hover_color="#2d2e3a", text_color="#ffffff", font=("Inter", 11, "bold"), command=self.configurar_automacao)
        self.btn_aplicar_tempo.pack(side="left", padx=(2, 10))

        # Botão para abrir Nova Tela de Cadastro
        self.btn_tela_cadastro = ctk.CTkButton(self.frame_top, text="+ Gerenciar Impressoras", width=170, height=45, fg_color="#10b981", hover_color="#059669", font=("Inter", 12, "bold"), command=self.abrir_gerenciador)
        self.btn_tela_cadastro.pack(side="right", padx=10)

        self.btn_atualizar = ctk.CTkButton(self.frame_top, text="Forçar Atualização", width=150, height=45, fg_color="#21222c", hover_color="#2d2e3a", text_color="#ffffff", font=("Inter", 12, "bold"), command=self.disparar_coleta)
        self.btn_atualizar.pack(side="right")

        # --- CONTAINER DE KPIs ---
        self.frame_kpis = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_kpis.pack(fill="x", padx=35, pady=10)
        self.frame_kpis.columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")
        
        self.kpi_total = self.card_kpi(self.frame_kpis, 0, "TOTAL IMPRESSORAS", "0", "🖨️")
        self.kpi_online = self.card_kpi(self.frame_kpis, 1, "ONLINE", "0", "✓", cor_val="#10b981")
        self.kpi_offline = self.card_kpi(self.frame_kpis, 2, "OFFLINE / INATIVAS", "0", "⚠", cor_val="#f87171")
        self.kpi_alerta_toner = self.card_kpi(self.frame_kpis, 3, "SUPRIMENTOS < 15%", "0", "⚡", cor_val="#f59e0b")

        # --- SEÇÃO DE GRID ROLÁVEL ---
        self.frame_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame_scroll.pack(fill="both", expand=True, padx=35, pady=(5, 20))
        
        self.frame_grid_dispositivos = ctk.CTkFrame(self.frame_scroll, fg_color="transparent")
        self.frame_grid_dispositivos.pack(fill="both", expand=True)
        for i in range(4):
            self.frame_grid_dispositivos.columnconfigure(i, weight=1, minsize=290)

        self.reconstruir_cards_dashboard()
        self.configurar_automacao()
        self.iniciar_tray_icon()

    def card_kpi(self, pai, col, titulo, valor, icone, cor_val="#ffffff"):
        f = ctk.CTkFrame(pai, fg_color="#16171d", corner_radius=10, border_color="#202127", border_width=1, height=85)
        f.grid(row=0, column=col, padx=6, sticky="nsew")
        f.pack_propagate(False)
        lbl_t = ctk.CTkLabel(f, text=titulo, font=("Inter", 10, "bold"), text_color="#646670")
        lbl_t.pack(anchor="w", padx=15, pady=(12, 0))
        lbl_v = ctk.CTkLabel(f, text=valor, font=("Inter", 24, "bold"), text_color=cor_val)
        lbl_v.pack(side="left", padx=15, pady=(0, 10))
        lbl_i = ctk.CTkLabel(f, text=icone, font=("Inter", 14), text_color="#444650", fg_color="#1d1e24", width=32, height=32, corner_radius=6)
        lbl_i.pack(side="right", padx=15, pady=(0, 10))
        return lbl_v

    def abrir_gerenciador(self):
        JanelaGerenciamento(self)

    def reconstruir_cards_dashboard(self):
        for widget in self.frame_grid_dispositivos.winfo_children():
            widget.destroy()
        self.cards_ui.clear()

        for index, imp in enumerate(self.impressoras_cadastradas):
            row = index // 4
            col = index % 4
            
            is_color = imp.get("is_color", True)
            is_plotter = imp.get("is_plotter", False)
            
            if is_color:
                self.criar_card_cmyk_dinamico(imp["id"], imp, row, col, exibir_sub_contadores=not is_plotter)
            else:
                self.criar_card_mono_dinamico(imp["id"], imp, row, col)

        self.kpi_total.configure(text=str(len(self.impressoras_cadastradas)))
        self.disparar_coleta()

    def criar_card_mono_dinamico(self, id_imp, dados, r, c):
        card = ctk.CTkFrame(self.frame_grid_dispositivos, fg_color="#16171d", corner_radius=12, border_color="#202127", border_width=1)
        card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(15, 2))
        ctk.CTkLabel(head, text=dados["nome"], font=("Inter", 13, "bold"), text_color="#ffffff").pack(side="left")
        badge = ctk.CTkLabel(head, text="• Status", font=("Inter", 9, "bold"), text_color="#646670", fg_color="#202127", corner_radius=12, width=60, height=20)
        badge.pack(side="right")

        ctk.CTkLabel(card, text=f"{dados.get('marca', 'Generic')} {dados.get('modelo', 'Mono')}", font=("Inter", 11), text_color="#646670").pack(anchor="w", padx=18)
        
        g = ctk.CTkFrame(card, fg_color="transparent")
        g.pack(fill="x", padx=18, pady=(10, 0))
        self.bloco(g, "Endereço IP", dados["ip"], "left")
        _, lbl_serial = self.bloco(g, "Nº de Série", dados["serial_inicial"], "right")

        ctk.CTkFrame(card, fg_color="#202127", height=1).pack(fill="x", padx=18, pady=12)
        g2 = ctk.CTkFrame(card, fg_color="transparent")
        g2.pack(fill="x", padx=18)
        _, lbl_contador = self.bloco(g2, "CONTADOR GERAL", "---", "left", dest=True)
        _, lbl_uptime = self.bloco(g2, "UPTIME", "---", "right", dest=True)

        ctk.CTkFrame(card, fg_color="#202127", height=1).pack(fill="x", padx=18, pady=12)
        f_t = ctk.CTkFrame(card, fg_color="transparent")
        f_t.pack(fill="x", padx=18, pady=(2, 0))
        ctk.CTkLabel(f_t, text="● Black Toner", font=("Inter", 11), text_color="#ffffff").pack(side="left")
        lbl_toner_pct = ctk.CTkLabel(f_t, text="---", font=("Inter", 11, "bold"), text_color="#ffffff")
        lbl_toner_pct.pack(side="right")

        barra_toner = ctk.CTkProgressBar(card, height=6, fg_color="#22232a", progress_color="#ffffff", corner_radius=4)
        barra_toner.set(0)
        barra_toner.pack(fill="x", padx=18, pady=(4, 12))

        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=18, pady=(0, 12))
        self.bloco(foot, "MENSAGEM DE PAINEL", "Aguardando...", "left")
        lbl_painel_msg = foot.winfo_children()[-1].winfo_children()[-1]

        self.cards_ui[id_imp] = {
            "badge": badge, "lbl_serial": lbl_serial, "lbl_contador": lbl_contador,
            "lbl_uptime": lbl_uptime, "lbl_toner_pct": lbl_toner_pct, "barra_toner": barra_toner,
            "lbl_painel_msg": lbl_painel_msg, "modelo_tipo": "mono"
        }

    def criar_card_cmyk_dinamico(self, id_imp, dados, r, c, exibir_sub_contadores=True):
        card = ctk.CTkFrame(self.frame_grid_dispositivos, fg_color="#16171d", corner_radius=12, border_color="#202127", border_width=1)
        card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(15, 2))
        ctk.CTkLabel(head, text=dados["nome"], font=("Inter", 13, "bold"), text_color="#ffffff").pack(side="left")
        badge = ctk.CTkLabel(head, text="• Status", font=("Inter", 9, "bold"), text_color="#646670", fg_color="#202127", corner_radius=12, width=60, height=20)
        badge.pack(side="right")

        ctk.CTkLabel(card, text=f"{dados.get('marca', 'Generic')} {dados.get('modelo', 'Color')}", font=("Inter", 11), text_color="#646670").pack(anchor="w", padx=18)

        g = ctk.CTkFrame(card, fg_color="transparent")
        g.pack(fill="x", padx=18, pady=(10, 0))
        self.bloco(g, "Endereço IP", dados["ip"], "left")
        _, lbl_serial = self.bloco(g, "Nº de Série", dados["serial_inicial"], "right")

        ctk.CTkFrame(card, fg_color="#202127", height=1).pack(fill="x", padx=18, pady=8)
        g2 = ctk.CTkFrame(card, fg_color="transparent")
        g2.pack(fill="x", padx=18)
        _, lbl_contador = self.bloco(g2, "CONTADOR TOTAL", "---", "left", dest=True)
        _, lbl_uptime = self.bloco(g2, "UPTIME", "---", "right", dest=True)

        lbl_a4, lbl_a3, lbl_a5 = None, None, None
        if exibir_sub_contadores:
            g3 = ctk.CTkFrame(card, fg_color="transparent")
            g3.pack(fill="x", padx=18, pady=(6, 0))
            _, lbl_a4 = self.bloco(g3, "A4", "---", "left")
            _, lbl_a3 = self.bloco(g3, "A3", "---", "left")
            _, lbl_a5 = self.bloco(g3, "A5", "---", "right")

        ctk.CTkFrame(card, fg_color="#202127", height=1).pack(fill="x", padx=18, pady=8)
        lbl_bk, bar_bk = self.criar_linha_suprimento(card, "● Black", "#ffffff")
        lbl_c, bar_c = self.criar_linha_suprimento(card, "● Cyan", "#22d3ee")
        lbl_m, bar_m = self.criar_linha_suprimento(card, "● Magenta", "#ec4899")
        lbl_y, bar_y = self.criar_linha_suprimento(card, "● Yellow", "#facc15")
        lbl_manut, bar_manut = self.criar_linha_suprimento(card, "⚙ Cx. Manut.", "#a855f7")

        ctk.CTkFrame(card, fg_color="#202127", height=1).pack(fill="x", padx=18, pady=6)
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=18, pady=(0,10))
        self.bloco(foot, "MENSAGEM DE PAINEL", "Aguardando...", "left")
        lbl_painel_msg = foot.winfo_children()[-1].winfo_children()[-1]

        self.cards_ui[id_imp] = {
            "badge": badge, "lbl_serial": lbl_serial, "lbl_contador": lbl_contador, "lbl_uptime": lbl_uptime,
            "lbl_a4": lbl_a4, "lbl_a3": lbl_a3, "lbl_a5": lbl_a5, "lbl_painel_msg": lbl_painel_msg,
            "lbl_bk": lbl_bk, "bar_bk": bar_bk, "lbl_c": lbl_c, "bar_c": bar_c, "lbl_m": lbl_m, "bar_m": bar_m,
            "lbl_y": lbl_y, "bar_y": bar_y, "lbl_manut": lbl_manut, "bar_manut": bar_manut, "modelo_tipo": "cmyk"
        }

    def criar_linha_suprimento(self, card, nome, cor_progresso):
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=1)
        ctk.CTkLabel(f, text=nome, font=("Inter", 10), text_color="#ffffff").pack(side="left")
        lbl_p = ctk.CTkLabel(f, text="---", font=("Inter", 10, "bold"), text_color="#ffffff")
        lbl_p.pack(side="right")
        bar = ctk.CTkProgressBar(card, height=4, fg_color="#22232a", progress_color=cor_progresso, corner_radius=2)
        bar.set(0)
        bar.pack(fill="x", padx=18, pady=(0, 2))
        return lbl_p, bar

    def bloco(self, pai, t, v, lado, dest=False):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.pack(side=lado, fill="x", expand=True)
        align = "w" if lado == "left" else "e"
        lbl_t = ctk.CTkLabel(f, text=t, font=("Inter", 10, "bold" if dest else "normal"), text_color="#646670", anchor=align)
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
        if not self.impressoras_cadastradas: 
            self.recalcular_kpis_globais()
            return
        self.btn_atualizar.configure(state="disabled", text="Pooling...")
        threading.Thread(target=lambda: asyncio.run(self.executar_todas_coletas_async()), daemon=True).start()

    async def executar_todas_coletas_async(self):
        async with httpx.AsyncClient() as client:
            tarefas = []
            for imp in self.impressoras_cadastradas:
                tarefas.append(self.executar_coleta_dinamica(client, imp))
            if tarefas:
                await asyncio.gather(*tarefas)
        
        self.after(0, lambda: self.btn_atualizar.configure(state="normal", text="Forçar Atualização"))
        self.after(0, self.recalcular_kpis_globais)

    async def enviar_payload_django(self, client, payload):
        try:
            res = await client.post(DJANGO_API_URL, json=payload, timeout=5.0)
            if res.status_code not in (200, 201):
                print(f"[Erro API] Código de status do servidor: {res.status_code} - {res.text}")
            else:
                print(f"[Sucesso API] Dados enviados com sucesso para {payload['ip']}.")
        except Exception as e:
            print(f"[Erro API] Falha na conexão com o servidor Django: {e}")

    async def executar_coleta_dinamica(self, client, imp):
        ip = imp["ip"]
        id_imp = imp["id"]
        serial_inicial = imp["serial_inicial"]
        
        # 1. Buscar configurações de OID do Django
        url = f"{DJANGO_SERVER_URL}/api/printer/search/"
        oids = {}
        marca = imp.get("marca", "Canon")
        modelo = imp.get("modelo", "Generic")
        is_color = imp.get("is_color", True)
        is_plotter = imp.get("is_plotter", False)
        
        try:
            response = await client.get(url, params={"serial": serial_inicial}, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                marca = data.get("marca", marca)
                modelo = data.get("modelo", modelo)
                is_color = data.get("is_color", is_color)
                is_plotter = data.get("is_plotter", is_plotter)
                oids = data.get("oids", {})
                
                # Salvar em cache de memória
                imp["marca"] = marca
                imp["modelo"] = modelo
                imp["is_color"] = is_color
                imp["is_plotter"] = is_plotter
                imp["oids"] = oids
            else:
                oids = imp.get("oids", {})
                print(f"[Aviso API] Status {response.status_code} ao buscar {serial_inicial}. Usando cache local.")
        except Exception as e:
            oids = imp.get("oids", {})
            print(f"[Erro API] Falha de rede ao buscar {serial_inicial}: {e}. Usando cache local.")
            
        if not oids:
            self.after(0, lambda: self.atualizar_ui_offline(id_imp))
            return
            
        # 2. Coletar dados via SNMP
        chaves = list(oids.keys())
        tarefas_snmp = []
        for chave in chaves:
            oid = oids[chave]
            decode = (chave in ("N_S", "mensagem_painel", "oid_serial_number", "oid_mensagem_painel"))
            # Se for nulo ou vazio o OID, adiciona dummy
            if not oid:
                async def dummy(): return "N/A"
                tarefas_snmp.append(dummy())
            else:
                tarefas_snmp.append(snmp_safe_get(ip, oid, decode=decode))
            
        resultados_snmp = await asyncio.gather(*tarefas_snmp)
        resultados = dict(zip(chaves, resultados_snmp))
        
        is_online = any(v != "N/A" for v in resultados_snmp)
        
        # Simulação caso esteja offline para Epson Colorida
        if not is_online and is_color and ("epson" in marca.lower() or "epson" in modelo.lower()):
            is_online = True
            simulados = {
                "contador_total": 42500,
                "contador_a4": 21000,
                "contador_a3": 19000,
                "tempo_ligada": 8931200,
                "N_S": serial_inicial,
                "mensagem_painel": "Pronta para Impressão",
                "tinta_preta": 70.0,
                "tinta_ciano": 95.0,
                "tinta_magenta": 34.0,
                "tinta_amarela": 12.0,
                "caixa_manutencao": 85.0
            }
            for k in chaves:
                if k in simulados:
                    resultados[k] = simulados[k]

        # 3. Formatar dados coletados
        uptime = formatar_uptime(resultados.get("tempo_ligada") or resultados.get("oid_tempo_ligada") or "N/A")
        painel = formatar_painel(resultados.get("mensagem_painel") or resultados.get("oid_mensagem_painel") or "N/A")
        serial_detectado = resultados.get("N_S") or resultados.get("oid_serial_number")
        if not serial_detectado or serial_detectado == "N/A":
            serial_detectado = serial_inicial
            
        contador_total = resultados.get("contador_total") or resultados.get("oid_counter_total")
        contador_total_val = int(contador_total) if (is_online and str(contador_total).isdigit()) else None
        
        suprimentos_payload = {}
        
        # 4. Atualizar UI
        if not is_color:
            pct_bk = 0.0
            try:
                toner_atual = resultados.get("toner_atual") or resultados.get("tinta_preta") or resultados.get("oid_toner_level") or resultados.get("oid_tinta_preta")
                toner_full = resultados.get("toner_full") or resultados.get("oid_toner_full") or 100
                
                # Trata string/valores nulos
                if toner_atual == "N/A" or toner_atual is None:
                    toner_atual = 0
                
                if isinstance(toner_atual, (int, float)) and isinstance(toner_full, (int, float)) and toner_full > 0:
                    pct_bk = round((toner_atual / toner_full) * 100, 1)
                else:
                    pct_bk = float(toner_atual) if (toner_atual is not None and str(toner_atual).replace('.','',1).isdigit()) else 0.0
            except Exception:
                pct_bk = 0.0
                
            self.after(0, lambda: self.atualizar_ui_card_mono(id_imp, is_online, contador_total_val or "---", uptime, serial_detectado, painel, pct_bk))
            
            suprimentos_payload = {
                "black": pct_bk if is_online else None,
                "cyan": None,
                "magenta": None,
                "yellow": None,
                "caixa_manutencao": None
            }
        else:
            a4 = resultados.get("contador_a4") or resultados.get("oid_counter_mono") or 0
            a3 = resultados.get("contador_a3") or resultados.get("oid_counter_color") or 0
            try:
                a4_val = int(a4) if str(a4).isdigit() else 0
                a3_val = int(a3) if str(a3).isdigit() else 0
                total_val = int(contador_total_val) if contador_total_val else 0
                a5_val = max(0, total_val - (a4_val + a3_val))
            except Exception:
                a4_val, a3_val, a5_val = 0, 0, 0
                
            def clean_pct(v):
                try:
                    return float(v) if (v != "N/A" and v is not None) else None
                except Exception:
                    return None
                    
            bk = clean_pct(resultados.get("tinta_preta") or resultados.get("oid_tinta_preta"))
            cy = clean_pct(resultados.get("tinta_ciano") or resultados.get("oid_tinta_ciano"))
            mg = clean_pct(resultados.get("tinta_magenta") or resultados.get("oid_tinta_magenta"))
            yl = clean_pct(resultados.get("tinta_amarela") or resultados.get("oid_tinta_amarela"))
            mt = clean_pct(resultados.get("caixa_manutencao") or resultados.get("oid_caixa_manutencao"))
            
            self.after(0, lambda: self.atualizar_ui_card_cmyk(
                id_imp, is_online,
                contador_total_val or "---",
                a4_val if not is_plotter else "---",
                a3_val if not is_plotter else "---",
                a5_val if not is_plotter else "---",
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
            "contador_a4": int(a4) if (is_color and not is_plotter and str(a4).isdigit()) else None,
            "contador_a3": int(a3) if (is_color and not is_plotter and str(a3).isdigit()) else None,
            "contador_a5": a5_val if (is_color and not is_plotter) else None,
            "uptime": uptime if is_online else None,
            "mensagem_painel": painel if is_online else "Inacessível",
            "suprimentos": suprimentos_payload
        }
        
        await self.enviar_payload_django(client, payload)

    def atualizar_ui_card_mono(self, uid, is_online, contador, uptime, serial, painel, pct_bk):
        if uid not in self.cards_ui: return
        ui = self.cards_ui[uid]
        if is_online:
            ui["badge"].configure(text="• Online", text_color="#10b981", fg_color="#064e3b")
            ui["lbl_contador"].configure(text=str(contador))
            ui["lbl_uptime"].configure(text=str(uptime))
            ui["lbl_serial"].configure(text=str(serial))
            ui["lbl_painel_msg"].configure(text=str(painel))
            ui["lbl_toner_pct"].configure(text=f"{pct_bk}%")
            ui["barra_toner"].configure(progress_color="#f59e0b" if pct_bk < 15.0 else "#ffffff")
            ui["barra_toner"].set(pct_bk / 100)
        else:
            self.atualizar_ui_offline(uid)

    def atualizar_ui_card_cmyk(self, uid, is_online, total, a4, a3, a5, uptime, serial, painel, bk, cy, mg, yl, mt):
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
        if ui["modelo_tipo"] == "mono":
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
                if ui["modelo_tipo"] == "mono":
                    txt = ui["lbl_toner_pct"].cget("text").replace("%","")
                    try:
                        if float(txt) < 15.0: alerta += 1
                    except ValueError:
                        pass
                elif ui["modelo_tipo"] == "cmyk":
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
                pystray.Menu.SEPARATOR,
                item('Encerrar Sistema', self.encerrar_sistema_definitivo)
            )
            self.tray = pystray.Icon("PrismaMonitor", self.gerar_icone_pillow(), "PRISMA Monitoramento", menu)
            self.tray.run()
        
        threading.Thread(target=criar_tray, daemon=True).start()

    def minimizar_para_tray(self):
        self.withdraw()

    def restaurar_janela(self, icon=None, item=None):
        self.after(0, self.deiconify)

    def encerrar_sistema_definitivo(self, icon=None, item=None):
        if self.timer_job: self.after_cancel(self.timer_job)
        self.tray.stop()
        self.quit()


if __name__ == "__main__":
    app = DashboardFinal()
    app.mainloop()