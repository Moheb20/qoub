from .admin_handlers import setup_admin_handlers
from .user_handlers import setup_user_handlers
from .contact_handlers import setup_contact_handlers
from .deadline_handlers import setup_deadline_handlers
from .group_handlers import setup_group_handlers

__all__ = [
    'setup_admin_handlers',
    'setup_user_handlers', 
    'setup_contact_handlers',
    'setup_deadline_handlers',
    'setup_group_handlers'
]
