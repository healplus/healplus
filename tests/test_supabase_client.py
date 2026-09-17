from unittest.mock import Mock

import pytest
import requests

from backend.supabase_client import SupabaseAuth, SupabaseClient, SupabaseUnavailable, is_supabase_ready


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "synthetic-public-key")


def response(payload, status=200):
    return Mock(status_code=status, content=b"json", json=Mock(return_value=payload))


def test_auth_validates_token_and_session_and_ignores_editable_permissions(monkeypatch):
    http = Mock(side_effect=[response({
        "id": "user-a", "email": "a@example.test",
        "app_metadata": {"roles": ["nurse"], "unit_ids": ["unit-a"]},
        "user_metadata": {"roles": ["admin"], "unit_ids": ["unit-b"], "uid": "user-b"},
    }), response(True)])
    monkeypatch.setattr(requests, "request", http)
    user = SupabaseAuth().verify_id_token("synthetic-jwt")
    assert user == {"uid": "user-a", "sub": "user-a", "email": "a@example.test", "roles": ["nurse"], "unit_ids": ["unit-a"]}
    assert http.call_args_list[0].args == ("GET", "https://synthetic.supabase.co/auth/v1/user")
    assert http.call_args_list[1].args[1].endswith("/rpc/current_session_is_active")
    assert http.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer synthetic-jwt"
    assert http.call_args_list[0].kwargs["allow_redirects"] is False


@pytest.mark.parametrize("active", [False, None, [], {"active": True}])
def test_revoked_or_unverifiable_session_fails_closed(monkeypatch, active):
    monkeypatch.setattr(requests, "request", Mock(side_effect=[response({"id": "a"}), response(active)]))
    with pytest.raises(SupabaseUnavailable):
        SupabaseAuth().verify_id_token("synthetic-jwt")


@pytest.mark.parametrize("status", [301, 401, 403, 500])
def test_upstream_errors_do_not_expose_secrets(monkeypatch, status):
    monkeypatch.setattr(requests, "request", Mock(return_value=response({"error": "sensitive-marker"}, status)))
    with pytest.raises(SupabaseUnavailable, match="^Supabase request failed$"):
        SupabaseClient("synthetic-jwt").select("patients")


def test_timeout_does_not_expose_request(monkeypatch):
    monkeypatch.setattr(requests, "request", Mock(side_effect=requests.Timeout("sensitive-marker")))
    with pytest.raises(SupabaseUnavailable, match="^Supabase request failed$"):
        SupabaseClient("synthetic-jwt").select("patients")


def test_configuration_missing_or_insecure_fails_closed(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://external.example.test")
    assert not is_supabase_ready()
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    assert is_supabase_ready()
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert not is_supabase_ready()


def test_logout_revokes_callers_sessions(monkeypatch):
    from flask import Flask
    http = Mock(side_effect=[response({"id": "a"}), response(None, 204)])
    monkeypatch.setattr(requests, "request", http)
    with Flask(__name__).test_request_context(headers={"Authorization": "Bearer synthetic-jwt"}):
        SupabaseAuth().revoke_refresh_tokens("a")
    assert http.call_args.args[1].endswith("/auth/v1/logout")
    assert http.call_args.kwargs["params"] == {"scope": "global"}


def test_logout_cannot_revoke_another_user(monkeypatch):
    from flask import Flask
    http = Mock(return_value=response({"id": "a"}))
    monkeypatch.setattr(requests, "request", http)
    with Flask(__name__).test_request_context(headers={"Authorization": "Bearer synthetic-jwt"}):
        with pytest.raises(SupabaseUnavailable):
            SupabaseAuth().revoke_refresh_tokens("b")
    assert http.call_count == 1
