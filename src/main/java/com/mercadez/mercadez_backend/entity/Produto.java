package com.mercadez.mercadez_backend.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "produtos")
public class Produto {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String nomeProduto;
    private String tags;
    private double preco;
    private int quantidade;

    public Produto() {}

    public Produto(String nomeProduto, String tags, double preco, int quantidade) {
        this.nomeProduto = nomeProduto;
        this.tags = tags;
        this.preco = preco;
        this.quantidade = quantidade;
    }

    // Getters e Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getNomeProduto() { return nomeProduto; }
    public void setNomeProduto(String nomeProduto) { this.nomeProduto = nomeProduto; }

    public String getTags() { return tags; }
    public void setTags(String tags) { this.tags = tags; }

    public double getPreco() { return preco; }
    public void setPreco(double preco) { this.preco = preco; }

    public int getQuantidade() { return quantidade; }
    public void setQuantidade(int quantidade) { this.quantidade = quantidade; }
}
