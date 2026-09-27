package com.instrumentalsw.backend.application;

public record RevisionAddOperation(int writtenPitchMidi, double onsetSeconds, double offsetSeconds, int velocity)
        implements RevisionOperation {
    @Override
    public String type() {
        return "add";
    }
}
