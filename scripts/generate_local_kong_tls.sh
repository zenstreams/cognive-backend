#!/usr/bin/env bash
set -euo pipefail

# Generates a self-signed TLS cert for local Kong HTTPS.
# Output location is gitignored (see .gitignore).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${ROOT_DIR}/.local/kong-certs"
CERT_FILE="${CERT_DIR}/localhost.crt"
KEY_FILE="${CERT_DIR}/localhost.key"

mkdir -p "${CERT_DIR}"

if [[ -f "${CERT_FILE}" && -f "${KEY_FILE}" ]]; then
  echo "[kong-tls] Found existing certs at ${CERT_DIR}"
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "[kong-tls] ERROR: openssl not found. Install openssl and retry."
  exit 1
fi

TMP_CFG="$(mktemp)"
trap 'rm -f "${TMP_CFG}"' EXIT

cat > "${TMP_CFG}" <<'EOF'
[req]
default_bits = 2048
distinguished_name = req_distinguished_name
prompt = no
x509_extensions = v3_req

[req_distinguished_name]
CN = localhost

[v3_req]
subjectAltName = @alt_names
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

echo "[kong-tls] Generating self-signed cert for localhost..."
openssl req -x509 -nodes -newkey rsa:2048 \
  -days 3650 \
  -keyout "${KEY_FILE}" \
  -out "${CERT_FILE}" \
  -config "${TMP_CFG}"

chmod 600 "${KEY_FILE}"
echo "[kong-tls] Generated:"
echo "  - ${CERT_FILE}"
echo "  - ${KEY_FILE}"


