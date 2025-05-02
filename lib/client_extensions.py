from kuru_sdk.client_order_executor import ClientOrderExecutor

from lib.utils.nonce_manager import NonceManager


def add_nonce_manager_to_client(client: ClientOrderExecutor) -> NonceManager:
    """
    Adds a nonce manager to a ClientOrderExecutor instance if one doesn't exist.
    This allows for atomic nonce management across concurrent transactions.

    Args:
        client: The ClientOrderExecutor instance to add nonce management to

    Returns:
        The NonceManager instance attached to the client
    """
    # Use hasattr to check if nonce_manager already exists on the client instance
    if not hasattr(client, "_nonce_manager"):
        # Attach a nonce manager to the client as a private attribute
        client._nonce_manager = NonceManager(client.web3, client.wallet_address)

    return client._nonce_manager


async def get_next_nonce(client: ClientOrderExecutor) -> int:
    """
    Get the next nonce value for a transaction from a ClientOrderExecutor instance.
    This will initialize the nonce manager if needed.

    Args:
        client: The ClientOrderExecutor instance to get a nonce from

    Returns:
        The next available nonce value
    """
    nonce_manager = add_nonce_manager_to_client(client)
    return await nonce_manager.get_next_nonce()


def reset_nonce(client: ClientOrderExecutor) -> None:
    """
    Reset the nonce counter for a ClientOrderExecutor instance.

    Args:
        client: The ClientOrderExecutor instance to reset the nonce for
    """
    if hasattr(client, "_nonce_manager"):
        client._nonce_manager.reset()
