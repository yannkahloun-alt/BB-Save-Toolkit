"""Human-readable formatting for diagnostics and reports."""

def component_summary(components: dict) -> str:
    return "; ".join(
        f"{stat}:{data['value']}×{data['weight']}→{data['utility']:.2f}"
        for stat, data in components.items()
    )
