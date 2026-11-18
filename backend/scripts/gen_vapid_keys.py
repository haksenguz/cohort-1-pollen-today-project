"""Print a fresh VAPID key pair for backend/.env.

uv run python scripts/gen_vapid_keys.py
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private = key.private_numbers().private_value.to_bytes(32, "big")
    print(f"VAPID_PUBLIC_KEY={_b64url(public)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(private)}")
    print("VAPID_SUBJECT=mailto:ismoiljonedu@gmail.com")


if __name__ == "__main__":
    main()
