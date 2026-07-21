from django import forms
from django.contrib.auth.models import User, Group
from core.models import Cliente, Impressora, Brand, PrinterOID

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'cnpj', 'status', 'telefone', 'email', 'endereco', 'contato']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'cnpj': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'placeholder': '00.000.000/0000-00'}),
            'status': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'telefone': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'email': forms.EmailInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'endereco': forms.Textarea(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'rows': 2}),
            'contato': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
        }

class ImpressoraForm(forms.ModelForm):
    class Meta:
        model = Impressora
        fields = ['serial_number', 'ip_address', 'name', 'brand', 'oid_profile']
        widgets = {
            'serial_number': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm font-mono', 'placeholder': 'Número de Série Físico'}),
            'ip_address': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm font-mono', 'placeholder': 'Ex: 192.168.1.100'}),
            'name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'placeholder': 'Nome da Impressora'}),
            'brand': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_profile': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['serial_number'].widget.attrs['readonly'] = True
            self.fields['serial_number'].widget.attrs['class'] += ' bg-gray-100 dark:bg-zinc-900/80 cursor-not-allowed opacity-80'
            self.fields['serial_number'].help_text = "O número de série é o identificador único da impressora e não pode ser alterado."

            # O campo de IP só deve estar disponível para edição se a impressora estiver locada em um cliente
            esta_alocada = (
                getattr(self.instance, 'cliente_id', None) is not None or 
                getattr(self.instance, 'cliente', None) is not None or 
                str(self.instance.status).upper() in ['CLIENTE', 'ALOCADA', 'LOCADA']
            )
            if not esta_alocada:
                if 'ip_address' in self.fields:
                    del self.fields['ip_address']
            else:
                if 'ip_address' in self.fields:
                    self.fields['ip_address'].help_text = "Endereço IP do equipamento na rede do cliente."
        else:
            # No cadastro inicial, o IP não é informado (será informado ao locar a impressora no cliente)
            if 'ip_address' in self.fields:
                del self.fields['ip_address']

class PerfilOidMarcaForm(forms.ModelForm):
    class Meta:
        model = PrinterOID
        fields = [
            'brand', 'brands', 'name', 'is_color', 'is_plotter', 'multiple_sizes', 'printer_oid', 'oid_serial_number', 'oid_tempo_ligada', 'oid_mensagem_painel', 
            'oid_counter_total', 'oid_counter_mono', 'oid_counter_color', 
            'oid_toner_level', 'oid_toner_full', 'oid_tinta_preta', 
            'oid_tinta_ciano', 'oid_tinta_magenta', 'oid_tinta_amarela', 'oid_caixa_manutencao'
        ]
        widgets = {
            'brand': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'brands': forms.CheckboxSelectMultiple(attrs={'class': 'rounded text-brand-600 focus:ring-brand-500 h-4 w-4 border-gray-300 dark:border-zinc-700 bg-white dark:bg-zinc-950'}),
            'name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'is_color': forms.CheckboxInput(attrs={'class': 'rounded text-brand-600 focus:ring-brand-500 h-4 w-4 border-gray-300 dark:border-zinc-700 bg-white dark:bg-zinc-950'}),
            'is_plotter': forms.CheckboxInput(attrs={'class': 'rounded text-brand-600 focus:ring-brand-500 h-4 w-4 border-gray-300 dark:border-zinc-700 bg-white dark:bg-zinc-950'}),
            'multiple_sizes': forms.CheckboxInput(attrs={'class': 'rounded text-brand-600 focus:ring-brand-500 h-4 w-4 border-gray-300 dark:border-zinc-700 bg-white dark:bg-zinc-950'}),
            'printer_oid': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'placeholder': '1.3.6.1.2.1.1.2.0'}),
            'oid_serial_number': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_tempo_ligada': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_mensagem_painel': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_counter_total': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_counter_mono': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_counter_color': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_toner_level': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_toner_full': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_tinta_preta': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_tinta_ciano': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_tinta_magenta': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_tinta_amarela': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
            'oid_caixa_manutencao': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
        }

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'placeholder': 'Nome da Marca (ex: Canon, Epson)'})
        }

