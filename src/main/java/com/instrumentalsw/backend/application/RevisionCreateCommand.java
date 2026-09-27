package com.instrumentalsw.backend.application;

import java.util.List;
import java.util.Objects;

public record RevisionCreateCommand(int baseRevisionNumber, List<RevisionOperation> operations) {
    public RevisionCreateCommand {
        if (baseRevisionNumber < 0) {
            throw new IllegalArgumentException("baseRevisionNumber must be non-negative");
        }
        operations = List.copyOf(Objects.requireNonNull(operations, "operations"));
        if (operations.isEmpty()) {
            throw new IllegalArgumentException("operations must not be empty");
        }
        operations.forEach(Objects::requireNonNull);
    }
}
