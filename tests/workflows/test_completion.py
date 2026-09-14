from cmm.workflows.completion import CompletionCriteria, evaluate_completion_criteria


def test_completion_criteria_are_declarative_and_deterministic():
    criteria = CompletionCriteria(
        all_required_nodes_completed=True,
        no_blocking_failures=True,
        minimum_successful_nodes=2,
        specific_node_completed="finish",
    )
    assert evaluate_completion_criteria(criteria, completed={"prepare", "finish"}, failed=set(), skipped=set())
    assert not evaluate_completion_criteria(criteria, completed={"prepare"}, failed=set(), skipped=set())
