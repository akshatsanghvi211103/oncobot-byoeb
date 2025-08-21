import logging
import os
from byoeb_core.channel.base import BaseChannelRegister
from byoeb_core.models.byoeb.response import ByoebResponseModel

class RegisterQikchat(BaseChannelRegister):
    """
    A class to handle the registration process for 
    Qikchat by implementing the BaseChannelRegister interface.

    Key Differences from WhatsApp:
    - Qikchat uses different parameter names for webhook verification
    - Simpler verification process (no hub.mode requirement)
    - Uses 'verify_token' instead of 'hub.verify_token'

    Methods
    -------
    register(params: dict) -> ByoebResponseModel
        Handles the registration request and returns a ByoebResponseModel object.
        
    __get_response(params, verification_token) -> ByoebResponseModel
        A private method that handles the webhook verification process
        specific to Qikchat's API requirements.
    """

    # Qikchat webhook verification parameters
    __REQUEST_TOKEN = "verify_token"  # Different from WhatsApp's "hub.verify_token"
    __REQUEST_CHALLENGE = "challenge"  # Similar to WhatsApp but simpler

    def __init__(
        self,
        verification_token: str
    ) -> None:
        self.__logger = logging.getLogger(self.__class__.__name__)
        self.__verification_token = verification_token.strip()

    async def register(
        self,
        params: dict,
        **kwargs
    ) -> ByoebResponseModel:
        self.__logger.debug(msg="Registering Qikchat webhook")
        self.__logger.debug(f"Registration hash: {self.__hash__}")
        response = self.__get_response(params, self.__verification_token)
        return response

    def __is_invalid(
        self,
        value: str
    ):
        return value in (None, '', 'null')
    
    def __get_response(
        self,
        params: dict,
        verification_token: str
    ) -> ByoebResponseModel:
        """
        Handle Qikchat webhook verification.
        
        Key Differences from WhatsApp:
        1. No 'hub.mode' requirement - Qikchat doesn't use this
        2. Simpler parameter structure
        3. Direct token and challenge verification
        """
        token = params.get(self.__REQUEST_TOKEN)
        challenge = params.get(self.__REQUEST_CHALLENGE)

        # Validate required parameters
        if (self.__is_invalid(token) or self.__is_invalid(challenge)):
            self.__logger.warning("Invalid Qikchat webhook verification request - missing parameters")
            return ByoebResponseModel(
                message="Invalid request to register Qikchat webhook - missing token or challenge",
                status_code=400
            )

        # Verify token matches configured verification token
        if token != self.__verification_token:
            self.__logger.warning("Invalid Qikchat verification token provided")
            return ByoebResponseModel(
                message="Invalid verification token for Qikchat",
                status_code=403
            )

        # Return challenge for successful verification
        self.__logger.info("Qikchat webhook verification successful")
        return ByoebResponseModel(
            message=challenge,  # Qikchat expects the challenge back
            status_code=200
        )
