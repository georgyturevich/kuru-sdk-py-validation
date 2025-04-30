import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Awaitable
from pyrate_limiter import Duration, Rate, Limiter
from pyrate_limiter.abstracts import AbstractClock
import structlog

log = structlog.get_logger(__name__)

class AsyncClock(AbstractClock):
    """A clock implementation that returns an awaitable timestamp"""
    
    def now(self) -> Awaitable[int]:
        """Return current timestamp as an awaitable"""
        async def _now() -> int:
            return int(asyncio.get_event_loop().time() * 1000)
        return _now()

async def run_tasks_in_parallel(
    fn: Callable[..., Any],
    args_list: Optional[List[Tuple[Any, ...]]] = None,
    kwargs_list: Optional[List[Dict[str, Any]]] = None,
    rate_limit: int = 1,
    interval: Union[int, Duration] = Duration.SECOND,
    max_delay: Union[int, Duration] = 2 * Duration.SECOND,
    raise_when_fail: bool = False,
) -> Tuple[int, int, Dict[str, float]]:
    """
    Run `fn` in parallel across a thread pool with token-bucket rate limiting.

    Args:
        fn: target function or coroutine
        args_list: list of positional args tuples
        kwargs_list: list of kwargs dicts
        rate_limit: max calls per interval
        interval: rate-limiter interval duration
        max_delay: max delay for acquiring token
        max_workers: ThreadPool max_workers (defaults to rate_limit)
        raise_when_fail: if True, limiter.try_acquire raises on failure

    Returns:
        success_count, failure_count, time_stats_dict
    """
    rate = Rate(limit=rate_limit, interval=interval)
    async_clock = AsyncClock()
    limiter = Limiter(rate, clock=async_clock, raise_when_fail=raise_when_fail, max_delay=max_delay)

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
        await limiter.try_acquire("parallel_task")
        return await fn(*args, **kwargs)
        

    promises = [_async_wrapper(args, kwargs) for args, kwargs in zip(args_list, kwargs_list)]
    log.info("Running parallel tasks", promises=promises)
    results = await asyncio.gather(*promises, return_exceptions=True)
    log.info("Parallel tasks finished", results=results)
    for result in results:
        if isinstance(result, Exception):
            failure += 1
            import traceback
            log.error("Exception in task", error=str(result), tb="".join(traceback.format_exception(result)))
        else:
            if isinstance(result, dict) and 'cloid' in result and 'duration' in result:
                time_stats[result['cloid']] = result['duration']
            success += 1

    return success, failure, time_stats 