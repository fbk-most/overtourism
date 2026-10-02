# SPDX-License-Identifier: Apache-2.0

import logging

from overtourism.backend.utils.logging_config import service_log_format
from overtourism.layer_3.api.logging_config import (
    service_log_format as layer_3_service_log_format,
)


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


def test_layer_3_log_format_includes_service_version_and_message() -> None:
    log_record = logging.LogRecord(
        name="overtourism.layer_3.api.main",
        level=logging.INFO,
        pathname="main.py",
        lineno=42,
        msg="Layer 3 started",
        args=(),
        exc_info=None,
    )
    formatter = logging.Formatter(layer_3_service_log_format("layer-3-models", "0.1.0"))

    formatted_message = formatter.format(log_record)

    assert "service=layer-3-models" in formatted_message
    assert "version=0.1.0" in formatted_message
    assert "Layer 3 started" in formatted_message
