package com.mercadez.dto;

import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class ContatoRequest {
    @NotBlank(message = "Nome é obrigatório")
    @Size(min = 2, max = 100)
    private String nome;

    @NotBlank(message = "Email é obrigatório")
    @Email(message = "Email inválido")
    private String email;

    @NotBlank(message = "Mensagem é obrigatória")
    @Size(min = 10, max = 2000)
    private String mensagem;
}
