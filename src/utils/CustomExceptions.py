class URLExpiredException(Exception):
    def __init__(self, message="One or more image URLs have expired. Please upload the images again or contact support."):
        self.message = message
        super().__init__(self.message)

class SignatureDoesNotMatch(Exception):
    def __init__(self, message="The request signature we calculated does not match the signature you provided. Check your key and signing method."):
        self.message = message
        super().__init__(self.message)

class UnauthorizedAccess(Exception):
    def __init__(self, message="The AWS Access Key Id you provided does not exist in our records."):
        self.message = message
        super().__init__(self.message)