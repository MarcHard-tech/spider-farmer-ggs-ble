"""Spider Farmer GGS BLE protocol v2 — framing, CRC and AES-128-CBC.

The 2026-08-17 controller firmware update replaced the plaintext-JSON BLE payload
(protocol v1) with an encrypted, chunked one (v2). This module is the transport
shim: everything above it — the JSON command set, the parsers, the entities — is
unchanged from v1.

Packet layout (one chunk of a message):

    off  size  field
    0    4     magic            aa aa 00 03
    4    2     length           packet length - 8          big-endian
    6    2     protocol version 00 02
    8    2     message id       shared across a message's chunks
    10   4     total length     full assembled ciphertext length
    14   4     chunk offset     this chunk's offset within the message
    18   2     chunk length     ciphertext bytes in this packet
    20   N     ciphertext       N = chunk length
    20+N 2     trailer          CRC16/MODBUS(header+ciphertext), big-endian

Crypto is AES-128-CBC with PKCS7 padding over the WHOLE reassembled ciphertext,
not per chunk — the CBC chain runs across chunk boundaries. The key and IV are
fixed literals recovered from the vendor app; the IV never varies, so the scheme
is deterministic.

Verified against 400 captured packets: 400/400 CRCs valid, 152/152 messages
decrypt to well-formed JSON.

Deliberately stdlib-only and free of Home Assistant imports so it can be tested
standalone. It prefers `cryptography` (C-backed, present in HA core) and falls
back to a pure-Python AES so it can never fail to import.
"""
from __future__ import annotations

import json
from typing import Optional

MAGIC = bytes.fromhex("aaaa0003")
VERSION = 2
KEY = b"iVi6D24KxbrvXUuO"
IV = b"RnWokNEvKW6LcWJg"
MAX_CHUNK = 400
HEADER_LEN = 20
TRAILER_LEN = 2


# ── CRC16/MODBUS ────────────────────────────────────────────────────────────

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


# ── AES-128 ─────────────────────────────────────────────────────────────────
# Fast path uses `cryptography`; the pure-Python implementation below is the
# fallback so this module has no hard dependency.

try:  # pragma: no cover - depends on the host environment
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def _cbc_decrypt(ct: bytes) -> bytes:
        d = Cipher(algorithms.AES(KEY), modes.CBC(IV)).decryptor()
        return d.update(ct) + d.finalize()

    def _cbc_encrypt(pt: bytes) -> bytes:
        e = Cipher(algorithms.AES(KEY), modes.CBC(IV)).encryptor()
        return e.update(pt) + e.finalize()

    USING_FALLBACK_AES = False

