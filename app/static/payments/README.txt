BINANCE PAY QR

Place here the official receive QR image downloaded from the Binance app, named exactly:
  binance-pay-qr.png

Do not generate a QR by simply encoding the numeric Binance ID: the official Binance Pay QR is the payment payload the app issues. The public checkout shows it only when the file exists and CALYRISIA_BINANCE_QR_IMAGE_URL=/payments/binance-pay-qr.png is configured.

A static personal receive QR does not automatically associate a payment with a checkout order and does not provide a signed webhook. Payments with this QR therefore stay in manual review until the operator verifies the actual receipt. For automatic confirmation, integrate a Binance Pay merchant account/API and validate the signed order webhook.
