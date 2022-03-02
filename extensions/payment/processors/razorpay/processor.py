""" RazorPay payment processing. """

import logging
import razorpay
import hmac
import hashlib

from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.functional import cached_property

from ecommerce.core.url_utils import get_ecommerce_url
from oscar.apps.payment.exceptions import GatewayError
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse

logger = logging.getLogger(__name__)


class RazorPay(BasePaymentProcessor):
    """
   PayPal REST API (May 2015)

   For reference, see https://developer.paypal.com/docs/api/.
   """

    NAME = 'razorpay'
    TITLE = 'RazorPay'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the RazorPay processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(RazorPay, self).__init__(site)

    @cached_property
    def razerpay_api(self):
        return razorpay.Client(auth=(self.configuration['client_id'], self.configuration['client_secret']))

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def error_url(self):
        return get_ecommerce_url(self.configuration['error_path'])

    def fetch_payment_details(self, payment_id):
        return self.razerpay_api.payment.fetch(payment_id)

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        client = self.razerpay_api

        payment = client.payment_link.create({
            "amount": int(basket.total_incl_tax),
            "currency": basket.currency,
            "accept_partial": False,
            "callback_url": get_ecommerce_url(reverse("razorpay:urls:callback")),
            "callback_method": "get"
        })
        entry = self.record_processor_response(payment, transaction_id=payment['id'], basket=basket)
        logger.info("Successfully created PayPal payment [%s] for basket [%d].", payment['id'], basket.id)
        parameters = {
            'payment_page_url': f'{reverse("razorpay:urls:redirect")}?redirect_url={payment["short_url"]}',
            'csrfmiddlewaretoken': get_token(request),
        }

        return parameters

    def handle_processor_response(self, response, basket=None):

        razorpay_payment_id = response.get('razorpay_payment_id')
        razorpay_payment_link_id = response.get('razorpay_payment_link_id')
        razorpay_payment_link_status = response.get('razorpay_payment_link_status')
        razorpay_signature = response.get('razorpay_signature')
        razorpay_payment_link_reference_id = response.get('razorpay_payment_link_reference_id')

        message = (
                razorpay_payment_link_id + '|' +
                razorpay_payment_link_reference_id + '|' +
                razorpay_payment_link_status + '|' +
                razorpay_payment_id
        )

        expected_signature = hmac.new(
            bytes(
                self.configuration['client_secret'],
                'latin-1'
            ),
            msg=bytes(
                message,
                'latin-1'
            ),
            digestmod=hashlib.sha256
        ).hexdigest().lower()

        entry = self.record_processor_response(response, transaction_id=razorpay_payment_id, basket=basket)

        if expected_signature == razorpay_signature and razorpay_payment_link_status == 'paid':
            logger.info("Successfully executed RazorPay payment [%s] for basket [%d].", razorpay_payment_id, basket.id)
        else:
            logger.error(
                "Failed to complete RazorPay payment [%s]. "
                "payment's response was recorded in entry [%d].",
                razorpay_payment_id,
                entry.id
            )
            raise GatewayError

        currency = basket.currency
        total = basket.total_incl_tax
        transaction_id = razorpay_payment_id
        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number='RazorPay',
            card_type=None
        )

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        pass
