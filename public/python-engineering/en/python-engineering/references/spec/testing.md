# Testing

A test suite is two things at once: a safety net that catches regressions and a description of what the code is supposed to do. Both jobs are served by the same discipline — test *behavior*, not implementation. A test that pins down observable behavior survives a refactor and documents intent; a test that pins down internal calls breaks on every refactor and documents nothing useful. This document is about organizing tests so they do both jobs well.

## Test Organization

Keep tests in a top-level `tests/` directory, separate from the production package, so they are never shipped and so they exercise the package the way a real consumer would (see [structure](../project/structure.md) for why the src layout reinforces this). Name test files and functions after the *behavior* under test, not the implementation file they happen to touch — `test_expired_token_is_rejected` tells a reader what the system guarantees; `test_validate` tells them only which function ran. For a large library or framework, loosely mirroring the package tree helps locate tests, but the mirror is a navigation aid, not a rule that every module gets a parallel test file. Tests deserve the same care as production code: clear names, no copy-paste sprawl, and obvious intent.

## Fixture Design

A fixture supplies a test with a prepared object or environment and, optionally, tears it down afterward. Good fixtures are small, composable, and named for what they provide (`temp_db`, `authenticated_client`), and they are scoped no wider than necessary — a function-scoped fixture gives each test a fresh instance and keeps tests independent, while a session-scoped fixture trades isolation for speed and should be reserved for genuinely expensive, read-only setup. Resist building one giant fixture that constructs an entire world; compose small fixtures so each test pulls in only what it needs, and a reader can see from the parameter list what a test depends on. When setup needs cleanup — a temp directory, an open connection — express it as a fixture that yields and then tears down, so the cleanup runs even when the test fails.

## Parametrization

When the same behavior should hold across many inputs, a parametrized test expresses each case as data rather than as duplicated test bodies:

```python
import pytest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Alice ", "alice"),
        ("BOB", "bob"),
        ("", ""),
    ],
)
def test_normalize_username(raw: str, expected: str) -> None:
    assert normalize_username(raw) == expected
```

Each case is reported as a separate test, so a failure names the exact input that broke. Parametrization is the right tool for boundary and equivalence-class testing — empty input, the typical case, the edge — and it keeps the cases visible as a table rather than buried in a loop. It is the wrong tool when the cases need genuinely different setup or assertions; forcing dissimilar scenarios through one parametrized body produces a test with branching logic, which is harder to read than separate tests.

## Behavior Coverage Over Line Coverage

Line coverage measures which lines ran, not whether anything was actually checked — a test that calls a function and asserts nothing can report 100% coverage while verifying nothing. What matters is *behavior* coverage: the typical path, the boundaries, the error paths, and the invariants. Aim assertions at observable outcomes — return values, raised exceptions, recorded side effects — and make sure the cases that matter (empty, boundary, failure, concurrent) are actually exercised. Coverage tooling is useful for finding code that *no* test touches, which is a real signal; it is misleading when treated as a quality target, because a high percentage says nothing about assertion quality. Use it to find blind spots, not to declare the suite done.

## Mock Boundaries

A mock replaces a real dependency with a stand-in. Mock at the *boundary* of your system — the network call, the clock, the filesystem, the external service — where the real thing is slow, nondeterministic, or has side effects you cannot afford in a test. Do not mock the code under test or its close collaborators; a test that mocks the very objects it is exercising ends up asserting that your code called your mock the way the test told it to, which is circular and breaks on any refactor. The more a test mocks, the less it proves about real behavior, so prefer real objects for anything cheap and deterministic and reserve mocks for the genuine edges. When a piece of code is hard to test without mocking everything around it, that is usually a design signal — the dependencies want to be injected as arguments rather than reached for internally.

## Tests As Documentation

A well-written test is the most reliable documentation a project has, because it cannot drift from the code without failing. A reader who wants to know how to use a function should be able to open its tests and see realistic calls with expected results. This is achievable on purpose: arrange-act-assert structure so each test reads as setup, action, expectation; one behavior per test so a failure points at one thing; names that state the guarantee. When tests are written this way, they double as worked examples, which is why test-driven development — writing the test first to pin the intended behavior, then making it pass — produces both a design tool and living documentation in one pass. Driving the design from tests also tends to push code toward smaller, injectable units, which is the same property that makes the production code easier to maintain.
