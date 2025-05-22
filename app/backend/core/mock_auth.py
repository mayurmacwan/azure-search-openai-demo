from typing import Any, Dict

class MockAuthenticationHelper:
    def __init__(self):
        """Initialize a mock authentication helper that returns no authentication required"""
        pass

    def get_auth_setup_for_client(self) -> Dict[str, Any]:
        """Returns mock MSAL.js settings with authentication disabled"""
        return {
            "useLogin": False,
            "requireAccessControl": False,
            "enableUnauthenticatedAccess": True,
            "msalConfig": {
                "auth": {
                    "clientId": "mock-client-id",
                    "authority": "https://login.microsoftonline.com/mock-tenant",
                    "redirectUri": "/redirect",
                    "postLogoutRedirectUri": "/",
                    "navigateToLoginRequestUrl": False,
                },
                "cache": {
                    "cacheLocation": "localStorage",
                    "storeAuthStateInCookie": False,
                },
            },
            "loginRequest": {
                "scopes": [".default"],
            },
            "tokenRequest": {
                "scopes": ["api://mock-server-id/access_as_user"],
            },
        }

    async def get_auth_claims_if_enabled(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Returns empty auth claims since authentication is disabled"""
        return {} 