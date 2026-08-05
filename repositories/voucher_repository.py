import logging
from typing import Optional

from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_voucher(subscription_id: str, code: str, postcode: str, status: str, voucher_type: str = 'RNFL') -> dict:
    """Insert a voucher record."""
    response = supabase.table('vouchers').insert({
        'subscription_id': subscription_id,
        'type': voucher_type,
        'code': code,
        'postcode': postcode,
        'status': status,
    }).execute()
    return response.data[0] if response.data else None


def get_voucher_by_subscription_id(subscription_id: str) -> Optional[dict]:
    """Fetch voucher by subscription id."""
    response = supabase.table('vouchers').select('*').eq('subscription_id', subscription_id).execute()
    return response.data[0] if response.data else None


def update_voucher_status(code: str, status: str) -> Optional[dict]:
    """Update voucher status by code."""
    response = supabase.table('vouchers').update({'status': status}).eq('code', code).execute()
    return response.data[0] if response.data else None
