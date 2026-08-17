# SPDX-License-Identifier: Apache-2.0

import numpy as np

from overtourism.model.fazzon.fazzon_backend import FazzonBackend


class TestFazzonBackend:
    """Smoke tests for FazzonBackend — catches import/reorg breakage."""

    def test_evaluate_default_scenario(self):
        backend = FazzonBackend()
        output = backend.evaluate({})

        assert output.field.shape == (101, 101)
        assert np.isfinite(output.field).all()
        assert ((output.field >= -1e-9) & (output.field <= 1.0 + 1e-9)).all()

    def test_parameter_schema_matches_evaluate_overrides(self):
        backend = FazzonBackend()
        schema = backend.parameter_schema()

        assert len(schema) > 0
        names = {spec.name for spec in schema}
        assert len(names) == len(schema)
