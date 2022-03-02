from django.conf.urls import include, url

from .views import (
    RazorPayRedirectView,
    RazorPayPaymentExecutionView,
)

RAZORPAY_URLS = [
    url(r'^redirect/$', RazorPayRedirectView.as_view(), name='redirect'),
    url(r'^callback/$', RazorPayPaymentExecutionView.as_view(), name='callback'),
]

urlpatterns = [
    url(r'^handlers/', include((RAZORPAY_URLS, 'urls'))),
]
