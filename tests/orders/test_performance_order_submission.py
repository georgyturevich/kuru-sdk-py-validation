import math

import asyncio
import threading
import time
import statistics
import random
from typing import Dict, List, Any

import pytest
import structlog
from eth_typing import HexStr
from eth_utils import to_wei
from kuru_sdk import ClientOrderExecutor, OrderRequest, TxOptions
from kuru_sdk_fork import MarginAccount as MarginAccountFork, ClientOrderExecutor as ClientOrderExecutorFork
from web3 import AsyncWeb3, AsyncHTTPProvider, Web3, HTTPProvider

from lib import constants
from lib.client_extensions import get_next_nonce
from lib.utils.nonce_manager import NonceManager
from lib.utils.price_change import price_suffix_change
from tests.settings import Settings

# Set up logger
log = structlog.get_logger(__name__)

# Global counter for generating unique IDs
counter = 0
lock = threading.Lock()

def increment_counter_with_lock():
    """Thread-safe counter increment"""
    global counter
    with lock:
        counter += 1
        return counter



@pytest.mark.asyncio
async def test_performance_order_submission(settings: Settings):
    """Test performance of order submission using different simulated SDK implementations"""

    web3_orig = Web3(HTTPProvider(
        endpoint_uri=settings.full_rpc_url(),
        # cacheable_requests={"eth_chainId"},
        # cache_allowed_requests=True
    ))
    web3_fork = AsyncWeb3(AsyncHTTPProvider(
        endpoint_uri=settings.full_rpc_url(),
        # cacheable_requests={"eth_chainId"},
        # cache_allowed_requests=True
    ))



    client_orig = ClientOrderExecutor(
        web3=web3_orig,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )
    client_orig_thread = ClientOrderExecutor(
        web3=web3_orig,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )

    client_fork = ClientOrderExecutorFork(
        web3=web3_fork,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )
    client_fork.orderbook.market_params = await client_fork.orderbook.fetch_market_params()


    nonce_manager = NonceManager(web3_fork, client_fork.wallet_address)
    price = "0.00000201"
    size = "10000"

    num_orders = 10  # Total number of orders

    max_price = price_suffix_change(price, num_orders)
    await add_margin_balance(web3_fork, max_price, size, num_orders * 3, settings.private_key)


    log.info(f"Running performance test with {num_orders} executions for each implementation...")
    
    # Initialize counters and result dictionaries
    orig_success = 0
    orig_failure = 0
    orig_times = {}
    fork_success = 0
    fork_failure = 0
    fork_times = {}
    thread_success = 0
    thread_failure = 0
    thread_times = {}
    
    # Create tasks for original SDK simulation
    orig_tasks = []
    for i in range(num_orders):
        uniq_price = price_suffix_change(price, i)
        orig_tasks.append(create_limit_buy_order__orig_sdk(client_orig, uniq_price, size, nonce_manager))
    
    # Create tasks for fork SDK simulation
    fork_tasks = []
    for i in range(num_orders):
        uniq_price = price_suffix_change(price, i)
        fork_tasks.append(create_limit_buy_order__fork_sdk(client_fork, uniq_price, size, nonce_manager))

    # Create tasks for threading simulation
    thread_tasks = []
    # for i in range(num_orders):
    #     thread_tasks.append(create_limit_buy_order__orig_sdk__threading(client_orig_thread, price, size, nonce_manager))
    
    # Measure total time for running all implementations
    total_start_time = time.time()
    
    # Run original SDK tasks
    orig_total_start_time = time.time()
    orig_results = await asyncio.gather(*orig_tasks, return_exceptions=True)
    orig_total_time = time.time() - orig_total_start_time
    
    # Run fork SDK tasks
    fork_total_start_time = time.time()
    fork_results = await asyncio.gather(*fork_tasks, return_exceptions=True)
    fork_total_time = time.time() - fork_total_start_time
    
    # Run threading implementation tasks
    thread_total_start_time = time.time()
    thread_results = await asyncio.gather(*thread_tasks, return_exceptions=True)
    thread_total_time = time.time() - thread_total_start_time
    
    # Calculate total time for the entire test
    total_time = time.time() - total_start_time
    
    # Process original SDK results
    for i, result in enumerate(orig_results):
        if isinstance(result, Exception):
            log.error(f"Error in original SDK run {i}: {result}")
            log.exception(result)
            orig_failure += 1
        else:
            orig_times[result["cloid"]] = result["duration"]
            orig_success += 1
    
    # Process fork SDK results
    for i, result in enumerate(fork_results):
        if isinstance(result, Exception):
            log.error(f"Error in fork SDK run {i}: {result}")
            log.exception(result)
            fork_failure += 1
        else:
            fork_times[result["cloid"]] = result["duration"]
            fork_success += 1
    
    # Process threading implementation results
    for i, result in enumerate(thread_results):
        if isinstance(result, Exception):
            log.error(f"Error in threading implementation run {i}: {result}")
            thread_failure += 1
        else:
            thread_times[result["cloid"]] = result["duration"]
            thread_success += 1
    
    log.info(f"Total time for running all implementations sequentially: {total_time:.4f}s")
    
    # Calculate statistics
    orig_durations = list(orig_times.values())
    fork_durations = list(fork_times.values())
    thread_durations = list(thread_times.values())
    
    # Print performance comparison
    log.info("===== PERFORMANCE COMPARISON =====")
    log.info(f"Original SDK Simulation - Successful runs: {orig_success}, Failed runs: {orig_failure}")
    log.info(f"  Total time for all {num_orders} runs: {orig_total_time:.4f}s")
    if orig_durations:
        log.info(f"  Min time per run: {min(orig_durations):.4f}s")
        log.info(f"  Max time per run: {max(orig_durations):.4f}s")
        log.info(f"  Avg time per run: {statistics.mean(orig_durations):.4f}s")
        log.info(f"  Median time per run: {statistics.median(orig_durations):.4f}s")
        if len(orig_durations) > 1:
            log.info(f"  Std dev: {statistics.stdev(orig_durations):.4f}s")
    
    log.info(f"Fork SDK Simulation - Successful runs: {fork_success}, Failed runs: {fork_failure}")
    log.info(f"  Total time for all {num_orders} runs: {fork_total_time:.4f}s")
    if fork_durations:
        log.info(f"  Min time per run: {min(fork_durations):.4f}s")
        log.info(f"  Max time per run: {max(fork_durations):.4f}s")
        log.info(f"  Avg time per run: {statistics.mean(fork_durations):.4f}s")
        log.info(f"  Median time per run: {statistics.median(fork_durations):.4f}s")
        if len(fork_durations) > 1:
            log.info(f"  Std dev: {statistics.stdev(fork_durations):.4f}s")
    
    # log.info(f"Threading Simulation - Successful runs: {thread_success}, Failed runs: {thread_failure}")
    # log.info(f"  Total time for all {num_orders} runs: {thread_total_time:.4f}s")
    # if thread_durations:
    #     log.info(f"  Min time per run: {min(thread_durations):.4f}s")
    #     log.info(f"  Max time per run: {max(thread_durations):.4f}s")
    #     log.info(f"  Avg time per run: {statistics.mean(thread_durations):.4f}s")
    #     log.info(f"  Median time per run: {statistics.median(thread_durations):.4f}s")
    #     if len(thread_durations) > 1:
    #         log.info(f"  Std dev: {statistics.stdev(thread_durations):.4f}s")
    
    log.info("=================================")

