import base64
import hashlib
import os
import time


def gen_signature(method: str) -> tuple[int, str]:
    ak = os.environ.get("EDUCODER_AK", "")
    sk = os.environ.get("EDUCODER_SK", "")
    if not ak or not sk:
        raise ValueError("请在本机设置 EDUCODER_AK 和 EDUCODER_SK 环境变量")
    ts = int(time.time() * 1000)
    params = f"method={method.upper()}&ak={ak}&sk={sk}&time={ts}"
    encoded = base64.b64encode(params.encode()).decode()
    return ts, hashlib.md5(encoded.encode()).hexdigest()
