"""
Create a test invoice image for testing PostMate

Usage:
    python create_test_image.py
"""

from PIL import Image, ImageDraw, ImageFont
import os


def create_test_invoice():
    """Create a sample invoice image"""

    # Create blank image
    img = Image.new('RGB', (800, 1100), color='white')
    draw = ImageDraw.Draw(img)

    # Try to use a better font, fall back to default
    try:
        # Try common font locations
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
        ]

        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, 24)
                    font_small = ImageFont.truetype(path, 16)
                    font_large = ImageFont.truetype(path, 36)
                    break
                except:
                    continue

        if font is None:
            raise Exception("No font found")

    except:
        print("Using default font (text may be small)")
        font = ImageFont.load_default()
        font_small = font
        font_large = font

    # Draw invoice header
    draw.rectangle([(0, 0), (800, 100)], fill='#2C3E50')
    draw.text((300, 30), "INVOICE", fill='white', font=font_large)

    # Company info
    y = 120
    draw.text((50, y), "ABC Consulting Inc.", fill='black', font=font)
    y += 30
    draw.text((50, y), "123 Business Street", fill='#555', font=font_small)
    y += 25
    draw.text((50, y), "New York, NY 10001", fill='#555', font=font_small)
    y += 25
    draw.text((50, y), "Phone: (555) 123-4567", fill='#555', font=font_small)

    # Invoice details (right side)
    y = 120
    draw.text((500, y), "Invoice #: INV-2024-001", fill='black', font=font)
    y += 30
    draw.text((500, y), "Date: January 15, 2024", fill='#555', font=font_small)
    y += 25
    draw.text((500, y), "Due Date: February 15, 2024", fill='#555', font=font_small)

    # Bill To section
    y = 280
    draw.rectangle([(50, y), (750, y+2)], fill='#BDC3C7')
    y += 20
    draw.text((50, y), "BILL TO:", fill='#2C3E50', font=font)
    y += 30
    draw.text((50, y), "John Doe", fill='black', font=font_small)
    y += 25
    draw.text((50, y), "XYZ Corporation", fill='#555', font=font_small)
    y += 25
    draw.text((50, y), "456 Client Avenue", fill='#555', font=font_small)

    # Table header
    y = 450
    draw.rectangle([(50, y), (750, y+40)], fill='#ECF0F1')
    draw.text((60, y+10), "Description", fill='#2C3E50', font=font)
    draw.text((400, y+10), "Quantity", fill='#2C3E50', font=font)
    draw.text((550, y+10), "Rate", fill='#2C3E50', font=font)
    draw.text((650, y+10), "Amount", fill='#2C3E50', font=font)

    # Line items
    items = [
        ("Software Development Services", "40 hrs", "$100.00", "$4,000.00"),
        ("Consulting Services", "20 hrs", "$150.00", "$3,000.00"),
        ("Project Management", "10 hrs", "$120.00", "$1,200.00"),
    ]

    y += 50
    for desc, qty, rate, amount in items:
        draw.text((60, y), desc, fill='black', font=font_small)
        draw.text((400, y), qty, fill='black', font=font_small)
        draw.text((550, y), rate, fill='black', font=font_small)
        draw.text((650, y), amount, fill='black', font=font_small)
        y += 35

    # Totals
    y = 750
    draw.rectangle([(50, y), (750, y+2)], fill='#BDC3C7')

    y += 20
    draw.text((550, y), "Subtotal:", fill='black', font=font_small)
    draw.text((650, y), "$8,200.00", fill='black', font=font_small)

    y += 30
    draw.text((550, y), "Tax (8%):", fill='black', font=font_small)
    draw.text((650, y), "$656.00", fill='black', font=font_small)

    y += 40
    draw.rectangle([(540, y-10), (750, y+35)], fill='#27AE60')
    draw.text((550, y), "TOTAL:", fill='white', font=font)
    draw.text((650, y), "$8,856.00", fill='white', font=font)

    # Payment terms
    y = 920
    draw.text((50, y), "Payment Terms:", fill='#2C3E50', font=font)
    y += 30
    draw.text((50, y), "Net 30 days. Payment due by February 15, 2024.", fill='#555', font=font_small)
    y += 25
    draw.text((50, y), "Please make checks payable to: ABC Consulting Inc.", fill='#555', font=font_small)

    # Thank you message
    y = 1020
    draw.text((250, y), "Thank you for your business!", fill='#7F8C8D', font=font)

    # Save
    output_path = "tests/sample_data/test_invoice.jpg"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=95)

    print(f"✓ Test invoice image created: {output_path}")
    print(f"  Size: {img.size}")
    print(f"  Format: JPEG")
    print()
    print("You can now upload this image:")
    print(f"  curl -X POST http://localhost:8080/api/v1/upload -F 'files=@{output_path}'")

    return output_path


if __name__ == "__main__":
    create_test_invoice()
