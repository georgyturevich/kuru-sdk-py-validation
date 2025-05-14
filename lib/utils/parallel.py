import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

import asynciolimiter
import structlog

log = structlog.get_logger(__name__)


async def run_tasks_in_parallel(
    fn: Callable[..., Any],
    args_list: Optional[List[Tuple[Any, ...]]] = None,
    kwargs_list: Optional[List[Dict[str, Any]]] = None,
    rate_limit: int = 1,
    max_burst: Optional[int] = 5,
) -> Tuple[int, int, Dict[str, float]]:
    """
    Run `fn` in parallel across a thread pool with token-bucket rate limiting.

    Args:
        fn: target function or coroutine
        args_list: list of positional args tuples
        kwargs_list: list of kwargs dicts
        rate_limit: max calls per-second
        max_burst: In case there's a delay, schedule no more than this many
            calls at once.

    Returns:
        success_count, failure_count, time_stats_dict
    """
    limiter = asynciolimiter.Limiter(rate=rate_limit, max_burst=max_burst)

    # Ensure args_list and kwargs_list are mutable lists for sequence operations
    if args_list is None:
        args_list = [()]
    else:
        args_list = list(args_list)
    if kwargs_list is None:
        kwargs_list = [{}]
    else:
        kwargs_list = list(kwargs_list)

    total = max(len(args_list), len(kwargs_list))
    if len(args_list) == 1 and total > 1:
        args_list *= total
    if len(kwargs_list) == 1 and total > 1:
        kwargs_list *= total

    success = failure = 0
    time_stats = {}  # Dictionary to store timing statistics

    async def _async_wrapper(args: Tuple[Any, ...], kwargs: Dict[str, Any]):

        log.debug("_async_wrapper before acquire")
        await limiter.wait()
        log.debug("_async_wrapper after acquire")
        return await fn(*args, **kwargs)

    promises = [_async_wrapper(args, kwargs) for args, kwargs in zip(args_list, kwargs_list)]
    log.debug("Running parallel tasks", promises=promises)
    results = await asyncio.gather(*promises, return_exceptions=True)
    log.debug("Parallel tasks finished", results=results)
    for result in results:
        if isinstance(result, Exception):
            failure += 1
            import traceback

            log.error(
                f"Exception in parallel task '{result}'; Stacktrace: {"".join(traceback.format_exception(result))} "
            )
        else:
            if isinstance(result, dict) and "cloid" in result and "duration" in result:
                time_stats[result["cloid"]] = result["duration"]
            success += 1

    return success, failure, time_stats
