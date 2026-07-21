def user_permissions(request):
    """
    Context processor para disponibilizar permissoes e grupos do usuario em todas as views.
    - Admin: Acesso total (Controle, Inventário, Dashboard, Gerenciamento).
    - Técnico: Acesso a Dashboard e Inventário.
    - Financeiro: Acesso a Controle.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'is_admin': False,
            'is_tecnico': False,
            'is_financeiro': False,
            'user_groups': set(),
        }
    
    groups = set(request.user.groups.values_list('name', flat=True))
    
    is_admin = request.user.is_superuser or 'Admin' in groups
    is_tecnico = 'Técnico' in groups
    is_financeiro = 'Financeiro' in groups

    # Se o usuario nao pertence a nenhum grupo explicitamente, assume Admin para compatibilidade
    if not groups:
        is_admin = True

    return {
        'is_admin': is_admin,
        'is_tecnico': is_tecnico,
        'is_financeiro': is_financeiro,
        'user_groups': groups,
    }
