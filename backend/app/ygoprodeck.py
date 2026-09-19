import httpx
import re


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
        "human_readable_card_type": raw.get("humanReadableCardType"),
        "frame_type": raw.get("frameType"),
        "archetype": raw.get("archetype"),
        "ygoprodeck_url": raw.get("ygoprodeck_url"),
        "image_url": images[0].get("image_url"),
        "image_url_small": images[0].get("image_url_small"),
        "image_url_cropped": images[0].get("image_url_cropped"),
        "raw_data": raw,
    }


def to_card_print_values(raw_print: dict) -> dict:
    set_code = raw_print["set_code"]
    language_match = re.search(r"-(EN|SP|FR|DE|IT|PT|ES|JP|KR|CN)\d", set_code, re.IGNORECASE)
    return {
        "set_name": raw_print["set_name"],
        "set_code": set_code,
        "language": language_match.group(1).upper() if language_match else None,
        "rarity": raw_print.get("set_rarity"),
        "rarity_code": raw_print.get("set_rarity_code"),
        "price": raw_print.get("set_price"),
    }
