from eth_account import Account
from eth_account.messages import encode_defunct


def register_and_login(client, email: str):
    password = "MemberPass123!"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password, "display_name": "Wallet User"}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def link(client, headers, account):
    challenge = client.post("/api/v1/wallet/challenge", headers=headers, json={"address": account.address})
    assert challenge.status_code == 200
    signature = Account.sign_message(encode_defunct(text=challenge.json()["message"]), account.key).signature.hex()
    return client.post("/api/v1/wallet/link", headers=headers, json={"address": account.address, "signature": signature})


def test_wallet_is_bound_by_signature_and_unique(client):
    first = register_and_login(client, "wallet-one@example.com")
    second = register_and_login(client, "wallet-two@example.com")
    account = Account.create()

    linked = link(client, first, account)
    assert linked.status_code == 200
    assert linked.json()["wallet_address"] == account.address

    duplicate = link(client, second, account)
    assert duplicate.status_code == 409


def test_invalid_wallet_signature_is_rejected(client):
    headers = register_and_login(client, "wallet-invalid@example.com")
    claimed, signer = Account.create(), Account.create()
    challenge = client.post("/api/v1/wallet/challenge", headers=headers, json={"address": claimed.address}).json()
    signature = Account.sign_message(encode_defunct(text=challenge["message"]), signer.key).signature.hex()
    response = client.post("/api/v1/wallet/link", headers=headers, json={"address": claimed.address, "signature": signature})
    assert response.status_code == 403
