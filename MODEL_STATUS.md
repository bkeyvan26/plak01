# وضعیت مدل‌های نصب‌شده — ۳۱ اوت ۲۰۲۶

مدل‌های محلی از مخزن عمومی `Dibachain/Platrix` دریافت شده‌اند. این مدل‌ها
برای اجرای CPU با ONNX Runtime طراحی شده‌اند: YOLO برای تشخیص پلاک و CRNN+CTC
برای خواندن کل پلاک. کارت مدل خروجی استاندارد پلاک ایرانی `DD L DDD DD` را
توضیح می‌دهد و می‌گوید inference بدون PyTorch/TensorFlow انجام می‌شود.

فایل‌ها:

```text
models/platrix/plate_yolo.onnx
models/platrix/plate_yolo_fallback.onnx
models/platrix/ocr_crnn.onnx
models/platrix/ocr_crnn.labels.json
models/platrix/ocr_cnn.onnx
models/platrix/ocr_cnn.labels.json
```

SHA-256:

```text
plate_yolo.onnx          A54E475C402E6036BB5C70F1A6FF75179E76098A5C8039BB5D148C0B6421F5C6
plate_yolo_fallback.onnx A6974FCB0A79755C270D50F1EBEFD4D96D765C879A29051A19AAC00DFDA8B5AF
ocr_crnn.onnx            45F8C45F29EB1EE91F6274CB8D9C328DA1A2050EA7D8596BAE61F4A6B9F9FB1E
ocr_crnn.labels.json     65A5B7DCB24234C6EA02CC93D58E8D9EF8E469F670F25F44D6B9CC8B2E2670BC
ocr_cnn.onnx             7D573C51CC855A8E080F1F88597477F4FB5A2B9CAFA1BB125BD6038E441F5BCA
ocr_cnn.labels.json      3E2CDD796B9F04049D2B02051FEE42DCC70413D62E145177BE33277AEA70DDB5
```

تست بارگذاری مدل موفق بود: `plate_yolo.onnx` با ONNX Runtime/CPU بارگذاری شد،
CRNN با ۳۲ برچسب بارگذاری شد و روی یک crop آزمایشی خروجی `13ز41` تولید کرد.