async def add_margin_balance(web3: AsyncWeb3, price: str, size: str, num_orders: int, private_key: str):
    margin_account = MarginAccountFork(
        web3=web3, contract_address=constants.testnet_kuru_contract_addresses["margin_account"], private_key=private_key
    )

    size_mon = float(price) * float(size) * num_orders  # make deposit for num_orders orders
    size_wei = to_wei(size_mon, "ether")
    size_wei = 10 * math.ceil(float(size_wei) / 10)

    margin_account_deposit_tx_hash = await margin_account.deposit(margin_account.NATIVE, size_wei)
    log.info("Deposit transaction hash", tx_hash=margin_account_deposit_tx_hash)

    assert margin_account_deposit_tx_hash is not None
    assert len(margin_account_deposit_tx_hash) > 0

    # Wait for the deposit transaction to be confirmed
    tx_receipt = await web3.eth.wait_for_transaction_receipt(HexStr(margin_account_deposit_tx_hash))
    assert tx_receipt["status"] == 1, "Deposit transaction failed"
    log.info("Deposit transaction confirmed", block_number=tx_receipt["blockNumber"])


async def create_limit_buy_order__orig_sdk(client: ClientOrderExecutor, price: str, size: str, nonce_manager: NonceManager):


    #nonce = await get_next_nonce(client)
    nonce = await nonce_manager.get_next_nonce()
    log.info("Order orign SDK", nonce=nonce, wallet_address=client.wallet_address)

    market_address = constants.testnet_market_addresses["TEST_CHOG_MON"]
    order = OrderRequest(
        market_address=market_address,
        order_type="limit",
        side="buy",
        price=price,
        size=size,
        post_only=False,
        #tick_normalization="round_up"
    )
    tx_options = TxOptions(nonce=nonce)
    start_time = time.time()
    log.info("Placing limit buy order", nonce=nonce, size=order.size, price=order.price)
    cloid = await client.place_order(order, tx_options, async_execution=True)

    assert cloid is not None
    assert len(cloid) > 0

    # End time tracking - this is when the transaction is completed
    end_time = time.time()
    duration = end_time - start_time

    log.info(
        "Order placed successfully by orig SDK",
        nonce=nonce,
        cloid=cloid,
        duration=f"{duration:.4f}",
    )

    return {"cloid": cloid, "duration": duration}


