import qrcode


def generate_qr_code(event_link: str, save_path: str) -> None:
    """Generates a QR Code and saves it to the specified path."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(event_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(save_path)
