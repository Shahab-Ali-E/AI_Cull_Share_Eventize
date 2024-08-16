class URLExpiredException(Exception):
    def __init__(self, message="One or more image URLs have expired. Please upload the images again or contact support."):
        self.message = message
        super().__init__(self.message)
    