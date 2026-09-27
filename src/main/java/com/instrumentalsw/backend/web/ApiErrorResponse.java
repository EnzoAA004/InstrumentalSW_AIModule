package com.instrumentalsw.backend.web;

public record ApiErrorResponse(String code, String message, String field) {}
