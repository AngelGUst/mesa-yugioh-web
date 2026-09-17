import httpx


YGOPRODECK_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"


class YGOProDeckError(RuntimeError):
    pass


def fetch_cards(query: str | None = None) -> list[dict]:
    params = {"name": query} if query else {}
    try:
        response = httpx.get(YGOPRODECK_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise YGOProDeckError("No fue posible consultar YGOProDeck") from exc
    return payload.get("data", [])


def to_card_values(raw: dict) -> dict:
    images = raw.get("card_images") or [{}]
    return {
        "ygoprodeck_id": raw["id"],
        "name": raw["name"],
        "card_type": raw.get("type"),
        "description": raw.get("desc"),
        "atk": raw.get("atk"),
        "def_": raw.get("def"),
        "level": raw.get("level"),
        "race": raw.get("race"),
        "attribute": raw.get("attribute"),
        "image_url": images[0].get("image_url"),
        "raw_data": raw,
    }
