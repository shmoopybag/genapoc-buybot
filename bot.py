import os
import time
import threading
import requests
from flask import Flask
from web3 import Web3

app = Flask(__name__)

@app.route("/")
def home():
    return "GENAPOC Buy Bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
RPC_URL = os.environ["WORLDCHAIN_RPC_URL"]
TOKEN_ADDRESS = Web3.to_checksum_address(os.environ["TOKEN_ADDRESS"])

POOL_ADDRESS = Web3.to_checksum_address(
    "0x0b9a52CEB98b56cf00e5751CB5e2514d060727F0"
)

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 20}))

POOL_ABI = [
    {"inputs": [], "name": "token0", "outputs": [{"type": "address", "name": ""}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token1", "outputs": [{"type": "address", "name": ""}], "stateMutability": "view", "type": "function"}
]

TOKEN_ABI = [
    {"inputs": [], "name": "symbol", "outputs": [{"type": "string", "name": ""}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8", "name": ""}], "stateMutability": "view", "type": "function"}
]

SWAP_TOPIC = Web3.keccak(
    text="Swap(address,address,int256,int256,uint160,uint128,int24)"
).hex()


def send_telegram(message):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True},
        timeout=20
    )
    response.raise_for_status()


def monitor_buys():
    if not w3.is_connected():
        raise RuntimeError("Cannot connect to World Chain RPC")

    if w3.eth.chain_id != 480:
        raise RuntimeError("RPC is not connected to World Chain")

    pool = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
    token0 = Web3.to_checksum_address(pool.functions.token0().call())
    token1 = Web3.to_checksum_address(pool.functions.token1().call())

    if TOKEN_ADDRESS not in (token0, token1):
        raise RuntimeError("Token address does not match the configured pool")

    token = w3.eth.contract(address=TOKEN_ADDRESS, abi=TOKEN_ABI)
    symbol = token.functions.symbol().call()
    decimals = token.functions.decimals().call()
    token_is_token0 = TOKEN_ADDRESS == token0

    send_telegram(
        f"GENAPOC BUY BOT IS ONLINE\n\n"
        f"Token: {symbol}\nNetwork: World Chain\n"
        f"Pool: {POOL_ADDRESS}"
    )

    last_block = w3.eth.block_number

    while True:
        try:
            latest = w3.eth.block_number

            if latest > last_block:
                logs = w3.eth.get_logs({
                    "address": POOL_ADDRESS,
                    "fromBlock": last_block + 1,
                    "toBlock": latest,
                    "topics": [SWAP_TOPIC]
                })

                for log in logs:
                    data = bytes(log["data"])
                    amount0 = int.from_bytes(data[0:32], "big", signed=True)
                    amount1 = int.from_bytes(data[32:64], "big", signed=True)

                    token_amount = -(amount0 if token_is_token0 else amount1)

                    if token_amount <= 0:
                        continue

                   
                   
