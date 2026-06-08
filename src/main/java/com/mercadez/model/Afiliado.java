package com.mercadez.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "afiliados",
    uniqueConstraints = {
        @UniqueConstraint(columnNames = "email", name = "uk_afiliados_email"),
        @UniqueConstraint(columnNames = "cnpj",  name = "uk_afiliados_cnpj")
    })
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class Afiliado {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(min = 2, max = 100)
    @Column(name = "nome_proprietario", nullable = false, length = 100)
    private String nomeProprietario;

    @NotBlank
    @Email
    @Column(nullable = false, unique = true, length = 150)
    private String email;

    @NotBlank
    @Column(nullable = false)
    private String senha;

    @NotBlank
    @Size(min = 14, max = 18)
    @Column(nullable = false, unique = true, length = 18)
    private String cnpj;

    @Size(max = 200)
    @Column(length = 200)
    private String endereco;

    @Size(max = 20)
    @Column(length = 20)
    private String telefone;

    @NotBlank
    @Size(max = 150)
    @Column(nullable = false, length = 150)
    private String mercado;

    @Size(max = 100)
    @Column(length = 100)
    private String categoria;

    @Min(0)
    private Integer funcionarios;

    @Size(max = 200)
    @Column(length = 200)
    private String pagamento;

    @Builder.Default
    private Boolean ativo = true;

    @Column(name = "criado_em", updatable = false)
    private LocalDateTime criadoEm;

    @Column(name = "atualizado_em")
    private LocalDateTime atualizadoEm;

    @PrePersist
    void onCreate() { criadoEm = atualizadoEm = LocalDateTime.now(); }

    @PreUpdate
    void onUpdate() { atualizadoEm = LocalDateTime.now(); }
}