except ImportError:  # pragma: no cover
    USING_FALLBACK_AES = True

    def _sbox_tables():
        p = q = 1
        sbox = [0] * 256
        while True:
            p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
            q ^= q << 1
            q ^= q << 2
            q ^= q << 4
            q &= 0xFF
            if q & 0x80:
                q ^= 0x09
            x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) \
                  ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
            sbox[p] = (x ^ 0x63) & 0xFF
            if p == 1:
                break
        sbox[0] = 0x63
        inv = [0] * 256
        for i, v in enumerate(sbox):
            inv[v] = i
        return sbox, inv

    _SBOX, _INV_SBOX = _sbox_tables()
    _RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]

    def _xt(a: int) -> int:
        return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF

    def _mul(a: int, b: int) -> int:
        r = 0
        for _ in range(8):
            if b & 1:
                r ^= a
            a = _xt(a)
            b >>= 1
        return r & 0xFF

    def _expand(key: bytes):
        w = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
        for i in range(4, 44):
            t = list(w[i - 1])
            if i % 4 == 0:
                t = t[1:] + t[:1]
                t = [_SBOX[b] for b in t]
                t[0] ^= _RCON[i // 4 - 1]
            w.append([w[i - 4][j] ^ t[j] for j in range(4)])
        return [sum(w[4 * r:4 * r + 4], []) for r in range(11)]

    _RK = _expand(KEY)

    def _shift_rows(s, inverse):
        t = list(s)
        for r in range(1, 4):
            for c in range(4):
                if inverse:
                    t[((c + r) % 4) * 4 + r] = s[c * 4 + r]
                else:
                    t[c * 4 + r] = s[((c + r) % 4) * 4 + r]
        return t

    def _enc_block(pt: bytes) -> bytes:
        s = [pt[i] ^ _RK[0][i] for i in range(16)]
        for rnd in range(1, 10):
            s = [_SBOX[b] for b in s]
            s = _shift_rows(s, inverse=False)
            o = list(s)
            for c in range(4):
                a = o[c * 4:c * 4 + 4]
                s[c * 4 + 0] = _mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3]
                s[c * 4 + 1] = a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3]
                s[c * 4 + 2] = a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3)
                s[c * 4 + 3] = _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)
            s = [s[i] ^ _RK[rnd][i] for i in range(16)]
        s = [_SBOX[b] for b in s]
        s = _shift_rows(s, inverse=False)
        return bytes(s[i] ^ _RK[10][i] for i in range(16))

    def _dec_block(ct: bytes) -> bytes:
        s = [ct[i] ^ _RK[10][i] for i in range(16)]
        for rnd in range(9, 0, -1):
            s = _shift_rows(s, inverse=True)
            s = [_INV_SBOX[b] for b in s]
            s = [s[i] ^ _RK[rnd][i] for i in range(16)]
            o = list(s)
            for c in range(4):
                a = o[c * 4:c * 4 + 4]
                s[c * 4 + 0] = _mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13) ^ _mul(a[3], 9)
                s[c * 4 + 1] = _mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11) ^ _mul(a[3], 13)
                s[c * 4 + 2] = _mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14) ^ _mul(a[3], 11)
                s[c * 4 + 3] = _mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9) ^ _mul(a[3], 14)
        s = _shift_rows(s, inverse=True)
        s = [_INV_SBOX[b] for b in s]
        return bytes(s[i] ^ _RK[0][i] for i in range(16))

    def _cbc_decrypt(ct: bytes) -> bytes:
        out = bytearray()
        prev = IV
        for i in range(0, len(ct), 16):
            blk = ct[i:i + 16]
            d = _dec_block(blk)
            out += bytes(d[j] ^ prev[j] for j in range(16))
            prev = blk
        return bytes(out)

    def _cbc_encrypt(pt: bytes) -> bytes:
        out = bytearray()
        prev = IV
        for i in range(0, len(pt), 16):
            blk = bytes(pt[i + j] ^ prev[j] for j in range(16))
            c = _enc_block(blk)
            out += c
            prev = c
        return bytes(out)


# ── message-level crypto ────────────────────────────────────────────────────

class ProtocolError(Exception):
    """Raised when a packet or message cannot be decoded."""


def decrypt_message(ciphertext: bytes) -> bytes:
    """Decrypt a fully reassembled message and strip PKCS7 padding."""
    if not ciphertext or len(ciphertext) % 16:
        raise ProtocolError(f"ciphertext length {len(ciphertext)} is not a multiple of 16")
    pt = _cbc_decrypt(ciphertext)
    pad = pt[-1]
    if not 1 <= pad <= 16 or pt[-pad:] != bytes([pad]) * pad:
        raise ProtocolError("bad PKCS7 padding — wrong key, or corrupt message")
    return pt[:-pad]


def encrypt_message(plaintext: bytes) -> bytes:
    pad = 16 - (len(plaintext) % 16)
    return _cbc_encrypt(plaintext + bytes([pad]) * pad)


# ── framing ─────────────────────────────────────────────────────────────────

