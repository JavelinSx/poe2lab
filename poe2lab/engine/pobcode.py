import base64
import zlib


def decode_pob_code(code: str) -> str:
    """PoB export code (URL-safe base64 of zlib-compressed XML) -> build XML."""
    code = code.strip().replace("-", "+").replace("_", "/")
    code += "=" * (-len(code) % 4)
    return zlib.decompress(base64.b64decode(code)).decode("utf-8")


def encode_pob_code(xml: str) -> str:
    return base64.b64encode(zlib.compress(xml.encode("utf-8"), 9)).decode("ascii").replace("+", "-").replace("/", "_")
