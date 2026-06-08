package com.mercadez.dto;

import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class CadastroAfiliadoRequest {
    @NotBlank(message = "Nome do proprietário é obrigatório")
    @Size(min = 2, max = 100)
    private String nome_proprietario;   // snake_case para bater com o payload do frontend

    @NotBlank(message = "Email é obrigatório")
    @Email(message = "Email inválido")
    private String email;

    @NotBlank(message = "Senha é obrigatória")
    @Size(min = 6, message = "Senha deve ter no mínimo 6 caracteres")
    private String senha;

    @NotBlank(message = "CNPJ é obrigatório")
    @Size(min = 14, max = 18)
    private String cnpj;

    @Size(max = 200)
    private String endereco;

    @Size(max = 20)
    private String telefone;

    @NotBlank(message = "Nome do mercado é obrigatório")
    @Size(max = 150)
    private String mercado;

    @Size(max = 100)
    private String categoria;

    @Min(value = 0, message = "Número de funcionários não pode ser negativo")
    private Integer funcionarios;

    @Size(max = 200)
    private String pagamento;
}
