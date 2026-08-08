"""Constants for the JDECo integration."""
DOMAIN = "jdeco"

# API endpoints (decoded from APK analysis)
# V3GACG appears to be the newer/primary endpoint
API_BASE_URL = "https://androidAPP.jdeco.net:2083/V3GACG"
API_BASE_URL_ALT = "https://androidAPP.jdeco.net:2083/GACG"

# API methods/operations
METHOD_REQUEST_PK = "requestPK"
METHOD_VERIFY_CREDENTIALS = "verifyCustomerCredentials"
METHOD_GET_AGREEMENTS = "getCustomerAgreements"
METHOD_GET_AGREEMENT_DETAILS = "getAgreementDetails"
METHOD_GET_AGREE_DEBT = "getAgreeDebt"
METHOD_GET_LAST_VOUCHER = "getAgreementLastVoucher"
METHOD_GET_KW_QTY = "getKWQty"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_AGREEMENT_NO = "agreement_no"
CONF_DEVICE_ID = "device_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL = 30  # minutes between updates
DEFAULT_TIMEOUT = 40  # seconds for HTTP requests

# Fixed app identifiers (from reverse-engineered Android app)
APP_SYSTEM_ID = 3
FRF_VALUE = "ANDROID"

# Storage/cache keys
STORAGE_AUTH_TOKEN = "auth_token"
STORAGE_SESSION_KEY = "session_key"
STORAGE_ENCRYPTED_SESSION = "encrypted_session"
