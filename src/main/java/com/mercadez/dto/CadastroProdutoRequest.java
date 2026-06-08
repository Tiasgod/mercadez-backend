package com.mercadez.dto;

import jakarta.validation.constraints.*;
import lombok.Data;
import java.math.BigDecimal;

@Data
public class CadastroProdutoRequest {
    @NotBlank(message = "Nome do produto é obrigatório")
    @Size(min = 2, max = 150)
    private String nomeProduto;

    @Size(max = 500)
    private String tags;

    @NotNull(message = "Preço é obrigatório")
    @DecimalMin(value = "0.01", message = "Preço deve ser maior que zero")
    private BigDecimal preco;

    @NotNull(message = "Quantidade é obrigatória")
    @Min(value = 0, message = "Quantidade não pode ser negativa")
    private Integer quantidade;
}
