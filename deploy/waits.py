"""Ed's waits and retries: for an AgentCore resource to finish changing, and for a
new role or permission to reach the service that uses it."""

import time
from collections.abc import Callable
from typing import Any

# What an AgentCore resource's status is while it's still changing.
BUSY = ("CREATING", "UPDATING", "SYNCHRONIZING")
# How long to pause between looks at a resource that's changing.
LOOK_EVERY = 3


def pause(seconds: float) -> None:
    """Wait, as every wait here does, so the tests can take the time out."""
    time.sleep(seconds)


def wait_for(get: Callable[[], dict[str, Any]], label: str) -> dict[str, Any]:
    """Wait while a resource is being created or updated, then print its status and
    any reasons, and return it."""
    while (resource := get())["status"] in BUSY:
        pause(LOOK_EVERY)
    print(f"{label}: {resource['status']}")
    for reason in resource.get("statusReasons", []):
        print(f"  {reason}")
    return resource


def retry[T](
    attempt: Callable[[], T],
    waiting: Callable[[Exception], bool],
    *,
    tries: int,
    every: float,
    message: str,
) -> T:
    """Call attempt until it works, pausing after each error that waiting says is
    worth waiting out, and raising any other error, or the last after the tries."""
    for _ in range(tries - 1):
        try:
            return attempt()
        except Exception as error:
            if not waiting(error):
                raise
            print(message)
            pause(every)
    return attempt()


def until_gone(listing: Callable[[], list[Any]], label: str, tries: int = 100) -> None:
    """Wait until a listing is empty, as Ed's teardown waited for a Gateway's
    targets and an engine's policies to go, giving up after the tries."""
    for _ in range(tries):
        if not listing():
            return
        pause(LOOK_EVERY)
    raise RuntimeError(f"The {label} didn't go")


def mentions(text: str, *words: str) -> bool:
    """Whether a message names any of these words, as Ed's retries tell a
    permission still on its way from any other error."""
    return any(word.lower() in text.lower() for word in words)


def says(*words: str) -> Callable[[Exception], bool]:
    """Whether an error's message names any of these words."""
    return lambda error: mentions(str(error), *words)
