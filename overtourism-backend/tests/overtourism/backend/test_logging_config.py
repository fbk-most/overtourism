# SPDX-License-Identifier: Apache-2.0

import logging

from overtourism.backend.utils.logging_config import service_log_format


def test_service_log_format_includes_service_version_and_message() -> None:
    log_record = logging.LogRecord(
        name="overtourism.backend.main",
        level=logging.INFO,
        pathname="main.py",
        lineno=42,
        msg="Backend started",
        args=(),
        exc_info=None,
    )
    formatter = logging.Formatter(service_log_format("backend-api", "2.0.0"))

    formatted_message = formatter.format(log_record)

    assert "service=backend-api" in formatted_message
    assert "version=2.0.0" in formatted_message
    assert "Backend started" in formatted_message
