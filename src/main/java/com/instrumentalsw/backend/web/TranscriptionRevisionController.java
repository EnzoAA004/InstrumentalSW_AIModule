package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.instrumentalsw.backend.application.CreateTranscriptionRevision;
import com.instrumentalsw.backend.application.GetTranscriptionRevision;
import com.instrumentalsw.backend.application.GetTranscriptionRevisionHistory;
import com.instrumentalsw.backend.application.RequestTranscriptionRegeneration;
import com.instrumentalsw.backend.application.RevisionAddOperation;
import com.instrumentalsw.backend.application.RevisionCreateCommand;
import com.instrumentalsw.backend.application.RevisionDeleteOperation;
import com.instrumentalsw.backend.application.RevisionOperation;
import com.instrumentalsw.backend.application.RevisionUpdateOperation;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/transcriptions")
public final class TranscriptionRevisionController {
    private final GetTranscriptionRevisionHistory getHistory;
    private final GetTranscriptionRevision getRevision;
    private final CreateTranscriptionRevision createRevision;
    private final RequestTranscriptionRegeneration requestRegeneration;

    public TranscriptionRevisionController(
            GetTranscriptionRevisionHistory getHistory,
            GetTranscriptionRevision getRevision,
            CreateTranscriptionRevision createRevision,
            RequestTranscriptionRegeneration requestRegeneration) {
        this.getHistory = getHistory;
        this.getRevision = getRevision;
        this.createRevision = createRevision;
        this.requestRegeneration = requestRegeneration;
    }

    @GetMapping(value = "/{jobId}/revisions", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TranscriptionRevisionHistoryResponse> history(@PathVariable String jobId) {
        UUID parsed = parseJobId(jobId);
        return ResponseEntity.ok(TranscriptionRevisionHistoryResponse.from(getHistory.execute(parsed)));
    }

    @GetMapping(value = "/{jobId}/revisions/{revisionNumber}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TranscriptionRevisionResponse> detail(
            @PathVariable String jobId, @PathVariable String revisionNumber) {
        UUID parsed = parseJobId(jobId);
        int revision = parseRevisionNumber(revisionNumber);
        return ResponseEntity.ok(TranscriptionRevisionResponse.from(getRevision.execute(parsed, revision)));
    }

    @PostMapping(
            value = "/{jobId}/revisions",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TranscriptionRevisionResponse> create(
            @PathVariable String jobId, @RequestBody JsonNode body) {
        UUID parsed = parseJobId(jobId);
        RevisionCreateCommand command = parseCommand(body);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(TranscriptionRevisionResponse.from(createRevision.execute(parsed, command)));
    }

    @PostMapping(
            value = "/{jobId}/revisions/{revisionNumber}/regeneration-requests",
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<RegenerationRequestResponse> regenerate(
            @PathVariable String jobId, @PathVariable String revisionNumber) {
        UUID parsed = parseJobId(jobId);
        int revision = parseRevisionNumber(revisionNumber);
        return ResponseEntity.accepted()
                .body(RegenerationRequestResponse.from(requestRegeneration.execute(parsed, revision)));
    }

    private static UUID parseJobId(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException error) {
            throw new TranscriptionException(UploadErrorCode.INVALID_JOB_ID, "Job ID must be a valid UUID.", "job_id");
        }
    }

    private static int parseRevisionNumber(String value) {
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < 0 || !Integer.toString(parsed).equals(value)) {
                throw new NumberFormatException();
            }
            return parsed;
        } catch (NumberFormatException error) {
            throw new TranscriptionException(
                    UploadErrorCode.REVISION_NOT_FOUND, "Transcription revision not found.", "revision_number");
        }
    }

    private static RevisionCreateCommand parseCommand(JsonNode body) {
        requireFields(body, Set.of("base_revision_number", "operations"));
        int base = nonNegativeInteger(body, "base_revision_number", "base_revision_number");
        JsonNode operationsNode = required(body, "operations");
        if (!operationsNode.isArray() || operationsNode.isEmpty()) {
            throw invalidOperation("At least one operation is required.");
        }
        List<RevisionOperation> operations = new ArrayList<>();
        Set<String> targeted = new HashSet<>();
        for (JsonNode operation : operationsNode) {
            RevisionOperation parsed = parseOperation(operation);
            if (parsed instanceof RevisionUpdateOperation update && !targeted.add(update.eventId())) {
                throw invalidOperation("An event cannot be changed more than once.");
            }
            if (parsed instanceof RevisionDeleteOperation delete && !targeted.add(delete.eventId())) {
                throw invalidOperation("An event cannot be changed more than once.");
            }
            operations.add(parsed);
        }
        return new RevisionCreateCommand(base, operations);
    }

