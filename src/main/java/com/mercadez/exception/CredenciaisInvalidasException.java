package com.mercadez.exception;

public class CredenciaisInvalidasException extends RuntimeException {
    public CredenciaisInvalidasException() { super("Email ou senha incorretos."); }
}
