from app.services.chat2edit_service import Chat2EditService
from app.services.impl.chat2edit_service_impl import Chat2EditServiceImpl


def get_chat2edit_service() -> Chat2EditService:
    """Get standalone chat2edit service (no storage backend needed)."""
    return Chat2EditServiceImpl()
