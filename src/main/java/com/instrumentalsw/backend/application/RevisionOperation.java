package com.instrumentalsw.backend.application;

public sealed interface RevisionOperation
        permits RevisionUpdateOperation, RevisionAddOperation, RevisionDeleteOperation {
    String type();
}
