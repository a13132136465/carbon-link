from urllib.parse import quote


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
    upload_required(client, seller, project_id)
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
    assert dashboard["open_market_quantity"] == "15.0000"
    assert dashboard["trade_volume"] == "25.0000"
    assert dashboard["latest_market_listings"][0]["id"] == listing.json()["id"]
    chain_config = client.get("/api/v1/system/blockchain", headers=admin)
    assert chain_config.status_code == 200
    assert chain_config.json()["enabled"] is False
    assert "private_key" not in chain_config.text
    operations = client.get("/api/v1/system/blockchain/operations", headers=admin)
    assert operations.status_code == 200
    assert operations.json() == []
    assert len(client.get("/api/v1/market/trades", headers=buyer).json()) == 1
    assert len(client.get("/api/v1/retirements", headers=buyer).json()) == 1
    assert len(client.get("/api/v1/wallet/ledger", headers=buyer).json()) == 2
    audit_events = client.get("/api/v1/system/audit-events", headers=admin)
    assert audit_events.status_code == 200
    assert any(event["action"] == "trade.settled" for event in audit_events.json())

def test_cannot_list_or_retire_more_than_available(client):
    register(client, "empty@example.com")
    user = login(client, "empty@example.com")
    response = client.post("/api/v1/market/listings", headers=user, json={"batch_id": "missing", "quantity": "1", "unit_price": "1", "currency": "CNY"})
    assert response.status_code == 404

def test_project_edit_delete_and_pagination(client):
    register(client, "editor@example.com")
    user = login(client, "editor@example.com")
    body = {"name": "Draft project", "project_type": "forestry", "region": "Guangxi", "methodology": "AR-001", "description": "draft", "estimated_tonnes": "12.5"}
    created = client.post("/api/v1/projects", headers=user, json=body)
    project_id = created.json()["id"]
    body["name"] = "Updated project"
    updated = client.put(f"/api/v1/projects/{project_id}", headers=user, json=body)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated project"
    page = client.get("/api/v1/projects?limit=1", headers=user)
    assert page.headers["X-Total-Count"] == "1"
    assert client.delete(f"/api/v1/projects/{project_id}", headers=user).status_code == 204

def test_account_recovery_and_admin_role_management(client, monkeypatch):
    delivered = []
    monkeypatch.setattr("app.api.send_password_reset", lambda email, token: delivered.append(token))
    register(client, "account@example.com")
    admin = login(client, "admin@example.com", "AdminPassword123!")
    users = client.get("/api/v1/users", headers=admin)
    target = next(user for user in users.json() if user["email"] == "account@example.com")
    changed = client.put(f"/api/v1/users/{target['id']}", headers=admin, json={"role": "verifier"})
    assert changed.status_code == 200
    assert changed.json()["role"] == "verifier"
    forgot = client.post("/api/v1/auth/password/forgot", json={"email": "account@example.com"})
    assert "reset_token" not in forgot.json()
    token = delivered[0]
    assert token
    reset = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "NewPassword123!"})
    assert reset.status_code == 200
    assert login(client, "account@example.com", "NewPassword123!")

def test_enterprise_application_materials_and_agent(client):
    register(client, "applicant@example.com")
    user = login(client, "applicant@example.com")
    created = client.post("/api/v1/projects", headers=user, json={"name":"智能申报示范项目","project_type":"energy_efficiency","region":"深圳","methodology":"CM-002","description":"园区节能改造","estimated_tonnes":"500"})
    project_id = created.json()["id"]
    readiness = client.get(f"/api/v1/applications/{project_id}/readiness", headers=user).json()
    assert readiness["completion_percent"] == 0
    assert client.post(f"/api/v1/applications/{project_id}/submit", headers=user).status_code == 409
    for category in ("project_design", "ownership", "methodology", "monitoring"):
        original_name = "项目设计文件.pdf" if category == "project_design" else f"{category}.pdf"
        uploaded = client.post(
            f"/api/v1/projects/{project_id}/documents?category={category}",
            headers={**user, "Content-Type":"application/pdf", "X-File-Name":quote(original_name)},
            content=b"%PDF-1.4 test document",
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["original_name"] == original_name
    ready = client.get(f"/api/v1/applications/{project_id}/readiness", headers=user).json()
    assert ready == {"ready": True, "completed_categories":["project_design","ownership","methodology","monitoring"], "missing_categories":[], "completion_percent":100}
    agent = client.post("/api/v1/application-agent/message", headers=user, json={"project_id":project_id,"message":"下一步做什么？"})
    assert agent.status_code == 200
    assert agent.json()["stage"] == "ready_to_submit"
    submitted = client.post(f"/api/v1/applications/{project_id}/submit", headers=user)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending"


def upload_required(client, headers, project_id):
    from app.application_agent import REQUIRED_DOCUMENTS
    for category in REQUIRED_DOCUMENTS:
        result = client.post(f"/api/v1/projects/{project_id}/documents?category={category}",
            headers={**headers, "Content-Type": "application/pdf", "X-File-Name": "test.pdf"}, content=b"%PDF-test")
        assert result.status_code == 201, result.text