class PrinterOIDForm(forms.ModelForm):
    class Meta:
        model = PrinterOID
        fields = [
            'brand', 'brands', 'name', 'is_color', 'is_plotter', 'multiple_sizes', 'printer_oid', 'oid_serial_number', 'oid_tempo_ligada', 'oid_mensagem_painel', 
            'oid_counter_total', 'oid_counter_mono', 'oid_counter_color', 
            'oid_toner_level', 'oid_toner_full', 'oid_tinta_preta', 
            'oid_tinta_ciano', 'oid_tinta_magenta', 'oid_tinta_amarela', 'oid_caixa_manutencao'
        ]
        widgets = {
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'brands': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Perfil / Grupo'}),
            'is_color': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_plotter': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'multiple_sizes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'printer_oid': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.1.2.0'}),
            'oid_serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.43.5.1.1.17.1'}),
            'oid_tempo_ligada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.1.3.0'}),
            'oid_mensagem_painel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.43.16.5.1.2.1.1'}),
            'oid_counter_total': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.43.10.2.1.4.1.1'}),
            'oid_counter_mono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.2'}),
            'oid_counter_color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.1'}),
            'oid_toner_level': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.43.11.1.1.9.1.1'}),
            'oid_toner_full': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.2.1.43.11.1.1.8.1.1'}),
            'oid_tinta_preta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.1'}),
            'oid_tinta_ciano': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.2'}),
            'oid_tinta_magenta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.3'}),
            'oid_tinta_amarela': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.4'}),
            'oid_caixa_manutencao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.5'}),
        }

class PrinterStockForm(forms.ModelForm):
    class Meta:
        model = Impressora
        fields = ['serial_number', 'brand', 'contador_inicial']
        widgets = {
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CANON_MB5410_REC'}),
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'contador_inicial': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

class UserRegistrationForm(forms.Form):
    nome = forms.CharField(
        max_length=150, 
        label="Nome Completo",
        widget=forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'})
    )
    username = forms.CharField(
        max_length=150, 
        label="Usuário / Login",
        widget=forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'}),
        label="Senha"
    )
    perfil = forms.ChoiceField(
        choices=[('Admin', 'Administrador'), ('Técnico', 'Técnico')],
        label="Tipo / Perfil",
        widget=forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'})
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nome de usuário já está em uso.")
        return username

    def save(self):
        nome = self.cleaned_data.get('nome')
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        perfil = self.cleaned_data.get('perfil')

        names = nome.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        group, _ = Group.objects.get_or_create(name=perfil)
        user.groups.add(group)

        if perfil == 'Admin':
            user.is_staff = True
            user.save()

        return user

class UserEditForm(forms.Form):
    nome = forms.CharField(
        max_length=150, 
        label="Nome Completo",
        widget=forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'})
    )
    perfil = forms.ChoiceField(
        choices=[('Admin', 'Administrador'), ('Técnico', 'Técnico')],
        label="Tipo / Perfil",
        widget=forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm'})
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-950 text-gray-900 dark:text-white focus:outline-none focus:ring-brand-500 focus:border-brand-500 text-sm', 'placeholder': 'Deixe em branco para manter'}),
        label="Nova Senha (Opcional)"
    )

    def __init__(self, *args, **kwargs):
        self.user_instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        if self.user_instance:
            self.fields['nome'].initial = f"{self.user_instance.first_name} {self.user_instance.last_name}".strip()
            groups = self.user_instance.groups.all()
            if groups.exists():
                self.fields['perfil'].initial = groups[0].name

    def save(self):
        nome = self.cleaned_data.get('nome')
        perfil = self.cleaned_data.get('perfil')
        password = self.cleaned_data.get('password')

        names = nome.split(' ', 1)
        self.user_instance.first_name = names[0]
        self.user_instance.last_name = names[1] if len(names) > 1 else ''

        if password:
            self.user_instance.set_password(password)

        self.user_instance.groups.clear()
        group, _ = Group.objects.get_or_create(name=perfil)
        self.user_instance.groups.add(group)

        if perfil == 'Admin':
            self.user_instance.is_staff = True
        else:
            self.user_instance.is_staff = False

        self.user_instance.save()
        return self.user_instance
