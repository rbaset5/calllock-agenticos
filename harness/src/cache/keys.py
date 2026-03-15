def tenant_key(tenant_id: str, category: str, item_id: str) -> str:
    return f"t:{tenant_id}:{category}:{item_id}"


def global_key(category: str, item_id: str) -> str:
    return f"g:{category}:{item_id}"