    private static RevisionOperation parseOperation(JsonNode node) {
        if (node == null || !node.isObject()) {
            throw invalidOperation("Each operation must be an object.");
        }
        String type = text(node, "type");
        return switch (type) {
            case "update" -> {
                requireFields(
                        node, Set.of("type", "event_id", "written_pitch_midi", "onset_seconds", "offset_seconds"));
                yield new RevisionUpdateOperation(
                        text(node, "event_id"),
                        midi(node, "written_pitch_midi"),
                        time(node, "onset_seconds", true),
                        time(node, "offset_seconds", false));
            }
            case "add" -> {
                Set<String> actual = fields(node);
                Set<String> required = Set.of("type", "written_pitch_midi", "onset_seconds", "offset_seconds");
                Set<String> allowed = new HashSet<>(required);
                allowed.add("velocity");
                if (!actual.containsAll(required) || !allowed.containsAll(actual)) {
                    throw invalidOperation("Add fields are incompatible.");
                }
                int velocity = node.has("velocity") ? midi(node, "velocity") : 64;
                yield new RevisionAddOperation(
                        midi(node, "written_pitch_midi"),
                        time(node, "onset_seconds", true),
                        time(node, "offset_seconds", false),
                        velocity);
            }
            case "delete" -> {
                requireFields(node, Set.of("type", "event_id"));
                yield new RevisionDeleteOperation(text(node, "event_id"));
            }
            default -> throw invalidOperation("Unsupported revision operation type.");
        };
    }

    private static int midi(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isIntegralNumber() || !value.canConvertToInt()) {
            throw invalidEvent(field + " must be an integer from 0 to 127.");
        }
        int parsed = value.intValue();
        if (parsed < 0 || parsed > 127) {
            throw invalidEvent(field + " must be an integer from 0 to 127.");
        }
        return parsed;
    }

    private static double time(JsonNode parent, String field, boolean nonNegative) {
        JsonNode value = required(parent, field);
        if (!value.isNumber() || !Double.isFinite(value.doubleValue())) {
            throw invalidEvent(field + " must be finite.");
        }
        double parsed = value.doubleValue();
        if (nonNegative && parsed < 0) {
            throw invalidEvent(field + " must be non-negative.");
        }
        return parsed;
    }

    private static int nonNegativeInteger(JsonNode parent, String field, String publicField) {
        JsonNode value = required(parent, field);
        if (!value.isIntegralNumber() || !value.canConvertToInt() || value.intValue() < 0) {
            throw new TranscriptionException(
                    UploadErrorCode.INVALID_REVISION_OPERATION,
                    field + " must be a non-negative integer.",
                    publicField);
        }
        return value.intValue();
    }

    private static String text(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isTextual() || value.textValue().isBlank()) {
            throw invalidOperation(field + " must be non-blank text.");
        }
        return value.textValue();
    }

    private static JsonNode required(JsonNode parent, String field) {
        if (parent == null
                || !parent.isObject()
                || !parent.has(field)
                || parent.get(field).isNull()) {
            throw invalidOperation(field + " is required.");
        }
        return parent.get(field);
    }

    private static void requireFields(JsonNode node, Set<String> expected) {
        if (node == null || !node.isObject() || !fields(node).equals(expected)) {
            throw invalidOperation("Request fields are incompatible.");
        }
    }

    private static Set<String> fields(JsonNode node) {
        Set<String> result = new HashSet<>();
        node.fieldNames().forEachRemaining(result::add);
        return result;
    }

    private static TranscriptionException invalidOperation(String message) {
        return new TranscriptionException(UploadErrorCode.INVALID_REVISION_OPERATION, message, "operations");
    }

    private static TranscriptionException invalidEvent(String message) {
        return new TranscriptionException(UploadErrorCode.INVALID_REVISION_EVENT, message, "operations");
    }
}
