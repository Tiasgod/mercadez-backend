package com.mercadez.exception;

import com.mercadez.dto.ErroResponse;
import org.springframework.http.*;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {

    /** Erros de validação (@Valid) */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErroResponse> handleValidation(MethodArgumentNotValidException ex) {
        String mensagem = ex.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining("; "));
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(new ErroResponse(400, "Dados inválidos", mensagem));
    }

    /** Regras de negócio (email duplicado, CNPJ inválido, etc.) */
    @ExceptionHandler(NegocioException.class)
    public ResponseEntity<ErroResponse> handleNegocio(NegocioException ex) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(new ErroResponse(400, "Erro de negócio", ex.getMessage()));
    }

    /** Recurso não encontrado */
    @ExceptionHandler(NaoEncontradoException.class)
    public ResponseEntity<ErroResponse> handleNaoEncontrado(NaoEncontradoException ex) {
        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .body(new ErroResponse(404, "Não encontrado", ex.getMessage()));
    }

    /** Credenciais inválidas no login */
    @ExceptionHandler(CredenciaisInvalidasException.class)
    public ResponseEntity<ErroResponse> handleCredenciais(CredenciaisInvalidasException ex) {
        return ResponseEntity
                .status(HttpStatus.UNAUTHORIZED)
                .body(new ErroResponse(401, "Não autorizado", ex.getMessage()));
    }

    /** Fallback genérico */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErroResponse> handleGenerico(Exception ex) {
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErroResponse(500, "Erro interno", "Ocorreu um erro inesperado."));
    }
}
