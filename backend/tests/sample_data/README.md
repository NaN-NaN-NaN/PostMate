# Test Sample Data

## Test Images

Place test images here for testing the upload and OCR functionality.

### Recommended Test Images:

1. **test_invoice.jpg** - Sample invoice image
2. **test_receipt.jpg** - Sample receipt image
3. **test_letter.jpg** - Sample letter/document image

### Creating Test Images:

You can use any of these methods:

1. **Screenshot approach**: Take a screenshot of a sample invoice/receipt
2. **Online generators**: Use free invoice/receipt generators
3. **Create programmatically**: Use PIL/Pillow to create test images with text

### Example: Create Test Image with Python

```python
from PIL import Image, ImageDraw, ImageFont

# Create blank image
img = Image.new('RGB', (800, 1000), color='white')
draw = ImageDraw.Draw(img)

# Add text
font = ImageFont.load_default()
draw.text((50, 50), "INVOICE", fill='black')
draw.text((50, 100), "Invoice #: 12345", fill='black')
draw.text((50, 130), "Date: 2024-01-15", fill='black')
draw.text((50, 160), "Total: $1,234.56", fill='black')

# Save
img.save('test_invoice.jpg')
```

### Using Sample Images:

Upload via curl:
```bash
curl -X POST http://localhost:8080/api/v1/upload \
  -F "files=@tests/sample_data/test_invoice.jpg"
```

Or use the test suite:
```bash
pytest tests/test_upload.py -v
```
