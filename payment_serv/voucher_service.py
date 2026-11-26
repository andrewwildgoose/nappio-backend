import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

from models.payment_models import VoucherVerificationResult

logger = logging.getLogger('uvicorn.error')

load_dotenv()

RNFL_API_URL = os.environ.get('RNFL_API_URL')
RNFL_BEARER_TOKEN = os.environ.get('RNFL_BEARER_TOKEN')
RNFL_DEFAULT_COUPON = os.environ.get('RNFL_40_STRIPE_ID')


class VoucherServiceError(Exception):
    """Raised for voucher service integration failures."""


class VoucherVerificationFailed(Exception):
    """Raised when a voucher cannot be verified."""

    def __init__(self, result: VoucherVerificationResult):
        super().__init__(result.message)
        self.result = result


def get_discount_code(voucher_type: str = 'RNFL') -> str:
    """Resolve the Stripe coupon id for a voucher type."""
    if voucher_type == 'RNFL' and RNFL_DEFAULT_COUPON:
        return RNFL_DEFAULT_COUPON
    raise VoucherServiceError(f'No configured Stripe coupon for voucher type {voucher_type}')


def _headers() -> dict:
    if not RNFL_API_URL or not RNFL_BEARER_TOKEN:
        raise VoucherServiceError('RNFL voucher configuration is missing')
    return {
        'Authorization': 'Bearer ' + RNFL_BEARER_TOKEN,
        'Content-Type': 'application/json',
    }


def _base_url() -> str:
    if not RNFL_API_URL:
        raise VoucherServiceError('RNFL voucher configuration is missing')
    return RNFL_API_URL.rstrip('/')


def _classify_failure(status_code: int, payload: Optional[dict]) -> VoucherVerificationResult:
    payload = payload or {}

    raw_message = ''
    if isinstance(payload, dict):
        error_details = payload.get('error')
        if isinstance(error_details, dict):
            raw_message = str(
                error_details.get('message')
                or error_details.get('detail')
                or error_details.get('error')
                or payload.get('message')
                or payload.get('detail')
                or ''
            )
        else:
            raw_message = str(
                payload.get('message')
                or payload.get('detail')
                or error_details
                or ''
            )
    normalized = raw_message.lower()

    if status_code == 404 or 'not found' in normalized or 'does not exist' in normalized:
        return VoucherVerificationResult(eligible=False, message='Voucher code not recognised.', failure_reason='not_found')
    if 'used' in normalized or 'redeemed' in normalized or 'already' in normalized:
        return VoucherVerificationResult(eligible=False, message='This voucher has already been used.', failure_reason='already_used')
    if 'postcode' in normalized or 'match' in normalized:
        return VoucherVerificationResult(
            eligible=False,
            message='Voucher details did not match the provided postcode.',
            failure_reason='postcode_mismatch'
        )
    if 'unavailable' in normalized or 'expired' in normalized:
        return VoucherVerificationResult(eligible=False, message='This voucher is no longer available.', failure_reason='unavailable')
    if status_code >= 500:
        return VoucherVerificationResult(
            eligible=False,
            message='Voucher service is currently unavailable. Please try again later.',
            failure_reason='service_error'
        )
    return VoucherVerificationResult(
        eligible=False,
        message='We could not verify that voucher. Please check the code and postcode.',
        failure_reason='unavailable'
    )


def _parse_error_payload(response: requests.Response) -> Optional[dict]:
    if not response.content:
        return {}

    try:
        payload = response.json()
    except ValueError:
        fallback_text = response.text.strip() if response.text else 'Voucher service returned an invalid response.'
        logger.warning(
            'verify_voucher(): RNFL returned non-JSON response. status=%s body=%s',
            response.status_code,
            fallback_text[:500],
        )
        return {'message': fallback_text}

    if isinstance(payload, dict):
        return payload
    if payload is None:
        return {}
    return {'message': str(payload)}


def verify_voucher(voucher_code: str, postcode: str) -> VoucherVerificationResult:
    """Verify an RNFL voucher."""
    try:
        headers = _headers()
        response = requests.post(
            f"{_base_url()}/vouchers/verify",
            headers=headers,
            json={
                'voucher_code': voucher_code,
                'postcode': postcode,
            },
            timeout=10,
        )

        logger.debug(f'verify_voucher(): response: {response.status_code} {response.text[:500]}')
    except requests.RequestException as e:
        logger.error(f'verify_voucher(): RNFL request failed: {str(e)}')
        raise VoucherServiceError('Voucher service is currently unavailable. Please try again later.') from e

    if response.status_code == 200:
        return VoucherVerificationResult(
            eligible=True,
            message='Voucher verified successfully.',
            code=voucher_code,
            postcode=postcode,
            discount_code=get_discount_code('RNFL'),
            voucher_type='RNFL',
        )

    payload = _parse_error_payload(response)
    raise VoucherVerificationFailed(_classify_failure(response.status_code, payload))


def redeem_voucher(
    voucher_code: str,
    postcode: str,
    amount_gbp: str,
    supplier_reference: str,
    surname: Optional[str] = None
) -> None:
    """Redeem an RNFL voucher after successful checkout using a GBP string like '70.00'."""
    payload = {
        'voucher_code': voucher_code,
        'amount': amount_gbp,
        'postcode': postcode,
        'supplier_reference': supplier_reference,
    }
    if surname:
        payload['surname'] = surname

    try:
        headers = _headers()
        response = requests.post(
            f"{_base_url()}/api/supplier/vouchers/redeem",
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f'redeem_voucher(): RNFL redeem failed for {voucher_code}: {str(e)}')
        raise VoucherServiceError('Voucher redeem failed') from e
