"""Phase 10.47 — Project domain benchmark assets.

Declarative benchmark cases derived from the audited Project Domain rules
(``project.architecture_contract``, ``project.validation_required``,
``project.semantic_transformation``, ``project.backward_compatibility``) and its
existing resource catalog.

These assets are declarative expectations only. They never execute tools or
code, never invoke a model, and never validate a response at runtime.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)


def build_project_benchmark_suites() -> tuple[DomainBenchmarkSuite, ...]:
    """Build the deterministic ``benchmark-suite:project:core`` suite."""
    return (
        DomainBenchmarkSuite(
            id="benchmark-suite:project:core",
            domain_id="domain:project",
            schema_version="1",
            version="1",
            cases=(
                DomainBenchmarkCase(
                    id="benchmark-case:project:architecture-consistency-001",
                    domain_id="domain:project",
                    objective=(
                        "Generate a code change that stays consistent with the "
                        "declared architecture and preserves backward compatibility"
                    ),
                    input_resource_refs=(
                        "project.resource.architecture_document",
                        "project.resource.source_file",
                        "project.resource.test_file",
                    ),
                    expected_elements=(
                        "generated code respects the architecture contract",
                        "public API changes are identified",
                        "backward compatibility is preserved or explicitly flagged",
                        "validation requirements are stated",
                    ),
                    required_constraints=(
                        "respect declared dependency boundaries",
                        "declare required validation before claiming completion",
                    ),
                    prohibited_behaviors=(
                        "violate the declared architecture contract",
                        "silently break backward compatibility",
                        "claim validation that was not performed",
                    ),
                    evaluation_criteria=(
                        "code generation",
                        "architectural consistency",
                        "validation",
                        "backward compatibility",
                    ),
                    required_format="structured",
                    required_schema={
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "changes": {"type": "array"},
                            "validation": {"type": "array"},
                        },
                        "required": ["summary", "changes"],
                    },
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "architecture-consistency",
                    },
                ),
                DomainBenchmarkCase(
                    id="benchmark-case:project:structured-output-and-tools-001",
                    domain_id="domain:project",
                    objective=(
                        "Produce a structured tool-call plan that matches the "
                        "requested schema and recovers from a declared error"
                    ),
                    input_resource_refs=(
                        "project.resource.task",
                        "project.resource.tool_contract",
                    ),
                    expected_elements=(
                        "tool calls are appropriate to the task",
                        "structured output matches the required schema",
                        "errors are corrected explicitly",
                    ),
                    required_constraints=(
                        "declare tools without executing them from the benchmark asset",
                        "keep the structured output schema-compliant",
                    ),
                    prohibited_behaviors=(
                        "execute a tool from a benchmark asset",
                        "emit unstructured output when a schema is required",
                        "silently ignore a declared error",
                    ),
                    evaluation_criteria=(
                        "tool calling",
                        "structured output",
                        "error correction",
                    ),
                    required_format="structured",
                    metadata={
                        "fixture_kind": "synthetic",
                        "roadmap_area": "structured-output-and-tools",
                    },
                ),
            ),
            metadata={"source": "first-party", "phase": "10.47"},
        ),
    )
