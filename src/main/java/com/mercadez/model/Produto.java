package com.mercadez.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import lombok.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "produtos")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class Produto {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(min = 2, max = 150)
    @Column(name = "nome_produto", nullable = false, length = 150)
    private String nomeProduto;

    @Size(max = 500)
    @Column(length = 500)
    private String tags;

    @NotNull
    @DecimalMin("0.01")
    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal preco;

    @NotNull
    @Min(0)
    @Column(nullable = false)
    private Integer quantidade;

    @Builder.Default
    private Boolean ativo = true;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "afiliado_id", nullable = false)
    private Afiliado afiliado;

    @Column(name = "criado_em", updatable = false)
    private LocalDateTime criadoEm;

    @Column(name = "atualizado_em")
    private LocalDateTime atualizadoEm;

    @PrePersist
    void onCreate() { criadoEm = atualizadoEm = LocalDateTime.now(); }

    @PreUpdate
    void onUpdate() { atualizadoEm = LocalDateTime.now(); }
}
