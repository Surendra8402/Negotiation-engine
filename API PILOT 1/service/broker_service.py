from lib.errors import BrokerAgreementNotAuthorized

import repository.broker_repository as broker_repository

from service.contract_service import get_contract, sign_contract
from service.user_service import get_signature


def get_agreement(agreement_id, username):
    agreement = broker_repository.get_agreement(agreement_id)
    if username not in (agreement["representant"], agreement["represented"]):
        raise BrokerAgreementNotAuthorized

    return agreement


def get_agreements(username, skip, limit):
    return broker_repository.get_agreements(username, skip, limit)


def get_active_agreements(username, skip, limit):
    return broker_repository.get_active_agreements(username, skip, limit)


def get_pending_agreements(username, skip, limit):
    return broker_repository.get_pending_agreements(username, skip, limit)


def create_agreement(username, representant, represented, end_date, template_id):
    title = "{} ({})".format(representant, represented)
    representant_signature = ""
    represented_signature = ""
    if username == representant:
        representant_signature = get_signature(representant)
    else:
        represented_signature = get_signature(represented)

    contract_id = broker_repository.create_agreement(
        title,
        representant,
        represented,
        end_date,
        template_id,
        representant_signature,
        represented_signature,
    )
    return contract_id


def accept_agreement(agreement_id, username):
    agreement = broker_repository.get_agreement(agreement_id)
    if username not in (agreement["representant"], agreement["represented"]):
        raise BrokerAgreementNotAuthorized

    # Check that the counter-party must accept
    if agreement["representant_signature"] != "" and username == agreement["representant"]:
        raise BrokerAgreementNotAuthorized
    if agreement["represented_signature"] != "" and username == agreement["represented"]:
        raise BrokerAgreementNotAuthorized

    # Get remaining signature
    representant_signature = agreement["representant_signature"]
    if representant_signature == "":
        representant_signature = get_signature(agreement["representant"])

    represented_signature = agreement["represented_signature"]
    if represented_signature == "":
        represented_signature = get_signature(agreement["represented"])

    # Sign contract
    template_id = agreement["template_id"]
    template = get_contract(template_id)
    values = {
        "title": agreement["title"],
        "representant": agreement["representant"],
        "represented": agreement["represented"],
        "start_date": agreement["start_date"],
        "end_date": agreement["end_date"],
        "representant_signature": representant_signature,
        "represented_signature": represented_signature,
    }
    contract = sign_contract(template, values)

    broker_repository.accept_agreement(
        agreement, contract, representant_signature, represented_signature
    )


def reject_agreement(agreement_id, username):
    agreement = broker_repository.get_agreement(agreement_id)
    if agreement["represented"] != username:
        raise BrokerAgreementNotAuthorized

    # Check that the counter-party must reject
    if agreement["representant_signature"] != "" and username == agreement["representant"]:
        raise BrokerAgreementNotAuthorized
    if agreement["represented_signature"] != "" and username == agreement["represented"]:
        raise BrokerAgreementNotAuthorized

    broker_repository.reject_agreement(agreement)
