# TDD iteration 001 — SAX-040 product audio upload gateway

## Scope

SAX-040 creates the Spring Boot product boundary for the existing FastAPI upload endpoint.

```text
priority:   P1
estimate:   5 points
epic:       E4 — Product and human review
```

Only the initial HTTP 202 job creation flow is implemented. SAX-041 and later stories remain untouched.

## Empty repository bootstrap

The GitHub repository initially had no commits and reported `size: 0`. A feature branch could not exist until one root commit was created. The connector cannot create a parentless multi-file commit, so the authorized direct bootstrap contained only README documentation:

```text
79651aabe14e3dd80d75345741f94beb3dc761fc
chore: bootstrap InstrumentalSW Backend repository
```

`.gitignore`, `.editorconfig`, dependencies, tests, source, workflow, and configuration were added only after `feature/SAX-040-audio-upload` was created.

## Harness before RED

```text
2f9fcccbb186b68e165f19b573b2fb75388feabd
build(SAX-040): establish backend test harness
```

The harness fixed Java 21, Spring Boot 3.5.16, Maven 3.9.16, JUnit 5, Spotless, Checkstyle, JaCoCo, and the normal GitHub Actions gate. It contained no controller, service, client, gateway, or product behavior.

## Initial RED

Tests-only commits preceded production:

```text
f4769864824ed06f90bc6bfe43eae5d1f1eb8304
  test(SAX-040): define upload application contract

daf9e617b029bc3aae59261406f289353e7d7f7a
  test(SAX-040): define product upload API contract

263f2ce1a873edc121bc02673d8c1b351da66fb3
  test(SAX-040): define FastAPI multipart forwarding and error mapping
```

The draft PR opened at the tests-only head. The normal workflow installed Java and Maven successfully and then failed in test compilation because the following product contracts did not exist:

```text
SubmitTranscription
TranscriptionGateway
TranscriptionUpload
TranscriptionUploadController
FastApiTranscriptionClient
domain enums and response contracts
configuration and public error handler
```

Evidence:

```text
Quality #1
run: 29856758697
job: 88722899956
result: failure during Verify after Java and Maven setup
```

No dependency-installation error was used as RED evidence.

## GREEN

Production was introduced after RED in inward-facing order:

```text
domain error codes, enums, exception, and validated job
immutable application upload command and gateway port
SubmitTranscription validation and normalization
configurable RestClient FastAPI adapter
configuration, CORS, multipart limits
public controller, response DTO, and error envelope
```

The application use case validates before the gateway, strips client path components, accepts `.mp3` and `.wav` case-insensitively, preserves content type and exact enum values, clones bytes, and does not persist.

The infrastructure test uses a real JDK HTTP server and inspects the emitted multipart body rather than verifying only a mock call.

## REFACTOR and diagnostics

The first GREEN compile exposed checked `IOException` boundaries in Spring `ClientHttpResponse` and Jackson byte-array parsing. Both were translated to controlled upstream errors.

The first completed test run exposed two test-harness issues:

```text
multipart inspection matched filename= as a fourth name
WebMvcTest required explicit CorsProperties registration
```

The regex was restricted to `Content-Disposition` field names and configuration properties were registered through `@EnableConfigurationProperties`.

The pinned formatter was applied to production and test sources. The final workflow was restored to:

```text
permissions: contents: read
checkout: pull request merge ref
command: ./mvnw verify
```

Quality evidence is uploaded as an external artifact. No generated log, coverage report, multipart, or audio is committed.

## Final regression RED

Two contract gaps were closed with new tests before their fixes:

```text
356b4d27199558a757ac5769a441fcff11fd76fd
  test(SAX-040): preserve explicit upstream HTTP status

d04da90e4b013864f6c349e02e27cd8dc5414a52
  test(SAX-040): reject incompatible upstream enums as 502
```

The tests required FastAPI HTTP 400 to remain public HTTP 400 and required an unknown enum inside an upstream HTTP 202 body to become a controlled 502 response error.

```text
Quality #41
run: 29860689194
job: 88736319956
result: failure after Java and Maven setup because publicStatus did not exist
```

Production fixes followed that RED:

```text
d42f6f87ad88dda62edf295be843dfc18236bb98
  fix(SAX-040): preserve stable public error status

563c5720256a3c2176cf026f910007dba88c0efd
  fix(SAX-040): translate the controlled public status

cddbd5cb7672b65961104c1b6fea1566ae3f0eb2
  fix(SAX-040): preserve 400 and wrap incompatible upstream enums
```

Application/domain still do not depend on Spring HTTP. The stable exception carries a numeric public error status, and the web adapter alone turns it into a Spring response.

## Test coverage

The completed suite covers:

- valid WAV and MP3 in lowercase and uppercase;
- exact public multipart names;
- normalized basename without client path leakage;
- missing, empty, unsupported, invalid instrument, and invalid mode requests;
- complete HTTP 202 response preservation;
- stable public JSON errors;
- one gateway call with unchanged bytes and enums;
- real upstream multipart method, path, names, filename, content, MIME, instrument, and mode;
- upstream 400, 413, 415, 422, 500, and 503;
- timeout and refused connection;
- malformed JSON, invalid UUID, invalid SHA, unsafe response filename, and unknown response enums;
- explicit preservation of upstream HTTP 400;
- domain invariants, defensive copies, configuration normalization, size-limit and malformed-multipart envelopes.

Final production-head evidence before this documentation update:

```text
head: a7d7748394d64e392bc34d6d812d2f1dc827196a
Quality #47
run: 29861381323
job: 88738667008
40 tests passed
0 failures, 0 errors, 0 skipped
215 / 227 lines covered = 94.71%
63 / 78 branches covered = 80.77%
Spotless: 26 Java files clean
Checkstyle: 0 violations
JaCoCo: all coverage checks met
BUILD SUCCESS
```

The draft PR body records the final documentation-only head and its last successful workflow without changing product behavior again.

## Contract coherence

The Backend tests demonstrate the same contract already present in the AI repository:

```text
file
saxophone_type
input_mode

soprano | alto | tenor | baritone
solo | mixture
```

No shared package or second contract was created.

## Boundaries

No audio is persisted. No replacement SHA-256 is calculated. The service does not expose its internal FastAPI URL, raw upstream body, stack trace, multipart, or audio. It does not implement authentication, database, storage, queue, worker, retries, polling, WebSocket, SSE, processing states, SAX-041, or later stories.
