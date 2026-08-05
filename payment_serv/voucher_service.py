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
        'Authorization': f'******',
        'Content-Type': 'application/json',
    }


def _classify_failure(status_code: int, payload: Optional[dict]) -> VoucherVerificationResult:
    raw_message = ''
    if isinstance(payload, dict):
        raw_message = str(payload.get('message') or payload.get('detail') or payload.get('error') or '')
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


def verify_voucher(voucher_code: str, postcode: str) -> VoucherVerificationResult:
    """Verify an RNFL voucher."""
    try:
        response = requests.post(
            f"{RNFL_API_URL.rstrip('/')}/api/supplier/vouchers/verify",
            headers=_headers(),
            json={
                'voucher_code': voucher_code,
                'postcode': postcode,
            },
            timeout=10,
        )
    except requests.RequestException as e:
        logger.error(f'verify_voucher(): RNFL request failed: {str(e)}')
        raise VoucherServiceError('Voucher service is currently unavailable. Please try again later.') from e

    if response.status_code == 200:
        return VoucherVerificationResult(
            eligible=True,
            message='Voucher verified successfully.',
            code=voucher_code,
            discount_code=get_discount_code('RNFL'),
            voucher_type='RNFL',
        )

    payload = response.json() if response.content else None
    raise VoucherVerificationFailed(_classify_failure(response.status_code, payload))


def redeem_voucher(voucher_code: str, postcode: str, amount: str, supplier_reference: str, surname: Optional[str] = None) -> None:
    """Redeem an RNFL voucher after successful checkout."""
    payload = {
        'voucher_code': voucher_code,
        'amount': amount,
        'postcode': postcode,
        'supplier_reference': supplier_reference,
    }
    if surname:
        payload['surname'] = surname

    try:
        response = requests.post(
            f"{RNFL_API_URL.rstrip('/')}/api/supplier/vouchers/redeem",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f'redeem_voucher(): RNFL redeem failed for {voucher_code}: {str(e)}')
        raise VoucherServiceError('Voucher redeem failed') from e
