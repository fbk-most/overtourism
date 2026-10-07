# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


def service_log_format(service: str, version: str) -> str:
    return (
        "%(asctime)s | %(levelname)s | "
        f"service={service} version={version} | "
        "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )
