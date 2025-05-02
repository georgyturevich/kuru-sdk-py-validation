import statistics

import structlog

log = structlog.get_logger(__name__)


def print_individual_orders_stats(success_count, time_stats, total_duration):
    # Print detailed time statistics for individual orders
    if time_stats:
        print("\n--- Time Statistics ---")
        print(f"{'Order':<10} {'Duration (s)':<15}")
        print("-" * 25)

        durations = list(time_stats.values())
        for cloid, duration in sorted(time_stats.items()):
            print(f"{cloid:<10} {duration:.4f}")

        if success_count > 0:
            print("\n--- Summary Statistics ---")
            avg_time = sum(durations) / len(durations)
            print(f"Average time: {avg_time:.4f} seconds")

            if len(durations) > 1:
                min_time = min(durations)
                max_time = max(durations)
                median_time = statistics.median(durations)
                std_dev = statistics.stdev(durations) if len(durations) > 1 else 0

                print(f"Min time: {min_time:.4f} seconds")
                print(f"Max time: {max_time:.4f} seconds")
                print(f"Median time: {median_time:.4f} seconds")
                print(f"Standard deviation: {std_dev:.4f} seconds")

            print(f"Total throughput: {success_count / total_duration:.2f} orders/second")


def print_cancel_order_stats(cancel_stats):
    """
    Print detailed time statistics for order cancellations.

    Args:
        cancel_stats (dict): Dictionary mapping cloid to cancellation duration
    """
    if not cancel_stats:
        log.info("No order cancellation statistics available.")
        return

    print("\n--- Order Cancellation Statistics ---")
    print(f"{'Order':<10} {'Duration (s)':<15}")
    print("-" * 25)

    durations = list(cancel_stats.values())
    for cloid, duration in sorted(cancel_stats.items()):
        print(f"{cloid:<10} {duration:.4f}")

    print("\n--- Summary Cancellation Statistics ---")
    avg_time = sum(durations) / len(durations)
    print(f"Average time: {avg_time:.4f} seconds")

    if len(durations) > 1:
        min_time = min(durations)
        max_time = max(durations)
        median_time = statistics.median(durations)
        std_dev = statistics.stdev(durations) if len(durations) > 1 else 0

        print(f"Min time: {min_time:.4f} seconds")
        print(f"Max time: {max_time:.4f} seconds")
        print(f"Median time: {median_time:.4f} seconds")
        print(f"Standard deviation: {std_dev:.4f} seconds")


def prepare_ws_delay_statistics(order_times):
    # Collect delays for orders that have received WebSocket events
    tx_to_ws_delays = []
    order_to_tx_delays = []
    total_delays = []

    stats = None
    for tx_hash, times in order_times.items():
        if "ws_time" in times:
            start_time = float(times["start_time"])
            end_time = float(times["end_time"])
            ws_time = float(times["ws_time"])

            tx_to_ws_delay = ws_time - end_time
            order_to_tx_delay = end_time - start_time
            total_delay = ws_time - start_time

            tx_to_ws_delays.append(tx_to_ws_delay)
            order_to_tx_delays.append(order_to_tx_delay)
            total_delays.append(total_delay)
    if tx_to_ws_delays:
        stats = {
            "count": len(tx_to_ws_delays),
            "tx_to_ws": {
                "min": min(tx_to_ws_delays),
                "max": max(tx_to_ws_delays),
                "mean": statistics.mean(tx_to_ws_delays),
                "median": statistics.median(tx_to_ws_delays),
            },
            "order_to_tx": {
                "min": min(order_to_tx_delays),
                "max": max(order_to_tx_delays),
                "mean": statistics.mean(order_to_tx_delays),
                "median": statistics.median(order_to_tx_delays),
            },
            "total": {
                "min": min(total_delays),
                "max": max(total_delays),
                "mean": statistics.mean(total_delays),
                "median": statistics.median(total_delays),
            },
        }

        if len(tx_to_ws_delays) > 1:
            stats["tx_to_ws"]["std_dev"] = statistics.stdev(tx_to_ws_delays)
            stats["order_to_tx"]["std_dev"] = statistics.stdev(order_to_tx_delays)
            stats["total"]["std_dev"] = statistics.stdev(total_delays)
    return stats


def prepare_order_details_statistics(order_times):
    result = []
    for tx_hash, times in order_times.items():
        if "ws_time" in times:
            start_time = float(times["start_time"])
            end_time = float(times["end_time"])
            ws_time = float(times["ws_time"])

            record = {
                "cloid": times["cloid"],
                "tx_hash": tx_hash,
                "initiation_time": start_time,
                "completion_time": end_time,
                "ws_event_time": ws_time,
                "order_execution_duration": end_time - start_time,
                "ws_event_delay": ws_time - end_time,
                "total_duration": ws_time - start_time,
            }
            result.append(record)
    return sorted(result, key=lambda x: x["cloid"])


def print_order_detailed_stats(ws_order_tester):
    # Print detailed order statistics
    print("\n--- Detailed Order Statistics ---")
    print(
        f"{'CLOID':<10} {'TX Hash':<12} {'Init(rel)':<10} {'Complete(rel)':<15} {'WS Event':<10} {'Duration':<10} {'WS Delay':<10} {'Total':<10}"
    )
    print("-" * 115)
    order_details = ws_order_tester.get_order_details()
    start_reference = min([order["initiation_time"] for order in order_details]) if order_details else 0
    for order in order_details:
        # Normalize timestamps relative to the first order
        init_rel = order["initiation_time"] - start_reference
        complete_rel = order["completion_time"] - start_reference
        ws_rel = order["ws_event_time"] - start_reference

        print(
            f"{order['cloid']:<10} {order['tx_hash'][:10]:<12} {init_rel:.4f}{'':>4} {complete_rel:.4f}{'':>9} {ws_rel:.4f}{'':>4} {order['order_execution_duration']:.4f}{'':>4} {order['ws_event_delay']:.4f}{'':>4} {order['total_duration']:.4f}"
        )


def print_ws_stats(ws_order_tester):
    # Print WebSocket delay statistics
    ws_stats = ws_order_tester.get_delay_statistics()
    if ws_stats:
        print("\n--- WebSocket Event Delay Statistics ---")

        print("\nOrder Execution (Order Initiation to Transaction Completion):")
        print(f"Minimum: {ws_stats['order_to_tx']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['order_to_tx']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['order_to_tx']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['order_to_tx']['median']:.4f} seconds")
        if "std_dev" in ws_stats["order_to_tx"]:
            print(f"Standard deviation: {ws_stats['order_to_tx']['std_dev']:.4f} seconds")

        print("\nWebSocket Notification Delay (Transaction Completion to WebSocket Event):")
        print(f"Minimum: {ws_stats['tx_to_ws']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['tx_to_ws']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['tx_to_ws']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['tx_to_ws']['median']:.4f} seconds")
        if "std_dev" in ws_stats["tx_to_ws"]:
            print(f"Standard deviation: {ws_stats['tx_to_ws']['std_dev']:.4f} seconds")

        print("\nTotal Delay (Order Initiation to WebSocket Event):")
        print(f"Minimum: {ws_stats['total']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['total']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['total']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['total']['median']:.4f} seconds")
        if "std_dev" in ws_stats["total"]:
            print(f"Standard deviation: {ws_stats['total']['std_dev']:.4f} seconds")
    else:
        log.info("No WebSocket event delay statistics available.")
