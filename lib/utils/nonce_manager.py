import asyncio
from typing import Optional, Union

from eth_typing import Address, ChecksumAddress
from web3 import AsyncWeb3
from web3.types import ENS


class NonceManager:
    """
    Manages nonces for blockchain transactions with atomic counter and async locking.
    Ensures nonces are not duplicated when multiple transactions are sent concurrently.
    """

    def __init__(self, web3: AsyncWeb3, wallet_address: Union[Address, ChecksumAddress, ENS]):
        self.web3 = web3
        self.wallet_address = wallet_address
        self.current_nonce: Optional[int] = None
        self._lock = asyncio.Lock()

    async def get_next_nonce(self) -> int:
        """
        Get the next available nonce for transactions.
        If the nonce counter isn't initialized, it will fetch the current nonce from the blockchain.
        Uses a lock to prevent multiple parallel initializations.

        Returns:
            int: The next available nonce
        """
        async with self._lock:
            if self.current_nonce is None:
                # Initialize from blockchain if not set
                self.current_nonce = await self.web3.eth.get_transaction_count(self.wallet_address)
            else:
                # Increment existing nonce
                self.current_nonce += 1

            return self.current_nonce

    def reset(self) -> None:
        """Reset the nonce counter, forcing re-initialization from blockchain on next use"""
        self.current_nonce = None
