import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pyrate_limiter import Duration, Rate, Limiter


def run_tasks_in_parallel(
    fn: Callable[..., Any],
    args_list: Optional[List[Tuple[Any, ...]]] = None,
    kwargs_list: Optional[List[Dict[str, Any]]] = None,
    rate_limit: int = 1,
    interval: Union[int, Duration] = Duration.SECOND,
    max_delay: Union[int, Duration] = 2 * Duration.SECOND,
    max_workers: Optional[int] = None,
    raise_when_fail: bool = False,
) -> Tuple[int, int]:
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
        success_count, failure_count
    """
    rate = Rate(limit=rate_limit, interval=interval)
    limiter = Limiter(rate, raise_when_fail=raise_when_fail, max_delay=max_delay)

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

    def _wrapper(args: Tuple[Any, ...], kwargs: Dict[str, Any]):
        limiter.try_acquire("parallel_task")
        if asyncio.iscoroutinefunction(fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(fn(*args, **kwargs))
            finally:
                loop.close()
        else:
            return fn(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=max_workers or rate_limit) as executor:
        futures = {
            executor.submit(_wrapper, args_list[i], kwargs_list[i]): i for i in range(total)
        }
        for fut in as_completed(futures):
            try:
                fut.result()
                success += 1
            except Exception as e:
                # print exception information
                print(f"Exception in task {futures[fut]}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

                failure += 1

    return success, failure 