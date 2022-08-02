import logging

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from extensions.payment.processors.razorpay import RazorPay
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class RazorPayPaymentExecutionView(EdxOrderPlacementMixin, View):
    """Execute an approved PayPal payment and place an order for paid products as appropriate."""

    @property
    def payment_processor(self):
        return RazorPay(self.request.site)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(RazorPayPaymentExecutionView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, payment_id):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        try:
            basket = PaymentProcessorResponse.objects.get(
                processor_name=self.payment_processor.NAME,
                transaction_id=payment_id
            ).basket
            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, self.request)

            basket_add_organization_attribute(basket, self.request.GET)
            return basket
        except MultipleObjectsReturned:
            logger.warning(u"Duplicate payment ID [%s] received from PayPal.", payment_id)
            return None
        except Exception:  # pylint: disable=broad-except
            logger.exception(u"Unexpected error during basket retrieval while executing PayPal payment.")
            return None

    def get(self, request):
        """Handle an incoming user returned to us by PayPal after approving payment."""
        razorpay_payment_id = request.GET.get('razorpay_payment_id')
        razorpay_payment_link_id = request.GET.get('razorpay_payment_link_id')
        razorpay_payment_link_status = request.GET.get('razorpay_payment_link_status')

        logger.info(u"Payment [%s] is [%s]", razorpay_payment_id, razorpay_payment_link_status)

        razorpay_response = request.GET.dict()
        basket = self._get_basket(razorpay_payment_link_id)

        if not basket:
            return redirect(self.payment_processor.error_url)

        receipt_url = get_receipt_page_url(
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration,
            disable_back_button=True,
        )

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(razorpay_response, basket)
                except PaymentError:
                    return redirect(self.payment_processor.error_url)
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return redirect(receipt_url)

        try:
            order = self.create_order(request, basket)
        except Exception:  # pylint: disable=broad-except
            # any errors here will be logged in the create_order method. If we wanted any
            # Paypal specific logging for this error, we would do that here.
            logger.exception('---------------')
            return redirect(receipt_url)

        try:
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)

        return redirect(receipt_url)


class RazorPayRedirectView(View):
    def get(self, request):
        return redirect(f'{request.GET.get("redirect_url")}&ecommerce_basket_id={request.GET.get("ecommerce_basket_id")}')

    def post(self, request):
        return redirect(f'{request.GET.get("redirect_url")}&ecommerce_basket_id={request.GET.get("ecommerce_basket_id")}')