def parse_packet(pkt: bytes) -> dict:
    """Validate one BLE notification and return its fields.

    Raises ProtocolError rather than returning junk: a bad CRC means the packet
    is not trustworthy and must not be fed into reassembly.
    """
    if len(pkt) < HEADER_LEN + TRAILER_LEN:
        raise ProtocolError(f"packet too short ({len(pkt)} bytes)")
    if pkt[:4] != MAGIC:
        raise ProtocolError(f"bad magic {pkt[:4].hex()}")
    length = int.from_bytes(pkt[4:6], "big")
    if length != len(pkt) - 8:
        raise ProtocolError(f"length field {length} != packet {len(pkt)} - 8")
    version = int.from_bytes(pkt[6:8], "big")
    chunk_len = int.from_bytes(pkt[18:20], "big")
    end = HEADER_LEN + chunk_len
    if len(pkt) < end + TRAILER_LEN:
        raise ProtocolError("chunk length overruns packet")
    trailer = int.from_bytes(pkt[end:end + TRAILER_LEN], "big")
    if crc16_modbus(pkt[:end]) != trailer:
        raise ProtocolError("CRC mismatch")
    return {
        "version": version,
        "msg_id": int.from_bytes(pkt[8:10], "big"),
        "total": int.from_bytes(pkt[10:14], "big"),
        "offset": int.from_bytes(pkt[14:18], "big"),
        "chunk_len": chunk_len,
        "ciphertext": pkt[HEADER_LEN:end],
    }


def build_packets(
    plaintext: bytes,
    msg_id: int,
    max_chunk: int = MAX_CHUNK,
    version: int = VERSION,
) -> list[bytes]:
    """Encrypt and frame a JSON command into packets for characteristic ff02.

    `version` is overridable for diagnostics only. Every packet the controller
    sends carries 2, and normal sends match that; the override exists to test
    whether the outbound direction expects a different value.
    """
    ct = encrypt_message(plaintext)
    total = len(ct)
    packets = []
    for off in range(0, total, max_chunk):
        chunk = ct[off:off + max_chunk]
        header = (
            MAGIC
            + (HEADER_LEN - 8 + len(chunk) + TRAILER_LEN).to_bytes(2, "big")
            + (version & 0xFFFF).to_bytes(2, "big")
            + (msg_id & 0xFFFF).to_bytes(2, "big")
            + total.to_bytes(4, "big")
            + off.to_bytes(4, "big")
            + len(chunk).to_bytes(2, "big")
        )
        body = header + chunk
        packets.append(body + crc16_modbus(body).to_bytes(2, "big"))
    return packets


class Reassembler:
    """Collects packet chunks into whole messages.

    The controller interleaves messages, so chunks are keyed by message id. A
    message is only released once every byte between 0 and `total` has arrived.
    """

    def __init__(self, max_messages: int = 8) -> None:
        self._buf: dict[int, dict] = {}
        self._max = max_messages

    def add(self, pkt: bytes) -> Optional[bytes]:
        """Feed one packet. Returns decrypted plaintext when a message completes."""
        info = parse_packet(pkt)
        mid = info["msg_id"]
        entry = self._buf.get(mid)
        if entry is None or entry["total"] != info["total"]:
            entry = {"total": info["total"], "chunks": {}}
            self._buf[mid] = entry
            # Bound memory if a message never completes (lost final chunk).
            while len(self._buf) > self._max:
                self._buf.pop(next(iter(self._buf)))
        entry["chunks"][info["offset"]] = info["ciphertext"]

        got = sum(len(c) for c in entry["chunks"].values())
        if got < entry["total"]:
            return None
        self._buf.pop(mid, None)
        buf = bytearray(entry["total"])
        for off, chunk in entry["chunks"].items():
            buf[off:off + len(chunk)] = chunk
        return decrypt_message(bytes(buf))


# ── self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Known-answer test for the AES core (NIST FIPS-197 AES-128).
    if USING_FALLBACK_AES:
        import sys
        _saved = KEY
        globals()["_RK"] = _expand(bytes.fromhex("000102030405060708090a0b0c0d0e0f"))
        assert _dec_block(bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")).hex() \
            == "00112233445566778899aabbccddeeff"
        assert _enc_block(bytes.fromhex("00112233445566778899aabbccddeeff")).hex() \
            == "69c4e0d86a7b0430d8cdb78070b4c55a"
        globals()["_RK"] = _expand(_saved)
        print("AES core: NIST FIPS-197 vectors PASS (pure-Python fallback)")
    else:
        print("AES core: using `cryptography`")

    cmd = json.dumps({"method": "getDevSta"}, separators=(",", ":")).encode()
    pkts = build_packets(cmd, msg_id=0x1234)
    r = Reassembler()
    out = None
    for p in pkts:
        out = r.add(p) or out
    assert out == cmd, "round-trip failed"
    print(f"round-trip: {len(pkts)} packet(s) OK")
