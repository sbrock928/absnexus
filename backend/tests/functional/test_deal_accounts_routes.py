"""Functional tests for deal-account CRUD + period-preview endpoints."""


def test_list_accounts_empty(admin_client, test_deal):
    r = admin_client.get(f"/api/deals/{test_deal.id}/accounts")
    assert r.status_code == 200
    assert r.json() == []


def test_create_account(admin_client, test_deal):
    r = admin_client.post(
        f"/api/deals/{test_deal.id}/accounts",
        json={"label": "Main", "account_number": "92994800", "position": 1},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["label"] == "Main"
    assert data["account_number"] == "92994800"
    assert data["position"] == 1
    assert data["deal_id"] == test_deal.id


def test_create_account_deal_not_found(admin_client):
    r = admin_client.post(
        "/api/deals/9999/accounts",
        json={"label": "Main", "account_number": "1"},
    )
    assert r.status_code == 404


def test_list_accounts_sorted_by_position(admin_client, test_deal):
    for pos, label in [(3, "Reserve"), (1, "Main"), (2, "Collection")]:
        admin_client.post(
            f"/api/deals/{test_deal.id}/accounts",
            json={"label": label, "account_number": f"1000{pos}", "position": pos},
        )
    r = admin_client.get(f"/api/deals/{test_deal.id}/accounts")
    labels = [a["label"] for a in r.json()]
    assert labels == ["Main", "Collection", "Reserve"]


def test_update_account(admin_client, test_deal):
    c = admin_client.post(
        f"/api/deals/{test_deal.id}/accounts",
        json={"label": "Main", "account_number": "1"},
    ).json()
    r = admin_client.patch(
        f"/api/deals/{test_deal.id}/accounts/{c['id']}",
        json={"account_number": "92994800"},
    )
    assert r.status_code == 200
    assert r.json()["account_number"] == "92994800"
    assert r.json()["label"] == "Main"  # unchanged


def test_update_account_404(admin_client, test_deal):
    r = admin_client.patch(
        f"/api/deals/{test_deal.id}/accounts/9999",
        json={"label": "X"},
    )
    assert r.status_code == 404


def test_update_account_wrong_deal_404(admin_client, test_deal, db, test_servicer):
    from app.models.deal import Deal

    other = Deal(name="OTHER", servicer_id=test_servicer.id, created_by="t")
    db.add(other)
    db.flush()
    c = admin_client.post(
        f"/api/deals/{other.id}/accounts",
        json={"label": "Main", "account_number": "1"},
    ).json()
    # Try to update via wrong deal_id
    r = admin_client.patch(
        f"/api/deals/{test_deal.id}/accounts/{c['id']}",
        json={"label": "Renamed"},
    )
    assert r.status_code == 404


def test_delete_account(admin_client, test_deal):
    c = admin_client.post(
        f"/api/deals/{test_deal.id}/accounts",
        json={"label": "Main", "account_number": "1"},
    ).json()
    r = admin_client.delete(f"/api/deals/{test_deal.id}/accounts/{c['id']}")
    assert r.status_code == 204
    r2 = admin_client.get(f"/api/deals/{test_deal.id}/accounts")
    assert r2.json() == []


def test_delete_account_404(admin_client, test_deal):
    r = admin_client.delete(f"/api/deals/{test_deal.id}/accounts/9999")
    assert r.status_code == 404


def test_analyst_cannot_write_accounts(analyst_client, test_deal):
    r = analyst_client.post(
        f"/api/deals/{test_deal.id}/accounts",
        json={"label": "X", "account_number": "1"},
    )
    assert r.status_code == 403


# ── Static deal-field updates via PATCH /deals/{id} ──


def test_patch_deal_accepts_static_fields(admin_client, test_deal):
    r = admin_client.patch(
        f"/api/deals/{test_deal.id}",
        json={
            "issuer_name": "American Credit Acceptance Receivables Trust 2025-4",
            "deal_key": "ACA254",
            "reg_ab": False,
            "equity_cusips_involved": True,
            "closing_date": "2025-10-16",
            "initial_cutoff_date": "2025-10-07",
            "initial_distribution_date": "2025-12-12",
            "cutoff_pool_balance": "455000312.51",
            "distribution_day_of_month": 12,
            "determination_business_days_before": 4,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["deal_key"] == "ACA254"
    assert data["distribution_day_of_month"] == 12
    assert data["determination_business_days_before"] == 4
    assert data["closing_date"] == "2025-10-16"
    assert data["equity_cusips_involved"] is True


# ── Period preview ──


def test_period_preview(admin_client, test_deal):
    admin_client.patch(
        f"/api/deals/{test_deal.id}",
        json={
            "distribution_day_of_month": 12,
            "determination_business_days_before": 4,
            "initial_cutoff_date": "2025-10-07",
        },
    )
    r = admin_client.get(f"/api/deals/{test_deal.id}/period-preview?period=2025-12")
    assert r.status_code == 200
    data = r.json()
    assert data["distribution_date"] == "2025-12-12"  # Fri, no bump
    assert data["determination_date"] == "2025-12-08"  # 4 biz days before Fri Dec 12
    # Day-count anchor is now the previous-month computed distribution date
    # (2025-11-12), which is the common recurring-cadence case.
    assert data["anchor_date"] == "2025-11-12"
    assert data["anchor_source"] == "prior_month_computed"
    assert data["days_in_period_actual"] == 30
    assert data["days_in_period_30_360"] == 30


def test_period_preview_missing_deal(admin_client):
    r = admin_client.get("/api/deals/9999/period-preview?period=2025-12")
    assert r.status_code == 404


def test_period_preview_no_config(admin_client, test_deal):
    """Deal with no distribution config returns nulls, not an error."""
    r = admin_client.get(f"/api/deals/{test_deal.id}/period-preview?period=2025-12")
    assert r.status_code == 200
    data = r.json()
    assert data["distribution_date"] is None
    assert data["determination_date"] is None
