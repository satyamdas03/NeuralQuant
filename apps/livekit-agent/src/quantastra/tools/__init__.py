"""QuantAstra tool registrations — LiveKit function-calling tools."""

from livekit.agents import llm


def register_all_tools() -> llm.FunctionContext:
    """Register all QuantAstra tools into a single FunctionContext."""
    from quantastra.tools.market_tools import MarketTools
    from quantastra.tools.portfolio_tools import PortfolioTools
    from quantastra.tools.screener_tools import ScreenerTools
    from quantastra.tools.research_tools import ResearchTools
    from quantastra.tools.macro_tools import MacroTools

    ctx = llm.FunctionContext()
    for tools_cls in [MarketTools, PortfolioTools, ScreenerTools, ResearchTools, MacroTools]:
        tools_cls._register(ctx)
    return ctx
