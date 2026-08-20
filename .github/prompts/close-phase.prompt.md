# Close Phase

Assess whether the phase or subphase I identify is ready for formal closure.

Verify:
- all known findings and remediation items are resolved or explicitly deferred with justification;
- focused tests and permanent closure/regression suites are green;
- broader regression is proportional to the change;
- validators, compile checks, or other repository gates required by the phase pass;
- roadmap, reference documentation, specifications, plans, and implementation state do not contradict one another;
- Git scope is known and unrelated work is preserved;
- the final closure claim is supported by current evidence.

Do not declare the phase closed merely because implementation exists or because earlier evidence was green.

If any required gate is missing or failing, report the phase as not ready for formal closure and identify the exact next action.
