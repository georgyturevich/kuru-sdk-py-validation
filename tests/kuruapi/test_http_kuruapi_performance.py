import os
import threading
import time
import statistics
import logging
import asyncio
from dotenv import load_dotenv
from kuru_sdk.api import KuruAPI
from kuru_sdk_fork.api import KuruAPI as KuruAPIFork
import pytest

# Set up logger
logger = logging.getLogger(__name__)

counter = 0
lock = threading.Lock()

def increment_counter_with_lock():
    global counter
    with lock:
        counter += 1
        return counter


@pytest.mark.asyncio
async def test_compare_performance():
    load_dotenv()

    # Number of runs (change this value to run more or fewer tests)
    n_runs = 30

    logger.info(f"Running performance test with {n_runs} executions for each SDK...")

    # Initialize counters and result dictionaries
    orig_success = 0
    orig_failure = 0
    orig_times = {}
    fork_success = 0
    fork_failure = 0
    fork_times = {}

    api = KuruAPI(url=os.getenv("KURU_API_URL"))
    api_fork = KuruAPIFork(url=os.getenv("KURU_API_URL"))

    # Create tasks for original SDK
    orig_tasks = []
    for i in range(n_runs):
        orig_tasks.append(get_user_order_orign_sdk(api))

    # Create tasks for fork SDK
    fork_tasks = []
    for i in range(n_runs):
        fork_tasks.append(get_user_orders_fork_sdk(api_fork))

    # Measure total time for running both SDKs in parallel
    total_start_time = time.time()

    # Run original SDK tasks with its own asyncio.gather
    orig_total_start_time = time.time()
    orig_results = await asyncio.gather(*orig_tasks, return_exceptions=True)
    orig_total_time = time.time() - orig_total_start_time

    # Run fork SDK tasks with its own asyncio.gather
    fork_total_start_time = time.time()
    fork_results = await asyncio.gather(*fork_tasks, return_exceptions=True)
    fork_total_time = time.time() - fork_total_start_time

    # Calculate total time for the entire test
    total_time = time.time() - total_start_time

    # Process original SDK results
    for i, result in enumerate(orig_results):
        if isinstance(result, Exception):
            logger.error(f"Error in original SDK run {i}: {result}")
            orig_failure += 1
        else:
            orig_times[result["cloid"]] = result["duration"]
            orig_success += 1

    # Process fork SDK results
    for i, result in enumerate(fork_results):
        if isinstance(result, Exception):
            logger.error(f"Error in fork SDK run {i}: {result}")
            fork_failure += 1
        else:
            fork_times[result["cloid"]] = result["duration"]
            fork_success += 1

    logger.info(f"Total time for running both SDKs sequentially: {total_time:.4f}s")

    # Calculate statistics
    orig_durations = list(orig_times.values())
    fork_durations = list(fork_times.values())

    await print_durations_summary(fork_durations, fork_failure, fork_success, fork_total_time, n_runs, orig_durations,
                                  orig_failure, orig_success, orig_total_time)


async def get_user_orders_fork_sdk(api_fork: KuruAPIFork):
    c = increment_counter_with_lock()
    logger.info(f"Running {c} request with fork SDK...")
    start_time = time.time()
    orders_response_fork = await api_fork.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    duration = time.time() - start_time
    logger.info(f"Completed {c} request with fork SDK")
    assert len(orders_response_fork) > 0
    # Return timing information in the format expected by run_tasks_in_parallel
    return {"cloid": f"fork_{time.time()}", "duration": duration}


async def get_user_order_orign_sdk(api: KuruAPI):
    c = increment_counter_with_lock()
    logger.info(f"Running {c} request with orig SDK...")

    start_time = time.time()

    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    duration = time.time() - start_time
    logger.info(f"Completed {c} request with orig SDK")
    assert len(orders_response) > 0
    # Return timing information in the format expected by run_tasks_in_parallel
    return {"cloid": f"orig_{time.time()}", "duration": duration}



async def print_durations_summary(fork_durations, fork_failure, fork_success, fork_total_time, n_runs, orig_durations,
                                  orig_failure, orig_success, orig_total_time):
    logger.info("===== PERFORMANCE COMPARISON =====")
    logger.info(f"Original SDK - Successful runs: {orig_success}, Failed runs: {orig_failure}")
    logger.info(f"  Total time for all {n_runs} runs: {orig_total_time:.4f}s")
    if orig_durations:
        logger.info(f"  Min time per run: {min(orig_durations):.4f}s")
        logger.info(f"  Max time per run: {max(orig_durations):.4f}s")
        logger.info(f"  Avg time per run: {statistics.mean(orig_durations):.4f}s")
        logger.info(f"  Median time per run: {statistics.median(orig_durations):.4f}s")
        if len(orig_durations) > 1:
            logger.info(f"  Std dev: {statistics.stdev(orig_durations):.4f}s")
    logger.info(f"Fork SDK - Successful runs: {fork_success}, Failed runs: {fork_failure}")
    logger.info(f"  Total time for all {n_runs} runs: {fork_total_time:.4f}s")
    if fork_durations:
        logger.info(f"  Min time per run: {min(fork_durations):.4f}s")
        logger.info(f"  Max time per run: {max(fork_durations):.4f}s")
        logger.info(f"  Avg time per run: {statistics.mean(fork_durations):.4f}s")
        logger.info(f"  Median time per run: {statistics.median(fork_durations):.4f}s")
        if len(fork_durations) > 1:
            logger.info(f"  Std dev: {statistics.stdev(fork_durations):.4f}s")
    logger.info("=================================")
