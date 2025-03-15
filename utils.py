from config import ADMIN_IDS


async def is_admin(user_id):
    """
    Check if a user is an admin

    Args:
        user_id (int): Telegram user ID

    Returns:
        bool: True if user is admin, False otherwise
    """
    return user_id in ADMIN_IDS