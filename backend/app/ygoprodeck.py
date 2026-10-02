import base64
import json
import re
import struct

import httpx


YGOPRODECK_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"


class YGOProDeckError(RuntimeError):
    pass


def decode_ydke(ydke_str: str) -> dict[str, list[int]]:
    cleaned = ydke_str.strip()
    if cleaned.startswith("ydke://"):
        cleaned = cleaned[7:]
    parts = cleaned.split("!")

    def decode_b64_ids(b64: str) -> list[int]:
        if not b64:
            return []
        rem = len(b64) % 4
        if rem > 0:
            b64 += "=" * (4 - rem)
        try:
            raw = base64.b64decode(b64)
            count = len(raw) // 4
            return list(struct.unpack(f"<{count}I", raw[: count * 4]))
        except Exception:
            return []

    main_ids = decode_b64_ids(parts[0]) if len(parts) > 0 else []
    extra_ids = decode_b64_ids(parts[1]) if len(parts) > 1 else []
    side_ids = decode_b64_ids(parts[2]) if len(parts) > 2 else []
    return {"main": main_ids, "extra": extra_ids, "side": side_ids}


def parse_ydk_text(ydk_text: str) -> dict[str, list[int]]:
    section = None
    main_ids, extra_ids, side_ids = [], [], []
    for line in ydk_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#created"):
            continue
        if line == "#main":
            section = "main"
        elif line == "#extra":
            section = "extra"
        elif line.startswith("!side"):
            section = "side"
        elif line.isdigit():
            val = int(line)
            if section == "main":
                main_ids.append(val)
            elif section == "extra":
                extra_ids.append(val)
            elif section == "side":
                side_ids.append(val)
    return {"main": main_ids, "extra": extra_ids, "side": side_ids}


def parse_deck_content(content: str) -> tuple[str | None, dict[str, list[int | str]]]:
    content = content.strip()
    if content.startswith("ydke://"):
        return None, decode_ydke(content)

    if content.startswith("{"):
        try:
            data = json.loads(content)
            name = data.get("name") or data.get("deck_name")

            def expand_section(items):
                expanded = []
                for item in items:
                    if isinstance(item, (int, str)):
                        expanded.append(item)
                    elif isinstance(item, dict):
                        card_ref = item.get("id") or item.get("ygoprodeck_id") or item.get("name")
                        qty = item.get("quantity", 1)
                        for _ in range(qty):
                            if card_ref is not None:
                                expanded.append(card_ref)
                return expanded

            sections = {
                "main": expand_section(data.get("main") or []),
                "extra": expand_section(data.get("extra") or []),
                "side": expand_section(data.get("side") or []),
            }
            return name, sections
        except json.JSONDecodeError:
            pass

    if "#main" in content or "#extra" in content or "!side" in content:
        return None, parse_ydk_text(content)

    if "!" in content:
        return None, decode_ydke("ydke://" + content)

    raise YGOProDeckError("Formato no reconocido. Pega un código YDKe (ydke://...), archivo .YDK o JSON.")


def fetch_cards_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    results = []
    chunk_size = 80
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        params = {"id": ",".join(map(str, chunk))}
        try:
            response = httpx.get(YGOPRODECK_URL, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            results.extend(payload.get("data", []))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                continue
            raise YGOProDeckError("No fue posible consultar cartas por ID en YGOProDeck") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise YGOProDeckError("No fue posible consultar cartas por ID en YGOProDeck") from exc
    return results


def fetch_cards(query: str | None = None) -> list[dict]:
    params = {"fname": query} if query else {}
    try:
        response = httpx.get(YGOPRODECK_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400 and query:
            return []
        raise YGOProDeckError("No fue posible consultar YGOProDeck") from exc
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
