# Audio upload gateway contract v1

## Purpose

SAX-040 introduces the product-facing upload boundary. The Backend accepts the browser request, validates stable public constraints, forwards the same multipart contract to the existing FastAPI endpoint, translates upstream failures, and returns the created job without field loss.

```text
Next.js
→ Spring Boot product API
→ existing Python/FastAPI AI service
```

No additional microservice or public API is introduced.

## Public request

```http
POST /api/v1/transcriptions
Content-Type: multipart/form-data
```

Required parts:

```text
file
saxophone_type
input_mode
```

Allowed values:

```text
saxophone_type = soprano | alto | tenor | baritone
input_mode     = solo | mixture
```

The names and values are identical to the AI service contract. They are not renamed between layers.

## File validation

Validation occurs before contacting FastAPI:

- the part must exist;
- content must contain at least one byte;
- the original filename must exist;
- client path components using `/` or `\\` are removed;
- the resulting basename must end in `.mp3` or `.wav`, case-insensitively;
- MIME type is forwarded when present but is not the extension authority.

The Backend does not inspect, play, decode, store, or retain the audio. `TranscriptionUpload` defensively copies request bytes and they remain request-scoped.

## Upstream request

The configured client sends exactly:

```http
POST {SAXO_AI_BASE_URL}/api/v1/transcriptions
Content-Type: multipart/form-data; boundary=generated-by-Spring
```

The file part preserves normalized filename, bytes, and reported content type. Text parts preserve the exact enum values. Only HTTP 202 is a successful creation response.

## Successful response

```json
{
  "job_id": "UUID",
  "status": "UPLOADED",
  "filename": "recording.wav",
  "size_bytes": 12345,
  "audio_sha256": "64 lowercase hexadecimal characters",
  "saxophone_type": "alto",
  "input_mode": "solo"
}
```

The Backend validates:

- `job_id` parses as UUID;
- `status` is nonblank;
- `filename` is a nonblank basename without path separators;
- `size_bytes` is nonnegative;
- `audio_sha256` is exactly 64 lowercase hexadecimal characters;
- saxophone type and input mode are known values.

The FastAPI SHA-256 remains authoritative. Spring does not calculate a substitute digest.

## Public error envelope

```json
{
  "code": "UNSUPPORTED_AUDIO_FORMAT",
  "message": "Only MP3 and WAV files are supported.",
  "field": "file"
}
```

`field` is null when the error is not associated with one public field.

Stable codes:

```text
AUDIO_FILE_REQUIRED
EMPTY_AUDIO_FILE
UNSUPPORTED_AUDIO_FORMAT
INVALID_SAXOPHONE_TYPE
INVALID_INPUT_MODE
AUDIO_SIZE_LIMIT_EXCEEDED
INVALID_TRANSCRIPTION_REQUEST
AI_SERVICE_UNAVAILABLE
AI_SERVICE_ERROR
```

Status translation:

| Condition | Public status |
| --- | --- |
| Missing/empty file or invalid enum | 400 |
| Unsupported extension | 415 |
| Product or FastAPI size limit | 413 |
| Invalid upstream request / multipart | 422 |
| FastAPI 5xx | 502 |
| Timeout / refused connection | 502 |
| Malformed or incompatible upstream JSON | 502 |

No response exposes audio bytes, multipart bodies, stack traces, hostnames, internal URLs, upstream HTML, tokens, or client paths.

## Configuration

```text
SAXO_AI_BASE_URL=http://localhost:8000
SAXO_AI_CONNECT_TIMEOUT=2s
SAXO_AI_READ_TIMEOUT=30s
SAXO_FRONTEND_ORIGIN=http://localhost:3000
SAXO_MAX_MULTIPART_FILE_SIZE=101MB
SAXO_MAX_MULTIPART_REQUEST_SIZE=102MB
```

CORS allows the configured frontend origin for POST and OPTIONS. Credentials are disabled and wildcard origins are not used.

## Architecture

```text
web/TranscriptionUploadController
→ application/SubmitTranscription
→ application/TranscriptionGateway
→ infrastructure/ai/FastApiTranscriptionClient
```

Application contracts do not depend on Spring HTTP. Infrastructure owns RestClient and multipart encoding. Web owns DTOs and public error translation.

## Limitations

SAX-040 creates only the initial `UPLOADED` job. It does not implement authentication, persistence, object storage, processing orchestration, retry, polling, WebSocket, SSE, progress states, source separation, model execution from Spring, SAX-041, or later stories.
