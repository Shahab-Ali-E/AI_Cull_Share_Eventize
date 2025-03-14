import qrcode
import base64
from io import BytesIO

def generate_qr_code(event_link: str) -> str:
    """Generates a QR Code and returns it as a base64-encoded string."""

    # Generate QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(event_link)
    qr.make(fit=True)

    # Convert QR to Image
    img = qr.make_image(fill="black", back_color="white")

    # Save Image to BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Encode Image as Base64
    base64_qr = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{base64_qr}"  # Return Base64 string