async def create_limit_buy_order__fork_sdk(client: ClientOrderExecutorFork, price: str, size: str, nonce_manager: NonceManager):
    nonce = await nonce_manager.get_next_nonce()
    log.info("Order fork SDK", nonce=nonce, wallet_address=client.wallet_address)

    market_address = constants.testnet_market_addresses["TEST_CHOG_MON"]
    order = OrderRequest(
        market_address=market_address,
        order_type="limit",
        side="buy",
        price=price,
        size=size,
        post_only=False,
        #tick_normalization="round_up"
    )
    tx_options = TxOptions(nonce=nonce)
    start_time = time.time()
    log.info("Placing limit buy order by fork SDK", nonce=nonce, size=order.size, price=order.price)
    try:
        cloid = await client.place_order(order, tx_options, async_execution=True)
    except Exception as e:
        log.error("Error in fork SDK", nonce=nonce)
        log.exception(e)
        assert False, "Fork SDK failed to place order"

    assert cloid is not None
    assert len(cloid) > 0

    # End time tracking - this is when the transaction is completed
    end_time = time.time()
    duration = end_time - start_time

    log.info(
        "Order placed successfully by fork SDK",
        nonce=nonce,
        cloid=cloid,
        duration=f"{duration:.4f}",
    )

    return {"cloid": cloid, "duration": duration}

# async def create_limit_buy_order__orig_sdk__threading(client: ClientOrderExecutor, price: str, size: str, nonce_manager: NonceManager):
#     # Create a Future object that will be set when the thread completes
#     loop = asyncio.get_event_loop()
#     future = loop.create_future()
#
#     def thread_function():
#         try:
#             loop_thread = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop_thread)
#             #loop_thread.run_forever()
#
#
#             future_thread = asyncio.run_coroutine_threadsafe(create_limit_buy_order__orig_sdk(client, price, size, nonce_manager), loop_thread)
#             res = future_thread.result(timeout=10)
#
#             cloid = res["cloid"]
#             duration = res["duration"]
#
#             log.info(
#                 "Order placed successfully",
#                 cloid=cloid,
#                 duration=f"{duration:.4f}",
#             )
#
#             # Set the Future's result with the timing information
#             loop.call_soon_threadsafe(
#                 future.set_result,
#                 {"cloid": cloid, "duration": duration}
#             )
#         except Exception as e:
#             log.exception(e)
#             # If there's an error, set the Future's exception
#             loop.call_soon_threadsafe(future.set_exception, e)
#
#     # Create and start the thread
#     thread = threading.Thread(target=thread_function, daemon=True)
#     thread.start()
#
#     # Wait for the future to be resolved
#     return await future
