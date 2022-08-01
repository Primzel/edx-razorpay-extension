# Description
This is a razorpay extension for edx ecommerce service.

# Setup with devstack.
1. `make ecommerce-shell`
2. `cd /edx/src`
3. `git clone git@github.com:Primzel/edx-razorpay-extension.git`
4. `pip install - /edx/src/edx-razorpay-extension`

# Configurations

```vi /edx/etc/ecommerce.yml```

```yml
OSCAR_DEFAULT_CURRENCY: "INR"
PAYMENT_PROCESSORS:
- 'ecommerce.extensions.payment.processors.cybersource.Cybersource'
- 'ecommerce.extensions.payment.processors.cybersource.CybersourceREST'
- 'ecommerce.extensions.payment.processors.paypal.Paypal'
- 'ecommerce.extensions.payment.processors.stripe.Stripe'
- 'extensions.payment.processors.razorpay.RazorPay'
EXTRA_PAYMENT_PROCESSOR_URLS:
    razorpay: extensions.payment.processors.razorpay.urls

PAYMENT_PROCESSOR_CONFIG:
  edx:
    razorpay:
      cancel_checkout_path: "/checkout/cancel-checkout/"
      client_id: razorpay-account-client-id
      client_secret: razorpay-account-secret
      error_url: "/checkout/error/"
      mode: sandbox
      receipt_url: "/checkout/receipt/"
    paypal:
      mode: sandbox
      client_id: paypal-account-client-id
      client_secret: paypal-account-secret
```