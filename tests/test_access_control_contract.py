import json
from pathlib import Path

import pytest


CONTRACT_PATH = Path(__file__).parents[1] / "docs" / "security" / "access-control-contract.v1.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.mark.contract
@pytest.mark.security
def test_contract_is_provisional_deny_by_default_and_has_unique_entries(contract):
    assert contract["status"] == "provisional"
    assert contract["deny_by_default"] is True

    actions = contract["critical_actions"]
    action_ids = [action["id"] for action in actions]
    assert len(action_ids) == len(set(action_ids))

    scenarios = contract["test_scenarios"]
    assert len(scenarios) == len(set(scenarios))


@pytest.mark.contract
@pytest.mark.security
def test_every_critical_action_has_an_explicit_role_decision(contract):
    declared_roles = set(contract["roles"])
    allowed_availability = {
        "enabled",
        "denied",
        "disabled_pending_governance",
        "out_of_scope",
    }

    for action in contract["critical_actions"]:
        roles = action["authorized_roles"]
        assert set(roles) <= declared_roles
        assert action["availability"] in allowed_availability
        assert action["requirements"]

        if action["availability"] == "enabled":
            assert roles
            assert action["authorization_mode"] in {"any", "all"}
        elif not roles:
            assert action["authorization_mode"] == "none"


@pytest.mark.contract
@pytest.mark.security
def test_administration_never_implies_clinical_access(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}
    clinical_actions = {
        "institution_clinical_resource.create",
        "institution_clinical_resource.read",
        "institution_clinical_resource.update",
        "institution_clinical_media.upload",
        "institution_clinical_resource.export",
        "institution_clinical_ai.request",
    }

    for action_id in clinical_actions:
        action = actions[action_id]
        assert action["authorized_roles"] == ["institution_member"]
        assert "active_membership" in action["requirements"]
        assert "explicit_resource_assignment" in action["requirements"]

    assert "administration_does_not_imply_clinical_access" in contract["invariants"]


@pytest.mark.contract
@pytest.mark.security
def test_invitation_and_revocation_are_fail_closed(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}

    acceptance = actions["membership.accept_invitation"]
    assert acceptance["authorized_roles"] == ["invited_account"]
    assert {
        "authenticated_identity_matches_invitee",
        "valid_unexpired_invitation",
        "explicit_acceptance",
    } <= set(acceptance["requirements"])

    removal = actions["membership.remove_member"]
    assert {
        "revoke_membership_before_reassigning_work",
        "invalidate_or_revalidate_session",
        "audited_operation",
    } <= set(removal["requirements"])

    invitation_revocation = actions["membership.revoke_invitation"]
    assert "target_invitation_within_grant_scope" in invitation_revocation["requirements"]

    invite_member = actions["membership.invite_member"]
    assert {
        "target_role_is_institution_member",
        "cannot_invite_admin_or_owner",
    } <= set(invite_member["requirements"])

    invite_admin = actions["membership.invite_admin"]
    assert invite_admin["authorized_roles"] == ["institution_owner"]
    assert {
        "target_role_is_institution_access_admin",
        "cannot_invite_owner",
    } <= set(invite_admin["requirements"])

    leave = actions["membership.leave"]
    assert "institution_owner" not in leave["authorized_roles"]
    assert "target_is_self" in leave["requirements"]

    assert "invitation_does_not_grant_data_access" in contract["invariants"]
    assert "revocation_is_checked_server_side_on_every_request" in contract["invariants"]


@pytest.mark.contract
@pytest.mark.security
def test_ownership_cannot_change_silently(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}

    regular_update = actions["technical_ownership.update_as_regular_field"]
    assert regular_update["authorized_roles"] == []
    assert regular_update["availability"] == "denied"

    transfer = actions["technical_ownership.transfer_personal_to_institution"]
    assert transfer["authorization_mode"] == "all"
    assert transfer["availability"] == "disabled_pending_governance"
    assert {"personal_owner", "institution_owner"} == set(transfer["authorized_roles"])
    assert {
        "explicit_two_party_confirmation",
        "enumerated_resource_set",
        "audited_operation",
    } <= set(transfer["requirements"])

    assert "ownership_is_immutable_in_ordinary_updates" in contract["invariants"]
    assert "ownership_transfer_requires_explicit_flow" in contract["invariants"]


@pytest.mark.contract
@pytest.mark.security
def test_institution_owner_transfer_requires_two_distinct_typed_actors(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}
    transfer = actions["institution_owner.transfer"]

    assert transfer["authorization_mode"] == "all"
    assert transfer["required_actors"] == [
        {"actor": "current_owner", "role": "institution_owner"},
        {"actor": "incoming_owner", "role": "institution_access_admin"},
    ]
    assert {
        "authenticated_current_owner",
        "authenticated_incoming_owner",
        "distinct_identities",
        "incoming_owner_has_active_membership",
        "explicit_two_party_confirmation",
    } <= set(transfer["requirements"])


@pytest.mark.contract
@pytest.mark.security
def test_clinical_media_upload_is_scoped_and_validated(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}
    upload = actions["institution_clinical_media.upload"]

    assert upload["authorized_roles"] == ["institution_member"]
    assert {
        "active_membership",
        "explicit_resource_assignment",
        "parent_resource_owner_match",
        "server_generated_storage_path",
        "validated_declared_content_type",
        "validated_actual_content_and_format",
        "validated_size",
    } <= set(upload["requirements"])


@pytest.mark.contract
@pytest.mark.security
def test_out_of_scope_and_pending_sensitive_operations_are_not_enabled(contract):
    actions = {action["id"]: action for action in contract["critical_actions"]}

    assert actions["technical_ownership.transfer_between_institutions"]["availability"] == "out_of_scope"
    assert actions["technical_ownership.transfer_institution_to_personal"]["availability"] == (
        "disabled_pending_governance"
    )
    assert actions["clinical_resource.hard_delete"]["availability"] == "disabled_pending_governance"
    assert actions["institution.audit_metadata.read"]["availability"] == "disabled_pending_governance"
    assert actions["institution.audit_metadata.read"]["authorized_roles"] == []

    assert {
        "scim",
        "definitive_regulatory_rbac",
        "cross_institution_sharing",
    } <= set(contract["scope"]["excluded"])


@pytest.mark.contract
@pytest.mark.security
def test_expected_security_scenarios_are_normative(contract):
    expected_scenarios = {
        "invite_grants_no_access_before_acceptance",
        "expired_replayed_or_wrong_identity_invite_is_denied",
        "access_admin_cannot_invite_admin_or_owner",
        "accepted_member_has_no_clinical_access_without_assignment",
        "admin_without_clinical_assignment_cannot_read_clinical_data",
        "known_resource_id_does_not_bypass_scope",
        "revoked_or_cross_scope_clinical_media_upload_is_denied",
        "revoked_member_is_denied_on_next_request",
        "revocation_does_not_change_resource_owner_or_history",
        "ordinary_update_cannot_change_owner",
        "work_reassignment_does_not_change_owner",
        "personal_to_institution_transfer_stays_disabled",
        "last_owner_cannot_leave_without_explicit_transfer",
        "cross_institution_access_is_denied",
        "account_switch_clears_sensitive_client_state",
    }

    assert set(contract["test_scenarios"]) == expected_scenarios
