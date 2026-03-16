from __future__ import annotations

from datetime import date

import pytest

from core.domain.client import Client, _clear_clients, create_client
from core.domain.payroll_run import PayrollRun, _clear_runs, create_payroll_run, get_previous_run


@pytest.fixture(autouse=True)
def clear_stores():
    _clear_clients()
    _clear_runs()
    yield
    _clear_clients()
    _clear_runs()


# ---------------------------------------------------------------------------
# Create client
# ---------------------------------------------------------------------------


class TestCreateClient:
    def test_returns_client_instance(self):
        client = create_client("C001", "Acme Corp", "monthly", "IE")
        assert isinstance(client, Client)

    def test_fields_set_correctly(self):
        client = create_client("C001", "Acme Corp", "monthly", "IE")
        assert client.client_id == "C001"
        assert client.client_name == "Acme Corp"
        assert client.payroll_frequency == "monthly"
        assert client.jurisdiction == "IE"

    def test_multiple_clients_stored_independently(self):
        c1 = create_client("C001", "Acme Corp", "monthly", "IE")
        c2 = create_client("C002", "Beta Ltd", "weekly", "UK")
        assert c1.client_id != c2.client_id
        assert c1.payroll_frequency != c2.payroll_frequency

    def test_create_client_returns_same_data_on_overwrite(self):
        create_client("C001", "Old Name", "monthly", "IE")
        updated = create_client("C001", "New Name", "weekly", "IE")
        assert updated.client_name == "New Name"
        assert updated.payroll_frequency == "weekly"


# ---------------------------------------------------------------------------
# Store payroll run
# ---------------------------------------------------------------------------


class TestStorePayrollRun:
    def test_returns_payroll_run_instance(self):
        run = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "abc123", [])
        assert isinstance(run, PayrollRun)

    def test_fields_set_correctly(self):
        run = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "abc123", [])
        assert run.client_id == "C001"
        assert run.period_start == date(2024, 1, 1)
        assert run.period_end == date(2024, 1, 31)
        assert run.dataset_hash == "abc123"
        assert run.normalized_rows == []

    def test_run_id_auto_generated(self):
        run = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        assert run.run_id is not None
        assert len(run.run_id) > 0

    def test_run_id_unique_per_run(self):
        r1 = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        r2 = create_payroll_run("C001", date(2024, 2, 1), date(2024, 2, 29), "h2", [])
        assert r1.run_id != r2.run_id

    def test_created_at_set_automatically(self):
        run = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        assert run.created_at is not None


# ---------------------------------------------------------------------------
# Retrieve previous run
# ---------------------------------------------------------------------------


class TestRetrievePreviousRun:
    def test_no_runs_returns_none(self):
        assert get_previous_run("C001") is None

    def test_single_run_returned(self):
        run = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        result = get_previous_run("C001")
        assert result is not None
        assert result.run_id == run.run_id

    def test_returns_most_recent_run_by_period_end(self):
        r1 = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        r2 = create_payroll_run("C001", date(2024, 2, 1), date(2024, 2, 29), "h2", [])
        result = get_previous_run("C001")
        assert result.run_id == r2.run_id

    def test_three_runs_returns_latest(self):
        r1 = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        r2 = create_payroll_run("C001", date(2024, 2, 1), date(2024, 2, 29), "h2", [])
        r3 = create_payroll_run("C001", date(2024, 3, 1), date(2024, 3, 31), "h3", [])
        result = get_previous_run("C001")
        assert result.run_id == r3.run_id


# ---------------------------------------------------------------------------
# Multiple clients isolation
# ---------------------------------------------------------------------------


class TestMultipleClientsIsolation:
    def test_runs_scoped_to_client(self):
        r_c1 = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        r_c2 = create_payroll_run("C002", date(2024, 1, 1), date(2024, 1, 31), "h2", [])

        assert get_previous_run("C001").run_id == r_c1.run_id
        assert get_previous_run("C002").run_id == r_c2.run_id

    def test_unknown_client_returns_none(self):
        create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        assert get_previous_run("C999") is None

    def test_many_runs_for_client_a_do_not_affect_client_b(self):
        for month in range(1, 4):
            create_payroll_run("C001", date(2024, month, 1), date(2024, month, 28), f"h{month}", [])
        r_b = create_payroll_run("C002", date(2024, 6, 1), date(2024, 6, 30), "hb", [])

        result = get_previous_run("C002")
        assert result.run_id == r_b.run_id
        assert result.client_id == "C002"

    def test_client_ids_are_independent(self):
        create_client("C001", "Acme", "monthly", "IE")
        create_client("C002", "Beta", "weekly", "UK")

        r1 = create_payroll_run("C001", date(2024, 3, 1), date(2024, 3, 31), "h1", [])
        r2 = create_payroll_run("C002", date(2024, 3, 1), date(2024, 3, 31), "h2", [])

        assert get_previous_run("C001").run_id == r1.run_id
        assert get_previous_run("C002").run_id == r2.run_id


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_insertion_order_does_not_affect_result(self):
        # Insert in reverse chronological order
        r3 = create_payroll_run("C001", date(2024, 3, 1), date(2024, 3, 31), "h3", [])
        r1 = create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        r2 = create_payroll_run("C001", date(2024, 2, 1), date(2024, 2, 29), "h2", [])

        result = get_previous_run("C001")
        assert result.run_id == r3.run_id

    def test_repeated_calls_return_same_run(self):
        create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "h1", [])
        create_payroll_run("C001", date(2024, 2, 1), date(2024, 2, 29), "h2", [])

        calls = [get_previous_run("C001") for _ in range(5)]
        run_ids = [r.run_id for r in calls]
        assert len(set(run_ids)) == 1, "repeated calls must return the same run_id"

    def test_latest_period_end_wins_over_insertion_order(self):
        # Add the later period first, earlier period second — result must still be the later period
        r_later = create_payroll_run("C001", date(2024, 12, 1), date(2024, 12, 31), "hDec", [])
        create_payroll_run("C001", date(2024, 1, 1), date(2024, 1, 31), "hJan", [])

        result = get_previous_run("C001")
        assert result.run_id == r_later.run_id
