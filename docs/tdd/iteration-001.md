# TDD iteration 001 — SAX-040 accessible audio upload flow

## Scope

SAX-040 implements one responsive Next.js screen that creates an `UPLOADED` transcription job through the Spring Boot product API.

```text
priority:   P1
estimate:   5 points
epic:       E4 — Product and human review
```

The iteration ends after HTTP 202 is displayed. SAX-041 and later stories are not started.

## Empty repository bootstrap

The repository initially had no commits and reported `size: 0`. The authorized direct root commit contained documentation only:

```text
aa82eb6091e6214a5ae7559780e3fc02b0844655
chore: bootstrap InstrumentalSW Frontend repository
```

The connector cannot create a parentless multi-file commit, so `.gitignore`, `.editorconfig`, tooling, tests, workflows, and product source were added only after `feature/SAX-040-audio-upload` existed.

## Harness before RED

```text
86552208df9a1c9717d6ed31f9a6767da65f3d2f
build(SAX-040): establish frontend test harness
```

The harness fixed Next.js 16.2.11, React 19.2.8, TypeScript 5.8.3 strict mode, Vitest 4.1.10, Testing Library, user-event, jsdom, ESLint, Prettier, and the normal Node 24.18.0 workflow. The page contained only a placeholder and no SAX-040 form or HTTP client.

The normal workflow generated the npm lockfile once with npm 11.6.2:

```text
58de9cccdccc93e1d9025bb0d06db0b87f4d0b2e
build(SAX-040): lock frontend dependencies
```

The workflow was then restored to read-only `npm ci`.

## Initial RED

Tests-only commits preceded production:

```text
44afc4b3c16dc61c7136039ced48ed805303cf70
  test(SAX-040): define typed multipart submission contract

dc880b4158bdf497425be6effc718ab4bef9aace
  test(SAX-040): define accessible upload success and error states
```

The draft PR opened before these modules existed:

```text
src/lib/transcription-api.ts
src/components/audio-upload-form.tsx
```

The normal workflow successfully installed Node, pinned npm, the lockfile, and all dependencies. `npm run quality` then failed because the tested client and form modules were absent. Installation failure was not used as RED evidence.

```text
Quality #1
run: 29858998366
job: 88730579834
result: failure in Run quality gate
```

## GREEN

Production followed the test contracts:

```text
typed union values and response contract
TranscriptionApiError
submitTranscription FormData client
accessible AudioUploadForm
explicit five-state UI model
complete success result
warm responsive styling
App Router page composition
```

The client appends exactly `file`, `saxophone_type`, and `input_mode`, sends POST only to the configured product Backend, accepts only HTTP 202, and validates all returned fields.

The form validates extension and zero-byte content before API contact, does not upload automatically, preserves a valid selection after failure, prevents double submission, and has no polling or automatic retry.

## REFACTOR and diagnostics

The first completed GREEN test run produced:

```text
25 passed
2 failed
```

Both failures exposed one overly narrow client assumption: a syntactically valid UUID was incorrectly required to contain RFC version and variant nibbles. The Backend uses Java `UUID.fromString`, so the frontend was aligned to the same syntactic shape without imposing an additional version contract.

The next run produced:

```text
27 passed
coverage above 90%
ESLint passed
Prettier identified four files
```

The pinned Prettier formatter was applied once to those files and the workflow was restored to read-only operation. Formatting did not change functional expectations.

Next.js added `.next/dev/types/**/*.ts` to the local build workspace. That stable include was recorded explicitly in `tsconfig.json`, and `NEXT_TELEMETRY_DISABLED=1` was fixed in CI before the final build.

## Accessibility regression RED

A final audit found that file-related errors were associated only with the technical `Field: file` line instead of the complete alert summary. A focused test preceded the correction:

```text
17f99c33b5994ba0d977c8037081bee496e2f1f3
  test(SAX-040): associate file errors with alert summary
```

The normal workflow installed Node, npm, and dependencies successfully and then failed in the quality step:

```text
Quality #21
run: 29860879497
job: 88736970005
result: failure from the new ARIA expectation
```

Production was corrected after RED:

```text
8f462fc7c50251a9362be720fdf5928ca98105b0
  fix(SAX-040): associate file input with complete error alert
```

For file-related errors, the input now includes `upload-error` in `aria-describedby`, so assistive technology receives the readable message, code, field, and retry action from the complete alert.

## Test coverage

The suite covers:

- visible labels and role-based queries;
- exact instrument and mode option values;
- file required validation;
- lowercase and uppercase WAV/MP3;
- unsupported and zero-byte files;
- filename and size display;
- replacement without automatic upload;
- exact POST URL and FormData field names/content;
- absence of manual `Content-Type`;
- HTTP 202 parsing and every displayed field;
- button disabling and synchronous double-submit protection;
- local validation without fetch;
- public 400, 413, 415, 422, and 502 envelopes;
- rejected network requests;
- malformed JSON and incompatible UUID, SHA, size, enums, and status;
- selection preservation and explicit retry;
- error focus, `role="alert"`, `aria-live`, keyboard traversal, and safe unknown errors;
- complete alert association through `aria-describedby`;
- explicit reset for another upload.

Final production-head evidence before this documentation update:

```text
head: 8c80477a146c5b1b90e0d7b5782ad736b98e8e25
Quality #25
run: 29861454062
job: 88738914866
3 test files passed
28 tests passed
92.43% statements
91.76% branches
100% functions
92.43% lines
ESLint passed
Prettier passed
TypeScript passed
Next.js 16.2.11 production build passed
static route / generated
```

The draft PR body records the final documentation-only head and its last successful workflow without changing product behavior again.

## Contract coherence

Frontend FormData tests demonstrate the same names and values enforced in Backend multipart tests and present in the existing AI route:

```text
file
saxophone_type
input_mode

soprano | alto | tenor | baritone
solo | mixture
```

No shared package or alternative API contract is introduced.

## Boundaries

The frontend does not know the FastAPI URL, persist audio, create object URLs, play audio, start polling, open WebSocket/SSE, navigate to progress, show a timeline or score, implement editing or downloads, authenticate, or begin SAX-041.
