def register(client, email):
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "MemberPass123!", "display_name": email.split("@")[0]})
    assert response.status_code == 201, response.text

def login(client, email, password="MemberPass123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_full_registry_market_and_retirement_workflow(client):
    register(client, "seller@example.com")
    register(client, "buyer@example.com")
    seller = login(client, "seller@example.com")
    buyer = login(client, "buyer@example.com")
    admin = login(client, "admin@example.com", "AdminPassword123!")

    created = client.post("/api/v1/projects", headers=seller, json={"name": "华南光伏一期", "project_type": "renewable_energy", "region": "广东", "methodology": "CM-001-V01", "description": "50MW 分布式光伏", "estimated_tonnes": "1000.0000"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert client.post(f"/api/v1/projects/{project_id}/submit", headers=seller).status_code == 200
    reviewed = client.post(f"/api/v1/projects/{project_id}/review", headers=admin, json={"approved": True, "note": "核证材料完整"})
    assert reviewed.json()["status"] == "approved"

    issued = client.post("/api/v1/credits/issue", headers={**admin, "Idempotency-Key": "issue-001"}, json={"project_id": project_id, "vintage": 2026, "quantity": "100.0000"})
    assert issued.status_code == 201, issued.text
    batch_id = issued.json()["id"]
    duplicate = client.post("/api/v1/credits/issue", headers={**admin, "Idempotency-Key": "issue-001"}, json={"project_id": project_id, "vintage": 2026, "quantity": "100.0000"})
    assert duplicate.status_code == 409

    listing = client.post("/api/v1/market/listings", headers=seller, json={"batch_id": batch_id, "quantity": "40.0000", "unit_price": "68.50", "currency": "CNY"})
    assert listing.status_code == 201, listing.text
    trade = client.post(f"/api/v1/market/listings/{listing.json()['id']}/buy", headers={**buyer, "Idempotency-Key": "buy-001"}, json={"quantity": "25.0000"})
    assert trade.status_code == 201, trade.text
    assert trade.json()["total_amount"] == "1712.50"

    retired = client.post("/api/v1/retirements", headers={**buyer, "Idempotency-Key": "retire-001"}, json={"batch_id": batch_id, "quantity": "10.0000", "beneficiary": "示例制造有限公司", "reason": "2026 年运营排放抵消"})
    assert retired.status_code == 201, retired.text
    certificate = client.get(f"/api/v1/retirements/{retired.json()['certificate_no']}")
    assert certificate.status_code == 200
    assert certificate.json()["quantity"] == "10.0000"

    seller_holding = client.get("/api/v1/wallet/holdings", headers=seller).json()[0]
    buyer_holding = client.get("/api/v1/wallet/holdings", headers=buyer).json()[0]
    assert seller_holding["quantity"] == "75.0000"
    assert seller_holding["locked_quantity"] == "15.0000"
    assert buyer_holding["quantity"] == "15.0000"
    dashboard = client.get("/api/v1/dashboard", headers=admin).json()
    assert dashboard["total_issued"] == "100.0000"
    assert dashboard["total_retired"] == "10.0000"
    chain_config = client.get("/api/v1/system/blockchain", headers=admin)
    assert chain_config.status_code == 200
    assert chain_config.json()["enabled"] is False
    assert "private_key" not in chain_config.text
    operations = client.get("/api/v1/system/blockchain/operations", headers=admin)
    assert operations.status_code == 200
    assert operations.json() == []

def test_cannot_list_or_retire_more_than_available(client):
    register(client, "empty@example.com")
    user = login(client, "empty@example.com")
    response = client.post("/api/v1/market/listings", headers=user, json={"batch_id": "missing", "quantity": "1", "unit_price": "1", "currency": "CNY"})
    assert response.status_code == 404
