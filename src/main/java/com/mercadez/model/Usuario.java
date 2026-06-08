package com.mercadez.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "usuarios",
    uniqueConstraints = @UniqueConstraint(columnNames = "email", name = "uk_usuarios_email"))
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class Usuario {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(min = 2, max = 100)
    @Column(nullable = false, length = 100)
    private String nome;

    @NotBlank
    @Email
    @Column(nullable = false, unique = true, length = 150)
    private String email;

    @NotBlank
    @Column(nullable = false)
    private String senha;

    @Size(max = 14)
    @Column(length = 14)
    private String cpf;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    @Builder.Default
    private Perfil perfil = Perfil.CLIENTE;

    @Column(name = "criado_em", updatable = false)
    private LocalDateTime criadoEm;

    @Column(name = "atualizado_em")
    private LocalDateTime atualizadoEm;

    @PrePersist
    void onCreate() {
        criadoEm = atualizadoEm = LocalDateTime.now();
    }

    @PreUpdate
    void onUpdate() {
        atualizadoEm = LocalDateTime.now();
    }

    public enum Perfil { CLIENTE, ADMIN }
}
