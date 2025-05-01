from typing import TypedDict

ADDRESSES = {
    'orderbook': '0x05e6f736b5dedd60693fa806ce353156a1b73cf3',
}

class MarketAddresses(TypedDict):
    MON_USDC: str
    DAK_MON: str
    CHOG_MON: str
    YAKI_MON: str
    KB_MON: str
    TEST_CHOG_MON: str

testnet_market_addresses: MarketAddresses = {
    "MON_USDC": "0xd3af145f1aa1a471b5f0f62c52cf8fcdc9ab55d3",
    "DAK_MON": "0x94b72620e65577de5fb2b8a8b93328caf6ca161b",
    "CHOG_MON": "0x277bf4a0aac16f19d7bf592feffc8d2d9a890508",
    "TEST_CHOG_MON": "0x05e6f736b5dedd60693fa806ce353156a1b73cf3",
    "YAKI_MON": "0xd5c1dc181c359f0199c83045a85cd2556b325de0",
    "KB_MON": "0x37676650654c9c2c36fcecfaea6172ee1849f9a4",
}

class KuruContractAddresses(TypedDict):
    margin_account: str
    

testnet_kuru_contract_addresses: KuruContractAddresses = {
    "margin_account": "0x4B186949F31FCA0aD08497Df9169a6bEbF0e26ef",
}
