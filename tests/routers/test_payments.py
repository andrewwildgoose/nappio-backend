"""
Tests for the payments router.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


MOCK_USER = MagicMock()
MOCK_USER.id = "user-123"
MOCK_USER.email = "user@example.com"


def _make_app():
    """Build a minimal FastAPI app with only the payments router."""
    from fastapi import FastAPI
    from api.routers.payments import router
    from api.dependencies.auth import get_authenticated_user
    app = FastAPI()
    app.dependency_overrides[get_authenticated_user] = lambda: MOCK_USER
    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


def voucher_error(reason, message):
    from models.payment_models import VoucherVerificationResult
    from payment_serv.voucher_service import VoucherVerificationFailed
    return VoucherVerificationFailed(VoucherVerificationResult(eligible=False, message=message, failure_reason=reason))


class TestVerifyVoucher:
    def test_verify_voucher_success(self, client):
        mock_result = {
            'eligible': True,
            'message': 'Voucher verified successfully.',
            'code': 'RNF1 23AB CD4E',
            'discount_code': 'coupon_123',
            'voucher_type': 'RNFL',
        }
        with patch('api.routers.payments.voucher_service.verify_voucher', return_value=mock_result):
            response = client.post('/api/v1/vouchers/verify', json={'voucher_code': 'RNF1 23AB CD4E', 'postcode': 'N1 1AA'})
        assert response.status_code == 200
        assert response.json()['eligible'] is True

    def test_verify_voucher_failure_returns_distinct_message(self, client):
        with patch('api.routers.payments.voucher_service.verify_voucher', side_effect=voucher_error('already_used', 'This voucher has already been used.')):
            response = client.post('/api/v1/vouchers/verify', json={'voucher_code': 'RNF1 23AB CD4E', 'postcode': 'N1 1AA'})
        assert response.status_code == 200
        assert response.json()['failure_reason'] == 'already_used'


class TestStartSubscription:
    def test_start_subscription_without_voucher(self, client):
        with patch('api.routers.payments.user_service.add_user_address', return_value=MagicMock(address=MagicMock(id='addr-1', postcode='N1 1AA'))), \
             patch('api.routers.payments.insert_user_subscription', return_value={'id': 'sub-1', 'status': 'pending'}), \
             patch('api.routers.payments.insert_subscription_progress'), \
             patch('api.routers.payments.sub_builder.build_subscription_items', return_value=[]), \
             patch('api.routers.payments.insert_subscription_items'), \
             patch('api.routers.payments.sub_builder.build_stripe_startup_cost_items', return_value=[{'price': 'price_1', 'quantity': 1}]), \
             patch('api.routers.payments.pa.create_stripe_checkout_session', return_value={'checkout_url': 'http://checkout', 'session_id': 'cs_123', 'metadata': {'checkout_type': 'start_up'}}) as create_session:
            response = client.post('/api/v1/subscriptions', json={
                'babyBirthdate': '2024-01-01',
                'babyWeight': 5.5,
                'serviceLevel': 'full-time',
                'address': {
                    'address_line_1': '1 Test Street',
                    'city': 'London',
                    'postcode': 'N1 1AA',
                    'country': 'UK'
                }
            })
        assert response.status_code == 200
        assert create_session.call_args.kwargs['coupon_id'] is None

    def test_start_subscription_with_voucher_applies_discount(self, client):
        with patch('api.routers.payments.user_service.add_user_address', return_value=MagicMock(address=MagicMock(id='addr-1', postcode='N1 1AA'))), \
             patch('api.routers.payments.insert_user_subscription', return_value={'id': 'sub-1', 'status': 'pending'}), \
             patch('api.routers.payments.insert_subscription_progress'), \
             patch('api.routers.payments.sub_builder.build_subscription_items', return_value=[]), \
             patch('api.routers.payments.insert_subscription_items'), \
             patch('api.routers.payments.insert_voucher') as insert_voucher, \
             patch('api.routers.payments.sub_builder.build_stripe_startup_cost_items', return_value=[{'price': 'price_1', 'quantity': 1}]), \
             patch('api.routers.payments.pa.create_stripe_checkout_session', return_value={'checkout_url': 'http://checkout', 'session_id': 'cs_123', 'metadata': {'checkout_type': 'start_up'}}) as create_session:
            response = client.post('/api/v1/subscriptions', json={
                'babyBirthdate': '2024-01-01',
                'babyWeight': 5.5,
                'serviceLevel': 'full-time',
                'address': {
                    'address_line_1': '1 Test Street',
                    'city': 'London',
                    'postcode': 'N1 1AA',
                    'country': 'UK'
                },
                'voucher': {
                    'code': 'RNF1 23AB CD4E',
                    'postcode': 'N1 1AA',
                    'discount_code': 'coupon_123',
                    'voucher_type': 'RNFL'
                }
            })
        assert response.status_code == 200
        insert_voucher.assert_called_once()
        assert create_session.call_args.kwargs['coupon_id'] == 'coupon_123'


class TestGetPaymentDetails:
    def test_get_payment_details_success(self, client):
        mock_response = MagicMock()
        mock_response.amount_total = 1000
        mock_response.customer_email = "user@example.com"
        mock_response.checkout_type = "start_up"

        with patch("api.routers.payments.pa.get_payment_completed_details", return_value=mock_response):
            response = client.post("/api/v1/payments/details", json={"session_id": "cs_test_123"})
        assert response.status_code == 200


class TestStartupWebhookProcessing:
    def test_marks_redeemed_when_redeem_succeeds(self):
        from payment_serv import payment_processor as pp

        with patch('payment_serv.payment_processor.update_user_subscription'), \
             patch('payment_serv.payment_processor.update_subscription_progress_admin'), \
             patch.object(pp, 'supabase') as mock_supabase, \
             patch('payment_serv.payment_processor.get_product_by_stripe_price_id', return_value={'name': 'Setup', 'currency': 'gbp', 'price': 7000, 'type': 'oneoff'}), \
             patch('payment_serv.payment_processor.get_user_by_subscription_id', return_value={'email': 'user@example.com', 'user_metadata': {'first_name': 'Test', 'surname': 'Tester'}}), \
             patch('payment_serv.payment_processor.get_voucher_by_subscription_id', return_value={'code': 'RNF1', 'postcode': 'N1 1AA', 'type': 'RNFL', 'status': 'verified'}), \
             patch('payment_serv.payment_processor.voucher_service.redeem_voucher'), \
             patch('payment_serv.payment_processor.update_voucher_status', return_value={'status': 'redeemed'}) as update_status, \
             patch('payment_serv.payment_processor.email_processor.send_new_subscription_email'), \
             patch('payment_serv.payment_processor.get_subscription_address', return_value={}), \
             patch('payment_serv.payment_processor.email_processor.send_order_email_to_team'):
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [MagicMock(data=[])]
            pp.startup_costs_paid_processing('sub-1', {'object': {'customer': 'cus_1', 'amount_total': 7000, 'id': 'cs_1'}}, [{'price': 'price_1', 'quantity': 1}])
        update_status.assert_called_with('RNF1', 'redeemed')

    def test_marks_manual_review_when_redeem_fails(self):
        from payment_serv import payment_processor as pp

        with patch('payment_serv.payment_processor.update_user_subscription'), \
             patch('payment_serv.payment_processor.update_subscription_progress_admin'), \
             patch.object(pp, 'supabase') as mock_supabase, \
             patch('payment_serv.payment_processor.get_product_by_stripe_price_id', return_value={'name': 'Setup', 'currency': 'gbp', 'price': 7000, 'type': 'oneoff'}), \
             patch('payment_serv.payment_processor.get_user_by_subscription_id', return_value={'email': 'user@example.com', 'user_metadata': {'first_name': 'Test'}}), \
             patch('payment_serv.payment_processor.get_voucher_by_subscription_id', return_value={'code': 'RNF1', 'postcode': 'N1 1AA', 'type': 'RNFL', 'status': 'verified'}), \
             patch('payment_serv.payment_processor.voucher_service.redeem_voucher', side_effect=pp.voucher_service.VoucherServiceError('fail')), \
             patch('payment_serv.payment_processor.update_voucher_status', return_value={'status': 'manual-review'}) as update_status, \
             patch('payment_serv.payment_processor.email_processor.send_new_subscription_email'), \
             patch('payment_serv.payment_processor.get_subscription_address', return_value={}), \
             patch('payment_serv.payment_processor.email_processor.send_order_email_to_team'):
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [MagicMock(data=[])]
            pp.startup_costs_paid_processing('sub-1', {'object': {'customer': 'cus_1', 'amount_total': 7000, 'id': 'cs_1'}}, [{'price': 'price_1', 'quantity': 1}])
        update_status.assert_called_with('RNF1', 'manual-review')
