package com.mercadez.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "contatos")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class Contato {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(min = 2, max = 100)
    @Column(nullable = false, length = 100)
    private String nome;

    @NotBlank
    @Email
    @Column(nullable = false, length = 150)
    private String email;

    @NotBlank
    @Size(min = 10, max = 2000)
    @Column(nullable = false, length = 2000)
    private String mensagem;

    @Builder.Default
    private Boolean lido = false;

    @Column(name = "criado_em", updatable = false)
    private LocalDateTime criadoEm;

    @PrePersist
    void onCreate() { criadoEm = LocalDateTime.now(); }
}
