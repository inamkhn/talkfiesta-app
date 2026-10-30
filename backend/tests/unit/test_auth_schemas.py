"""Unit tests for the registration request contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    RegisterRequest,
)


def test_email_is_trimmed_and_lowercased() -> None:
    request = RegisterRequest(email="  Sam@Example.COM ", password="a" * 12)

    assert request.email == "sam@example.com"


def test_server_owned_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.co", password="a" * 12, role="ADMIN")


def test_password_length_bounds() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.co", password="a" * (PASSWORD_MIN_LENGTH - 1))

    RegisterRequest(email="a@b.co", password="a" * PASSWORD_MIN_LENGTH)
    RegisterRequest(email="a@b.co", password="a" * PASSWORD_MAX_LENGTH)

    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.co", password="a" * (PASSWORD_MAX_LENGTH + 1))


def test_password_whitespace_is_preserved() -> None:
    request = RegisterRequest(email="a@b.co", password="  secret12  ")

    assert request.password == "  secret12  "


def test_blank_first_name_becomes_none() -> None:
    request = RegisterRequest(email="a@b.co", password="a" * 12, first_name="   ")

    assert request.first_name is None


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="a" * 12)
