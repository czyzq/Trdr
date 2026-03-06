"""Signal generation service - wraps main.py signal generation for API use"""
import asyncio
from typing import List

# Lazy imports to avoid circular dependencies
def get_generate_signals():
    """Get generate_signals function from main.py"""
    from main import generate_signals as _generate_signals
    return _generate_signals


async def generate_signals() -> List:
    """Generate trading signals - delegates to main.py implementation"""
    gen_signals = get_generate_signals()
    return await gen_signals()
