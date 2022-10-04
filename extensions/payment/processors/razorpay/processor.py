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
        user = request.user

        payment = client.payment_link.create({
            "amount": int(basket.total_incl_tax * 100),
            "currency": basket.currency,
            "accept_partial": False,
            "callback_url": get_ecommerce_url(reverse("razorpay:urls:callback")),
            "callback_method": "get",
            "notes": {
                "info": "Payment from MOOC platform"
            },
            "description": f"Payment for the order - [{basket.order_number}]]",
            "customer": {
                "name": user.profile.name,
                "contact": user.extended_profile.phone_number,
                "email": user.email,
            }
        })
        entry = self.record_processor_response(payment, transaction_id=payment['id'], basket=basket)
        logger.info("Successfully created Razorpay payment [%s] for basket [%d].", payment['id'], basket.id)
        redirect_url = f'{reverse("razorpay:urls:redirect")}?redirect_url={payment["short_url"]}'
        allow_user_info_tracking = self.configuration.get('allow_user_info_tracking', False)
        if allow_user_info_tracking:
            redirect_url = f'{reverse("razorpay:urls:redirect")}?redirect_url={self.configuration["lms_form_url"]}?redirect_url={payment["short_url"]}&ecommerce_basket_id={basket.id}'

        parameters = {
            'payment_page_url': redirect_url,
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
        total = basket.total_incl_tax * 100
        transaction_id = razorpay_payment_id
        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number='RazorPay',
            card_type=None
        )

    def issue_credit(self, order_number, basket, payment_id, amount, currency):
        amount = int(amount) * 100

        try:
            client = self.razerpay_api
            refund = client.payment.refund(
                payment_id,
                {'amount': amount}
            )
        except:
            msg = 'An error occurred while attempting to issue a credit (via RazorPay) for order [{}].'.format(
                order_number
            )
            logger.exception(msg)
            raise GatewayError(msg)

        if refund['status'] == 'processed':
            transaction_id = refund['id']
            self.record_processor_response(refund, transaction_id=transaction_id, basket=basket)
            return transaction_id

        msg = "Failed to refund RazorPay payment [{sale_id}]."
        logger.info(refund)
        raise GatewayError(msg)
