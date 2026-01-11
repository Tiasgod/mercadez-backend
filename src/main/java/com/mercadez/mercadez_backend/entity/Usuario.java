package com.mercadez.mercadez_backend.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "usuarios")
public class Usuario {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;  // id AUTO_INCREMENT

    @Column(nullable = false, length = 100)
    private String nome;  // nome do usuário

    @Column(nullable = false, length = 100, unique = true)
    private String email;  // email único

    @Column(nullable = false, length = 14, unique = true)
    private String cpf;  // CPF único

    @Column(nullable = false, length = 100)
    private String senha;  // senha

    @Column(name = "criado_em", nullable = false)
    private LocalDateTime criadoEm = LocalDateTime.now();  // timestamp de criação

    @Column(length = 255)
    private String perfil;  // perfil opcional

    // ===========================
    // Getters e Setters
    // ===========================
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getNome() { return nome; }
    public void setNome(String nome) { this.nome = nome; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getCpf() { return cpf; }
    public void setCpf(String cpf) { this.cpf = cpf; }

    public String getSenha() { return senha; }
    public void setSenha(String senha) { this.senha = senha; }

    public LocalDateTime getCriadoEm() { return criadoEm; }
    public void setCriadoEm(LocalDateTime criadoEm) { this.criadoEm = criadoEm; }

    public String getPerfil() { return perfil; }
    public void setPerfil(String perfil) { this.perfil = perfil; }
}
