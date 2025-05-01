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
