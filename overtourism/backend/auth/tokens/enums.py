# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum


class AuthClaim(StrEnum):
    SUBJECT = "sub"
    TERRITORY = "tenant_id"
    EMAIL = "email"
    EMAIL_VERIFIED = "email_verified"


class AuthEnvironmentVariable(StrEnum):
    ENABLED = "AUTH_ENABLED"
    ISSUER = "AUTH_ISSUER"
    AUDIENCE = "AUTH_AUDIENCE"
    JWKS_URL = "AUTH_JWKS_URL"
    TERRITORY_CLAIM = "AUTH_TENANT_CLAIM"
    ALGORITHMS = "AUTH_ALGORITHMS"
    LEEWAY_SECONDS = "AUTH_LEEWAY_SECONDS"


class AuthHeaderScheme(StrEnum):
    BEARER = "bearer"


class AuthErrorDetail(StrEnum):
    MISSING_BEARER_TOKEN = "Missing bearer token"
    INVALID_BEARER_TOKEN = "Invalid bearer token"
    TERRITORY_MISMATCH = "Token territory does not match requested territory"


class JwtAlgorithm(StrEnum):
    RS256 = "RS256"


class JwtDecodeOption(StrEnum):
    VERIFY_SIGNATURE = "verify_signature"
    VERIFY_EXP = "verify_exp"
    VERIFY_NBF = "verify_nbf"
    VERIFY_IAT = "verify_iat"
    VERIFY_AUD = "verify_aud"
    VERIFY_ISS = "verify_iss"
