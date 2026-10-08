#!/usr/bin/env python3
"""
Генерация самоподписанных сертификатов для OPC UA (SignAndEncrypt).

Создаёт:
  ca_cert.pem / ca_key.pem         — корневой CA
  server_cert.pem / server_key.pem — сертификат OPC UA-сервера
  client_cert.pem / client_key.pem — сертификат OPC UA-клиента

Запуск:
  python certs/generate.py

Сертификаты НЕ коммитятся в git (см. .gitignore). В K8s передаются
через Secret (helm/opc-monitor/certs-secrets.yaml).
"""
import datetime
import ipaddress
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


CERT_DIR = Path(__file__).resolve().parent
KEY_SIZE = 2048
CA_DAYS = 3650
LEAF_DAYS = 825  # Apple/Chrome ограничивают срок leaf-сертификатов 825 днями


def _generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    print(f"  ✅ {path.name}")


def _write_cert(path: Path, cert) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  ✅ {path.name}")


def _make_ca():
    key = _generate_key()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OPC Monitor"),
        x509.NameAttribute(NameOID.COMMON_NAME, "OPC Monitor CA"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True, key_cert_sign=True,
                crl_sign=True, content_commitment=False, data_encipherment=False,
                key_agreement=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _write_key(CERT_DIR / "ca_key.pem", key)
    _write_cert(CERT_DIR / "ca_cert.pem", cert)
    return key, cert


def _make_leaf(ca_key, ca_cert, common_name: str, san_dns=None, san_uri=None):
    key = _generate_key()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OPC Monitor"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    san_entries = []
    if san_dns:
        san_entries += [x509.DNSName(d) for d in san_dns]
    if san_uri:
        san_entries.append(x509.UniformResourceIdentifier(san_uri))

    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=LEAF_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
    )
    if san_entries:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(san_entries), critical=False
        )
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def main() -> int:
    print(f"🔐 Генерация сертификатов в {CERT_DIR}")
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] CA")
    ca_key, ca_cert = _make_ca()

    print("\n[2/3] Server")
    srv_key, srv_cert = _make_leaf(
        ca_key, ca_cert,
        common_name="opc-server",
        san_dns=["server", "localhost"],
        san_uri="urn:opc-monitor:server",
    )
    _write_key(CERT_DIR / "server_key.pem", srv_key)
    _write_cert(CERT_DIR / "server_cert.pem", srv_cert)

    print("\n[3/3] Client")
    cli_key, cli_cert = _make_leaf(
        ca_key, ca_cert,
        common_name="opc-client",
        san_uri="urn:opc-monitor:client",
    )
    _write_key(CERT_DIR / "client_key.pem", cli_key)
    _write_cert(CERT_DIR / "client_cert.pem", cli_cert)

    print("\n✅ Готово. Не коммитьте эти файлы в git!")
    return 0


if __name__ == "__main__":
    sys.exit(main())