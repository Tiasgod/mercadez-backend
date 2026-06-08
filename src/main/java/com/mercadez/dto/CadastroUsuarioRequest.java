package com.mercadez.dto;

import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class CadastroUsuarioRequest {
    @NotBlank(message = "Nome é obrigatório")
    @Size(min = 2, max = 100)
    private String nome;

    @NotBlank(message = "Email é obrigatório")
    @Email(message = "Email inválido")
    private String email;

    @NotBlank(message = "Senha é obrigatória")
    @Size(min = 6, message = "Senha deve ter no mínimo 6 caracteres")
    private String senha;

    @Size(max = 14, message = "CPF deve ter no máximo 14 caracteres")
    private String cpf;
}
