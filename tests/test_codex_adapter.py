from __future__ import annotations

from types import SimpleNamespace

from bookanalyzer.codex_adapter import dimension_output_schema


def test_dimension_schema_is_closed_and_supports_conditional_na() -> None:
    dimension = SimpleNamespace(
        key="demo",
        features=[
            SimpleNamespace(
                id="CAT",
                type="categorical",
                values=["a", "b"],
                condition=None,
            ),
            SimpleNamespace(
                id="SCL",
                type="scale",
                values=["1_low", "2_high"],
                condition="when applicable",
            ),
            SimpleNamespace(
                id="MUL",
                type="multi_select",
                values=["x", "y"],
                condition=None,
            ),
        ],
    )

    schema = dimension_output_schema(dimension)

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["CAT", "SCL", "MUL"]
    assert schema["properties"]["CAT"]["enum"] == ["a", "b"]
    assert schema["properties"]["SCL"]["anyOf"][0]["enum"] == [1, 2]
    assert schema["properties"]["SCL"]["anyOf"][1]["enum"] == ["n/a"]
    assert schema["properties"]["MUL"]["items"]["enum"] == ["x", "y"]
